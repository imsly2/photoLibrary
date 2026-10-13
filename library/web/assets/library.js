(function () {
  const main = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  const viewerVideo = document.getElementById("viewer-video");
  const addFolderBtn = document.getElementById("add-folder-btn");
  const addDialog = document.getElementById("add-folder");
  const addPath = document.getElementById("add-path");
  const addSubmit = document.getElementById("add-submit");
  const addCancel = document.getElementById("add-cancel");
  const addError = document.getElementById("add-error");
  const sortSelect = document.getElementById("sort");
  const dirSelect = document.getElementById("dir");
  const zoomSlider = document.getElementById("zoom-slider");
  const scanStatus = document.getElementById("scan-status");
  if (!main || !viewer || !viewerImage || !viewerVideo || !addFolderBtn || !addDialog) {
    return;
  }

  const PLACEHOLDER = "Preview is not available";
  const LEVELS = ["years", "months", "days", "all"];
  const EMPTY = "No pictures yet";

  let settings = {
    sort: "date",
    dir: "desc",
    zoomLevel: "years",
    addFolderDefault: "ask",
    playProxies: "days-and-all",
  };
  let items = [];
  let groups = [];
  let hoveredId = null;
  let viewerIndex = -1;
  let savedScroll = 0;
  let savedLevel = "years";
  let pollTimer = 0;
  let scanning = false;
  let levelWheelLock = false;
  let panning = false;
  let panLastX = 0;
  let panLastY = 0;
  let scale = 1;
  let fitScale = 1;
  let tx = 0;
  let ty = 0;
  let naturalW = 0;
  let naturalH = 0;
  let fitOnLoad = false;
  let renderKey = "";
  let loadGen = 0;

  function levelIndex(level) {
    const idx = LEVELS.indexOf(level);
    return idx === -1 ? 0 : idx;
  }

  function queryString(extra) {
    const params = new URLSearchParams();
    params.set("sort", settings.sort);
    params.set("dir", settings.dir);
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        params.set(key, extra[key]);
      });
    }
    return params.toString();
  }

  function readJson(res) {
    if (!res.ok) {
      return res.json().catch(function () {
        return {};
      }).then(function (body) {
        const err = new Error((body && body.error) || "request");
        err.status = res.status;
        err.body = body;
        throw err;
      });
    }
    return res.json();
  }

  function persist(patch) {
    return fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(readJson).then(function (next) {
      applySettings(next);
      return next;
    });
  }

  function applySettings(data) {
    if (!data) {
      return;
    }
    settings.sort = data.sort || settings.sort;
    settings.dir = data.dir || settings.dir;
    settings.zoomLevel = data.zoomLevel || settings.zoomLevel;
    settings.addFolderDefault = data.addFolderDefault || settings.addFolderDefault;
    settings.playProxies = data.playProxies || settings.playProxies;
    main.dataset.playProxies = settings.playProxies;
  }

  function selectedMode() {
    const node = addDialog.querySelector('input[name="add-mode"]:checked');
    return node ? node.value : "";
  }

  function syncAddEnabled() {
    addSubmit.disabled = !(addPath.value.trim() && selectedMode());
  }

  function clearAddModes() {
    addDialog.querySelectorAll('input[name="add-mode"]').forEach(function (node) {
      node.checked = false;
    });
  }

  function openAddDialog() {
    addError.hidden = true;
    addError.textContent = "";
    addPath.value = "";
    clearAddModes();
    const preset = settings.addFolderDefault;
    if (preset === "copy-here" || preset === "serve-from-there") {
      const radio = addDialog.querySelector('input[name="add-mode"][value="' + preset + '"]');
      if (radio) {
        radio.checked = true;
      }
    }
    syncAddEnabled();
    addDialog.showModal();
    addPath.focus();
  }

  function closeAddDialog() {
    if (addDialog.open) {
      addDialog.close();
    }
  }

  function showStatus(text, visible) {
    if (!scanStatus) {
      return;
    }
    if (!visible) {
      scanStatus.hidden = true;
      return;
    }
    scanStatus.hidden = false;
    scanStatus.textContent = text;
  }

  function sourcesStatus(sources) {
    let added = 0;
    let skipped = 0;
    let errors = 0;
    let running = false;
    (sources || []).forEach(function (source) {
      const scan = source.scan || {};
      added += Number(scan.added || 0);
      skipped += Number(scan.skipped || 0);
      errors += (scan.errors || []).length;
      if (scan.state === "running") {
        running = true;
      }
    });
    return {
      running: running,
      text: "added " + added + ", skipped " + skipped + ", errors " + errors,
    };
  }

  function stillWhich(item) {
    return item && item.kind === "video" ? "poster" : "thumb";
  }

  function hoverAllowed() {
    const policy = settings.playProxies || "days-and-all";
    if (policy === "off") {
      return false;
    }
    const level = settings.zoomLevel;
    if (policy === "always") {
      return true;
    }
    return level === "days" || level === "all";
  }

  let hoverVideo = null;
  let hoverCell = null;

  function stopHover() {
    if (hoverVideo) {
      hoverVideo.pause();
      hoverVideo.removeAttribute("src");
      hoverVideo.load();
      if (hoverVideo.parentNode) {
        hoverVideo.parentNode.removeChild(hoverVideo);
      }
      hoverVideo = null;
    }
    if (hoverCell) {
      const img = hoverCell.querySelector("img");
      if (img) {
        img.hidden = false;
      }
      hoverCell = null;
    }
  }

  function startHover(cell, item) {
    stopHover();
    if (!hoverAllowed() || !item || item.kind !== "video") {
      return;
    }
    const proxyStatus = ((item.renditions || {}).status || {}).proxy;
    if (proxyStatus !== "ready") {
      return;
    }
    const video = document.createElement("video");
    video.muted = true;
    video.defaultMuted = true;
    video.volume = 0;
    video.loop = true;
    video.playsInline = true;
    video.setAttribute("muted", "");
    video.setAttribute("playsinline", "");
    video.src = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    const img = cell.querySelector("img");
    if (img) {
      img.hidden = true;
    }
    cell.appendChild(video);
    hoverVideo = video;
    hoverCell = cell;
    const play = video.play();
    if (play && play.catch) {
      play.catch(function () {});
    }
  }

  function requestStill(cell, id) {
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    const item = itemById(id);
    const which = stillWhich(item);
    const url = "/api/media/" + encodeURIComponent(id) + "?which=" + which;
    if (hoverCell === cell) {
      return;
    }
    if (img.getAttribute("data-still") === url && !img.hidden && img.complete && img.naturalWidth > 0) {
      return;
    }
    const slotStatus = ((item.renditions || {}).status || {})[which];
    if (slotStatus === "error" || slotStatus === "not-applicable") {
      placeholder.hidden = false;
      img.hidden = true;
      return;
    }
    if (slotStatus !== "ready") {
      window.setTimeout(function () {
        requestStill(cell, id);
      }, 1000);
      return;
    }
    fetch(url).then(function (res) {
      if (!res.ok) {
        placeholder.hidden = false;
        img.hidden = true;
        window.setTimeout(function () {
          requestStill(cell, id);
        }, 1000);
        return;
      }
      img.onload = function () {
        placeholder.hidden = true;
        if (hoverCell !== cell) {
          img.hidden = false;
        }
      };
      img.onerror = function () {
        img.hidden = true;
        placeholder.hidden = false;
        window.setTimeout(function () {
          requestStill(cell, id);
        }, 1000);
      };
      img.setAttribute("data-still", url);
      img.src = url;
    }).catch(function () {
      window.setTimeout(function () {
        requestStill(cell, id);
      }, 1000);
    });
  }

  function applyTransform() {
    viewerImage.style.transformOrigin = "0 0";
    viewerImage.style.transform = "translate(" + tx + "px, " + ty + "px) scale(" + scale + ")";
    viewerImage.style.width = naturalW + "px";
    viewerImage.style.height = naturalH + "px";
  }

  function fitViewer() {
    const sw = viewer.clientWidth;
    const sh = viewer.clientHeight;
    if (!naturalW || !naturalH || !sw || !sh) {
      return;
    }
    fitScale = Math.min(sw / naturalW, sh / naturalH);
    if (!isFinite(fitScale) || fitScale <= 0) {
      fitScale = 1;
    }
    scale = fitScale;
    tx = (sw - naturalW * scale) / 2;
    ty = (sh - naturalH * scale) / 2;
    applyTransform();
  }

  function resetViewerVideo() {
    viewerVideo.pause();
    viewerVideo.removeAttribute("src");
    viewerVideo.removeAttribute("poster");
    viewerVideo.removeAttribute("data-source-ready");
    viewerVideo.removeAttribute("data-using-proxy");
    viewerVideo.load();
    viewerVideo.hidden = true;
  }

  function closeViewer() {
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
    viewerImage.hidden = false;
    resetViewerVideo();
    viewerIndex = -1;
    panning = false;
    window.requestAnimationFrame(function () {
      main.scrollTop = savedScroll;
    });
  }

  function originalVideoType(item) {
    const name = ((item && item.filename) || "").toLowerCase();
    if (name.endsWith(".mp4") || name.endsWith(".m4v")) {
      return "video/mp4";
    }
    if (name.endsWith(".webm")) {
      return "video/webm";
    }
    if (name.endsWith(".mov")) {
      return "video/quicktime";
    }
    if (name.endsWith(".avi")) {
      return "video/x-msvideo";
    }
    if (name.endsWith(".mkv")) {
      return "video/x-matroska";
    }
    return "";
  }

  function browserCanPlayOriginal(item) {
    const type = originalVideoType(item);
    if (!type) {
      return false;
    }
    const result = viewerVideo.canPlayType(type);
    return result === "probably" || result === "maybe";
  }

  function playOriginalOrProxy(item) {
    const originalUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=original";
    const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    if (viewerVideo.getAttribute("data-source-ready") === item.id) {
      return;
    }
    function useProxy() {
      if (viewerVideo.getAttribute("data-using-proxy") === "1") {
        return;
      }
      viewerVideo.setAttribute("data-using-proxy", "1");
      viewerVideo.src = proxyUrl;
    }
    viewerVideo.onerror = useProxy;
    viewerVideo.setAttribute("data-source-ready", item.id);
    if (!browserCanPlayOriginal(item)) {
      useProxy();
      return;
    }
    viewerVideo.src = originalUrl;
  }

  function toggleViewerPlay() {
    if (viewerIndex < 0 || viewer.hidden) {
      return;
    }
    const item = items[viewerIndex];
    if (!item || item.kind !== "video") {
      return;
    }
    playOriginalOrProxy(item);
    if (viewerVideo.paused) {
      const play = viewerVideo.play();
      if (play && play.catch) {
        play.catch(function () {
          const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
          if (viewerVideo.getAttribute("data-using-proxy") !== "1") {
            viewerVideo.setAttribute("data-using-proxy", "1");
            viewerVideo.src = proxyUrl;
            const retry = viewerVideo.play();
            if (retry && retry.catch) {
              retry.catch(function () {});
            }
          }
        });
      }
    } else {
      viewerVideo.pause();
    }
  }

  function openStillViewer(item, index) {
    resetViewerVideo();
    viewerImage.hidden = false;
    const url = "/api/media/" + encodeURIComponent(item.id) + "?which=preview";
    const same = viewerIndex === index && !viewer.hidden && viewerImage.getAttribute("src") === url;
    viewerIndex = index;
    viewer.hidden = false;
    viewerImage.draggable = false;
    if (same && viewerImage.complete && viewerImage.naturalWidth > 0) {
      return;
    }
    fitOnLoad = true;
    viewerImage.onload = function () {
      naturalW = viewerImage.naturalWidth;
      naturalH = viewerImage.naturalHeight;
      if (fitOnLoad) {
        fitViewer();
        fitOnLoad = false;
      }
    };
    viewerImage.src = url;
  }

  function openVideoViewer(item, index) {
    viewerImage.removeAttribute("src");
    viewerImage.hidden = true;
    resetViewerVideo();
    viewerIndex = index;
    viewer.hidden = false;
    viewerVideo.hidden = false;
    viewerVideo.poster = "/api/media/" + encodeURIComponent(item.id) + "?which=poster";
  }

  function openViewerAt(index) {
    if (index < 0 || index >= items.length) {
      return;
    }
    const item = items[index];
    if (item.kind === "video") {
      openVideoViewer(item, index);
      return;
    }
    openStillViewer(item, index);
  }

  function openViewer(id) {
    const index = items.findIndex(function (item) {
      return item.id === id;
    });
    if (index < 0) {
      return;
    }
    savedScroll = main.scrollTop;
    savedLevel = settings.zoomLevel;
    openViewerAt(index);
  }

  function visibleAnchorId() {
    if (hoveredId && main.querySelector('.cell[data-id="' + hoveredId + '"]')) {
      return hoveredId;
    }
    const bounds = main.getBoundingClientRect();
    const midY = bounds.top + bounds.height / 2;
    const cells = main.querySelectorAll(".cell");
    let best = null;
    let bestDist = Infinity;
    cells.forEach(function (cell) {
      const rect = cell.getBoundingClientRect();
      const center = rect.top + rect.height / 2;
      const dist = Math.abs(center - midY);
      if (rect.bottom > bounds.top && rect.top < bounds.bottom && dist < bestDist) {
        bestDist = dist;
        best = cell.dataset.id;
      }
    });
    return best || (items[0] && items[0].id) || null;
  }

  function scrollIdIntoView(id) {
    if (!id) {
      return;
    }
    const cell = main.querySelector('.cell[data-id="' + id + '"]');
    if (cell) {
      cell.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }

  function makeCell(item) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "cell";
    cell.dataset.id = item.id;
    cell.dataset.filename = item.filename || "";
    cell.dataset.kind = item.kind || "";
    const placeholder = document.createElement("span");
    placeholder.className = "placeholder";
    placeholder.textContent = PLACEHOLDER;
    const img = document.createElement("img");
    img.alt = "";
    img.hidden = true;
    cell.appendChild(placeholder);
    cell.appendChild(img);
    cell.addEventListener("mouseenter", function () {
      hoveredId = item.id;
      startHover(cell, item);
    });
    cell.addEventListener("mouseleave", function () {
      if (hoveredId === item.id) {
        hoveredId = null;
      }
      stopHover();
    });
    cell.addEventListener("click", function () {
      openViewer(item.id);
    });
    requestStill(cell, item.id);
    return cell;
  }

  function itemById(id) {
    for (let i = 0; i < items.length; i += 1) {
      if (items[i].id === id) {
        return items[i];
      }
    }
    return { id: id, filename: "" };
  }

  function render() {
    const level = settings.zoomLevel;
    main.dataset.level = level;
    main.className = "level-" + level;
    zoomSlider.value = String(levelIndex(level));
    sortSelect.value = settings.sort;
    dirSelect.value = settings.dir;
    if (!items.length) {
      main.innerHTML = "<p>" + EMPTY + "</p>";
      renderKey = "empty";
      return;
    }
    const key = level + "|" + settings.sort + "|" + settings.dir + "|" + groups.map(function (group) {
      return group.key + ":" + (group.itemIds || []).join(",");
    }).join(";");
    if (key === renderKey) {
      main.querySelectorAll(".cell").forEach(function (cell) {
        requestStill(cell, cell.dataset.id);
      });
      return;
    }
    const anchor = visibleAnchorId();
    const fragment = document.createDocumentFragment();
    const mosaic = level === "years" || level === "months";
    groups.forEach(function (group) {
      const section = document.createElement("section");
      section.className = "group";
      section.dataset.key = group.key;
      const heading = document.createElement("h2");
      heading.className = "group-key";
      heading.textContent = group.key;
      section.appendChild(heading);
      const list = document.createElement("div");
      list.className = mosaic ? "mosaic" : "item-list";
      (group.itemIds || []).forEach(function (id) {
        list.appendChild(makeCell(itemById(id)));
      });
      section.appendChild(list);
      fragment.appendChild(section);
    });
    main.innerHTML = "";
    main.appendChild(fragment);
    renderKey = key;
    if (anchor) {
      scrollIdIntoView(anchor);
    }
  }

  function loadCatalog() {
    const gen = loadGen + 1;
    loadGen = gen;
    const qs = queryString();
    return Promise.all([
      fetch("/api/items?" + qs).then(readJson),
      fetch("/api/groups?" + queryString({ level: settings.zoomLevel })).then(readJson),
      fetch("/api/sources").then(readJson),
      fetch("/api/settings").then(readJson),
    ]).then(function (parts) {
      if (gen !== loadGen) {
        return;
      }
      const nextItems = Array.isArray(parts[0]) ? parts[0] : [];
      const nextGroups = Array.isArray(parts[1]) ? parts[1] : [];
      const sources = Array.isArray(parts[2]) ? parts[2] : [];
      applySettings(parts[3]);
      const status = sourcesStatus(sources);
      scanning = status.running;
      if (sources.length) {
        showStatus(status.text, true);
      } else {
        showStatus("", false);
      }
      items = nextItems;
      groups = nextGroups;
      render();
    });
  }

  function setLevel(level, persistChange) {
    if (LEVELS.indexOf(level) === -1 || level === settings.zoomLevel) {
      return Promise.resolve();
    }
    const anchor = visibleAnchorId();
    settings.zoomLevel = level;
    zoomSlider.value = String(levelIndex(level));
    const done = persistChange ? persist({ zoomLevel: level }) : Promise.resolve();
    return done.then(function () {
      renderKey = "";
      return loadCatalog();
    }).then(function () {
      scrollIdIntoView(anchor || hoveredId);
    });
  }

  function stepLevel(delta) {
    const next = Math.max(0, Math.min(LEVELS.length - 1, levelIndex(settings.zoomLevel) + delta));
    return setLevel(LEVELS[next], true);
  }

  function handleGridWheel(event) {
    if (levelWheelLock) {
      return;
    }
    levelWheelLock = true;
    window.setTimeout(function () {
      levelWheelLock = false;
    }, 80);
    stepLevel(event.deltaY < 0 ? 1 : -1);
  }

  function handleViewerZoom(event) {
    if (!naturalW || viewer.hidden) {
      return;
    }
    fitOnLoad = false;
    const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    const next = Math.min(fitScale * 16, Math.max(fitScale, scale * factor));
    if (next === scale) {
      return;
    }
    const cx = event.clientX;
    const cy = event.clientY;
    const ix = (cx - tx) / scale;
    const iy = (cy - ty) / scale;
    scale = next;
    tx = cx - ix * scale;
    ty = cy - iy * scale;
    applyTransform();
  }

  function textFocused() {
    const node = document.activeElement;
    if (!node) {
      return false;
    }
    const tag = (node.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || node.isContentEditable;
  }

  function submitAdd() {
    const path = addPath.value.trim();
    const mode = selectedMode();
    if (!path || !mode) {
      return;
    }
    addError.hidden = true;
    fetch("/api/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, mode: mode }),
    }).then(readJson).then(function () {
      closeAddDialog();
      renderKey = "";
      return loadCatalog();
    }).catch(function (err) {
      addError.hidden = false;
      addError.textContent = (err && err.body && err.body.error) || "invalid-argument";
    });
  }

  addFolderBtn.addEventListener("click", openAddDialog);
  addCancel.addEventListener("click", closeAddDialog);
  addSubmit.addEventListener("click", submitAdd);
  addPath.addEventListener("input", syncAddEnabled);
  addDialog.querySelectorAll('input[name="add-mode"]').forEach(function (node) {
    node.addEventListener("change", syncAddEnabled);
  });
  addDialog.addEventListener("close", function () {
    addFolderBtn.focus();
  });
  addDialog.addEventListener("cancel", function () {
    addError.hidden = true;
  });

  sortSelect.addEventListener("change", function () {
    settings.sort = sortSelect.value;
    persist({ sort: settings.sort }).then(function () {
      renderKey = "";
      return loadCatalog();
    });
  });
  dirSelect.addEventListener("change", function () {
    settings.dir = dirSelect.value;
    persist({ dir: settings.dir }).then(function () {
      renderKey = "";
      return loadCatalog();
    });
  });
  zoomSlider.addEventListener("input", function () {
    const level = LEVELS[Number(zoomSlider.value)] || "years";
    setLevel(level, true);
  });

  window.addEventListener("wheel", function (event) {
    if (!event.ctrlKey) {
      return;
    }
    event.preventDefault();
    if (!viewer.hidden) {
      handleViewerZoom(event);
      return;
    }
    handleGridWheel(event);
  }, { passive: false });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      if (addDialog.open) {
        return;
      }
      if (!viewer.hidden) {
        if (settings.zoomLevel !== savedLevel) {
          setLevel(savedLevel, true).then(closeViewer);
        } else {
          closeViewer();
        }
      }
      return;
    }
    if (textFocused() || viewer.hidden) {
      return;
    }
    if (event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      toggleViewerPlay();
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (viewerIndex > 0) {
        openViewerAt(viewerIndex - 1);
      }
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      if (viewerIndex >= 0 && viewerIndex < items.length - 1) {
        openViewerAt(viewerIndex + 1);
      }
    }
  });

  document.addEventListener("mousedown", function (event) {
    if (event.button === 1) {
      event.preventDefault();
    }
  }, true);

  viewer.addEventListener("mousedown", function (event) {
    if (event.button !== 1 || viewer.hidden) {
      return;
    }
    event.preventDefault();
    fitOnLoad = false;
    panning = true;
    panLastX = event.clientX;
    panLastY = event.clientY;
  });
  window.addEventListener("mousemove", function (event) {
    if (!panning || viewer.hidden) {
      return;
    }
    event.preventDefault();
    tx += event.clientX - panLastX;
    ty += event.clientY - panLastY;
    panLastX = event.clientX;
    panLastY = event.clientY;
    applyTransform();
  });
  window.addEventListener("mouseup", function (event) {
    if (event.button === 1) {
      panning = false;
    }
  });
  viewer.addEventListener("auxclick", function (event) {
    if (event.button === 1) {
      event.preventDefault();
    }
  });
  viewerVideo.addEventListener("click", function (event) {
    event.preventDefault();
    toggleViewerPlay();
  });

  fetch("/api/settings").then(readJson).then(function (data) {
    applySettings(data);
    sortSelect.value = settings.sort;
    dirSelect.value = settings.dir;
    zoomSlider.value = String(levelIndex(settings.zoomLevel));
    return loadCatalog();
  }).catch(function () {
    return loadCatalog();
  });

  pollTimer = window.setInterval(function () {
    loadCatalog();
  }, 1000);
  window.addEventListener("beforeunload", function () {
    window.clearInterval(pollTimer);
  });
})();
