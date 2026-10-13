(function () {
  const main = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
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
  if (!main || !viewer || !viewerImage || !addFolderBtn || !addDialog) {
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
      settings.sort = next.sort;
      settings.dir = next.dir;
      settings.zoomLevel = next.zoomLevel;
      settings.addFolderDefault = next.addFolderDefault;
      return next;
    });
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

  function requestThumb(cell, id) {
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    const url = "/api/media/" + encodeURIComponent(id) + "?which=thumb";
    if (img.getAttribute("data-thumb") === url && !img.hidden && img.complete && img.naturalWidth > 0) {
      return;
    }
    const item = itemById(id);
    const thumbStatus = ((item.renditions || {}).status || {}).thumb;
    if (thumbStatus !== "ready") {
      window.setTimeout(function () {
        requestThumb(cell, id);
      }, 1000);
      return;
    }
    fetch(url).then(function (res) {
      if (!res.ok) {
        placeholder.hidden = false;
        img.hidden = true;
        window.setTimeout(function () {
          requestThumb(cell, id);
        }, 1000);
        return;
      }
      img.onload = function () {
        placeholder.hidden = true;
        img.hidden = false;
      };
      img.onerror = function () {
        img.hidden = true;
        placeholder.hidden = false;
        window.setTimeout(function () {
          requestThumb(cell, id);
        }, 1000);
      };
      img.setAttribute("data-thumb", url);
      img.src = url;
    }).catch(function () {
      window.setTimeout(function () {
        requestThumb(cell, id);
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

  function closeViewer() {
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
    viewerIndex = -1;
    panning = false;
    window.requestAnimationFrame(function () {
      main.scrollTop = savedScroll;
    });
  }

  function openViewerAt(index) {
    if (index < 0 || index >= items.length) {
      return;
    }
    const item = items[index];
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
    });
    cell.addEventListener("click", function () {
      openViewer(item.id);
    });
    requestThumb(cell, item.id);
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
        requestThumb(cell, cell.dataset.id);
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
    ]).then(function (parts) {
      if (gen !== loadGen) {
        return;
      }
      const nextItems = Array.isArray(parts[0]) ? parts[0] : [];
      const nextGroups = Array.isArray(parts[1]) ? parts[1] : [];
      const sources = Array.isArray(parts[2]) ? parts[2] : [];
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

  fetch("/api/settings").then(readJson).then(function (data) {
    settings.sort = data.sort || settings.sort;
    settings.dir = data.dir || settings.dir;
    settings.zoomLevel = data.zoomLevel || settings.zoomLevel;
    settings.addFolderDefault = data.addFolderDefault || settings.addFolderDefault;
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
