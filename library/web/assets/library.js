(function () {
  const LEVELS = ["years", "months", "days", "all"];
  const empty = document.getElementById("empty");
  const grid = document.getElementById("grid");
  const main = document.getElementById("library-main");
  const statusEl = document.getElementById("status");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  const addButton = document.getElementById("add-folder");
  const addDialog = document.getElementById("add-dialog");
  const addPath = document.getElementById("add-path");
  const addError = document.getElementById("add-error");
  const addCancel = document.getElementById("add-cancel");
  const addSubmit = document.getElementById("add-submit");
  const sortSelect = document.getElementById("sort");
  const dirSelect = document.getElementById("dir");
  const zoomSlider = document.getElementById("zoom-slider");

  let sort = "date";
  let dir = "desc";
  let zoomLevel = "years";
  let addFolderDefault = "ask";
  let items = [];
  let groups = [];
  let fingerprint = "";
  let viewerId = null;
  let savedView = null;
  let fitScale = 1;
  let viewScale = 1;
  let panX = 0;
  let panY = 0;
  let panning = false;
  let panLast = { x: 0, y: 0 };
  let gridWheelBurst = false;
  let gridWheelTimer = null;

  function thumbUrl(id) {
    return "/api/media/" + encodeURIComponent(id) + "?which=thumb";
  }

  function previewUrl(id) {
    return "/api/media/" + encodeURIComponent(id) + "?which=preview";
  }

  function queryString() {
    return "sort=" + encodeURIComponent(sort) + "&dir=" + encodeURIComponent(dir);
  }

  function itemsById() {
    const map = {};
    items.forEach(function (item) {
      map[item.id] = item;
    });
    return map;
  }

  function locationLabel(item) {
    const places = (item.entities && item.entities.places) || [];
    const place = places[0];
    if (place && place.name) {
      return place.name;
    }
    if (place && place.latitude != null && place.longitude != null) {
      return Number(place.latitude).toFixed(2) + "," + Number(place.longitude).toFixed(2);
    }
    return "No location";
  }

  function thumbReady(item) {
    const rend = item.renditions || {};
    const status = rend.status || {};
    return status.thumb === "ready" && !!rend.thumb;
  }

  function previewReady(item) {
    const rend = item.renditions || {};
    const status = rend.status || {};
    return status.preview === "ready" && !!rend.preview;
  }

  function makeCell(item) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "cell";
    el.dataset.id = item.id;
    el.dataset.filename = item.filename || "";
    el.dataset.locationLabel = locationLabel(item);
    const label = document.createElement("span");
    label.className = "placeholder";
    label.textContent = "Preview is not available";
    const img = document.createElement("img");
    img.alt = "";
    img.hidden = true;
    img.addEventListener("load", function () {
      if (img.naturalWidth > 0) {
        img.hidden = false;
        label.hidden = true;
      }
    });
    img.addEventListener("error", function () {
      img.removeAttribute("src");
      img.hidden = true;
      label.hidden = false;
    });
    el.append(label, img);
    el.addEventListener("click", function () {
      openViewer(item.id);
    });
    updateThumb(el, item);
    return el;
  }

  function updateThumb(cell, item) {
    const img = cell.querySelector("img");
    if (!img) {
      return;
    }
    if (!thumbReady(item)) {
      img.removeAttribute("src");
      img.hidden = true;
      const label = cell.querySelector(".placeholder");
      if (label) {
        label.hidden = false;
      }
      return;
    }
    if (img.complete && img.naturalWidth > 0 && img.getAttribute("src")) {
      return;
    }
    img.src = thumbUrl(item.id);
  }

  function applyViewerTransform() {
    viewerImage.style.transform = "translate(" + panX + "px, " + panY + "px) scale(" + viewScale + ")";
  }

  function resetFit() {
    const vw = viewer.clientWidth;
    const vh = viewer.clientHeight;
    const iw = viewerImage.naturalWidth;
    const ih = viewerImage.naturalHeight;
    if (!iw || !ih || vw <= 0 || vh <= 0) {
      return;
    }
    viewerImage.style.width = iw + "px";
    viewerImage.style.height = ih + "px";
    fitScale = Math.min(vw / iw, vh / ih);
    viewScale = fitScale;
    panX = (vw - iw * viewScale) / 2;
    panY = (vh - ih * viewScale) / 2;
    applyViewerTransform();
  }

  function openViewer(id) {
    if (viewer.hidden) {
      savedView = {
        scrollTop: main.scrollTop,
        scrollLeft: main.scrollLeft,
        zoomLevel: zoomLevel,
      };
    }
    viewerId = id;
    const item = itemsById()[id];
    viewerImage.removeAttribute("src");
    panX = 0;
    panY = 0;
    viewScale = 1;
    applyViewerTransform();
    if (item && previewReady(item)) {
      viewerImage.src = previewUrl(id);
    }
    viewer.hidden = false;
  }

  function closeViewer() {
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
    const restore = savedView;
    viewerId = null;
    savedView = null;
    panning = false;
    if (!restore) {
      return;
    }
    function applyScroll() {
      main.scrollTop = restore.scrollTop;
      main.scrollLeft = restore.scrollLeft;
    }
    if (zoomLevel !== restore.zoomLevel) {
      zoomLevel = restore.zoomLevel;
      zoomSlider.value = String(LEVELS.indexOf(zoomLevel));
      document.body.dataset.zoomLevel = zoomLevel;
      loadGrid().then(applyScroll);
    } else {
      applyScroll();
    }
  }

  function viewerIndex() {
    return items.findIndex(function (item) {
      return item.id === viewerId;
    });
  }

  function stepViewer(delta) {
    const index = viewerIndex();
    if (index < 0) {
      return;
    }
    const next = index + delta;
    if (next < 0 || next >= items.length) {
      return;
    }
    openViewer(items[next].id);
  }

  function zoomViewer(event) {
    if (!viewerImage.naturalWidth) {
      return;
    }
    const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    const minScale = fitScale;
    const maxScale = fitScale * 16;
    const next = Math.min(maxScale, Math.max(minScale, viewScale * factor));
    if (next === viewScale) {
      return;
    }
    const rect = viewer.getBoundingClientRect();
    const cx = event.clientX - rect.left;
    const cy = event.clientY - rect.top;
    const imgX = (cx - panX) / viewScale;
    const imgY = (cy - panY) / viewScale;
    viewScale = next;
    panX = cx - imgX * viewScale;
    panY = cy - imgY * viewScale;
    applyViewerTransform();
  }

  function renderGrid() {
    const hasItems = items.length > 0;
    empty.hidden = hasItems;
    grid.hidden = !hasItems;
    grid.dataset.level = zoomLevel;
    grid.innerHTML = "";
    const byId = itemsById();
    groups.forEach(function (group) {
      const section = document.createElement("section");
      section.className = "group " + zoomLevel;
      section.dataset.key = group.key;
      const heading = document.createElement("h2");
      heading.className = "group-title";
      heading.textContent = group.key;
      section.appendChild(heading);
      const row = document.createElement("div");
      row.className = zoomLevel === "years" || zoomLevel === "months" ? "mosaic" : "row";
      (group.itemIds || []).forEach(function (id) {
        const item = byId[id];
        if (!item) {
          return;
        }
        row.appendChild(makeCell(item));
      });
      section.appendChild(row);
      grid.appendChild(section);
    });
  }

  function updateThumbsOnly() {
    const byId = itemsById();
    Array.from(grid.querySelectorAll(".cell")).forEach(function (cell) {
      const item = byId[cell.dataset.id];
      if (item) {
        updateThumb(cell, item);
      }
    });
  }

  function groupFingerprint() {
    return zoomLevel + "|" + sort + "|" + dir + "|" + groups.map(function (group) {
      return group.key + ":" + (group.itemIds || []).join(",");
    }).join(";");
  }

  function itemUnderPoint(x, y) {
    const el = document.elementFromPoint(x, y);
    const cell = el && el.closest ? el.closest("[data-id]") : null;
    return cell ? cell.dataset.id : null;
  }

  function centralVisibleItem() {
    const rect = main.getBoundingClientRect();
    const id = itemUnderPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    if (id) {
      return id;
    }
    const midY = main.scrollTop + main.clientHeight / 2;
    let best = null;
    let bestDist = Infinity;
    Array.from(grid.querySelectorAll("[data-id]")).forEach(function (cell) {
      const top = cell.offsetTop;
      const dist = Math.abs(top + cell.offsetHeight / 2 - midY);
      if (dist < bestDist) {
        bestDist = dist;
        best = cell.dataset.id;
      }
    });
    return best;
  }

  function scrollItemIntoView(id) {
    if (!id) {
      return;
    }
    const cell = grid.querySelector('[data-id="' + id + '"]');
    if (cell) {
      cell.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }

  async function putSettings(patch) {
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
    } catch (err) {
      return;
    }
  }

  async function loadGrid(anchorId, anchorClient) {
    try {
      const level = zoomLevel;
      const sortNow = sort;
      const dirNow = dir;
      const qs = "sort=" + encodeURIComponent(sortNow) + "&dir=" + encodeURIComponent(dirNow);
      const itemsResp = await fetch("/api/items?" + qs);
      const groupsResp = await fetch("/api/groups?level=" + encodeURIComponent(level) + "&" + qs);
      if (!itemsResp.ok || !groupsResp.ok) {
        return;
      }
      const nextItems = await itemsResp.json();
      const nextGroups = await groupsResp.json();
      if (!Array.isArray(nextItems) || !Array.isArray(nextGroups)) {
        return;
      }
      if (level !== zoomLevel || sortNow !== sort || dirNow !== dir) {
        return;
      }
      items = nextItems;
      groups = nextGroups;
      document.body.dataset.sort = sort;
      document.body.dataset.dir = dir;
      document.body.dataset.zoomLevel = zoomLevel;
      if (!viewer.hidden) {
        return;
      }
      const nextPrint = groupFingerprint();
      if (nextPrint === fingerprint) {
        updateThumbsOnly();
        return;
      }
      fingerprint = nextPrint;
      renderGrid();
      if (anchorId) {
        scrollItemIntoView(anchorId);
        if (anchorClient) {
          const cell = grid.querySelector('[data-id="' + anchorId + '"]');
          if (cell) {
            const rect = cell.getBoundingClientRect();
            main.scrollTop += rect.top + rect.height / 2 - anchorClient.y;
            main.scrollLeft += rect.left + rect.width / 2 - anchorClient.x;
          }
        }
      }
    } catch (err) {
      return;
    }
  }

  function selectedMode() {
    const checked = addDialog.querySelector('input[name="add-mode"]:checked');
    return checked ? checked.value : "";
  }

  function syncAddEnabled() {
    addSubmit.disabled = !(addPath.value.trim() && selectedMode());
  }

  function closeAddDialog() {
    if (addDialog.open) {
      addDialog.close();
    }
    addError.hidden = true;
    addError.textContent = "";
    addButton.focus();
  }

  function resetAddDialog() {
    addPath.value = "";
    addError.hidden = true;
    addError.textContent = "";
    addDialog.querySelectorAll('input[name="add-mode"]').forEach(function (input) {
      input.checked = false;
    });
    if (addFolderDefault === "copy-here" || addFolderDefault === "serve-from-there") {
      const preset = addDialog.querySelector('input[name="add-mode"][value="' + addFolderDefault + '"]');
      if (preset) {
        preset.checked = true;
      }
    }
    syncAddEnabled();
  }

  function openAddDialog() {
    resetAddDialog();
    addDialog.showModal();
    addPath.focus();
  }

  function showStatus(source) {
    const scan = source && source.scan ? source.scan : {};
    const added = scan.added == null ? 0 : scan.added;
    const skipped = scan.skipped == null ? 0 : scan.skipped;
    const errors = Array.isArray(scan.errors) ? scan.errors.length : 0;
    statusEl.textContent = "added " + added + ", skipped " + skipped + ", errors " + errors;
    statusEl.hidden = false;
  }

  async function submitAdd() {
    const path = addPath.value.trim();
    const mode = selectedMode();
    if (!path || !mode) {
      return;
    }
    addSubmit.disabled = true;
    addError.hidden = true;
    try {
      const resp = await fetch("/api/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, mode: mode }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        addError.textContent = data && data.error ? data.error : "not-found";
        addError.hidden = false;
        syncAddEnabled();
        return;
      }
      closeAddDialog();
      showStatus(data);
      fingerprint = "";
      await loadGrid();
    } catch (err) {
      addError.textContent = "not-found";
      addError.hidden = false;
      syncAddEnabled();
    }
  }

  function stepZoom(deltaY, clientX, clientY) {
    const index = LEVELS.indexOf(zoomLevel);
    const nextIndex = deltaY < 0
      ? Math.min(LEVELS.length - 1, index + 1)
      : Math.max(0, index - 1);
    if (nextIndex === index) {
      return;
    }
    const anchorId = itemUnderPoint(clientX, clientY) || centralVisibleItem();
    zoomLevel = LEVELS[nextIndex];
    zoomSlider.value = String(nextIndex);
    document.body.dataset.zoomLevel = zoomLevel;
    putSettings({ zoomLevel: zoomLevel });
    loadGrid(anchorId, { x: clientX, y: clientY });
  }

  function onGridWheel(event) {
    if (!event.ctrlKey) {
      return;
    }
    event.preventDefault();
    if (!viewer.hidden) {
      return;
    }
    if (gridWheelBurst) {
      clearTimeout(gridWheelTimer);
      gridWheelTimer = setTimeout(function () {
        gridWheelBurst = false;
      }, 80);
      return;
    }
    gridWheelBurst = true;
    clearTimeout(gridWheelTimer);
    gridWheelTimer = setTimeout(function () {
      gridWheelBurst = false;
    }, 80);
    stepZoom(event.deltaY, event.clientX, event.clientY);
  }

  viewerImage.addEventListener("load", function () {
    if (viewerImage.naturalWidth > 0) {
      resetFit();
    }
  });

  viewer.addEventListener("wheel", function (event) {
    if (!event.ctrlKey || viewer.hidden) {
      return;
    }
    event.preventDefault();
    zoomViewer(event);
  }, { passive: false });

  viewer.addEventListener("mousedown", function (event) {
    if (event.button !== 1 || viewer.hidden) {
      return;
    }
    event.preventDefault();
    panning = true;
    panLast = { x: event.clientX, y: event.clientY };
  });

  window.addEventListener("mousemove", function (event) {
    if (!panning) {
      return;
    }
    panX += event.clientX - panLast.x;
    panY += event.clientY - panLast.y;
    panLast = { x: event.clientX, y: event.clientY };
    applyViewerTransform();
  });

  window.addEventListener("mouseup", function () {
    panning = false;
  });

  viewer.addEventListener("auxclick", function (event) {
    if (event.button === 1) {
      event.preventDefault();
    }
  });

  document.addEventListener("wheel", onGridWheel, { passive: false });

  document.addEventListener("keydown", function (event) {
    const typing = event.target && event.target.closest && event.target.closest("input, textarea, select");
    if (addDialog.open) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeAddDialog();
      }
      return;
    }
    if (typing) {
      return;
    }
    if (viewer.hidden) {
      if (event.key === "Escape") {
        return;
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeViewer();
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepViewer(-1);
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      stepViewer(1);
    }
  });

  addButton.addEventListener("click", openAddDialog);
  addCancel.addEventListener("click", closeAddDialog);
  addSubmit.addEventListener("click", submitAdd);
  addPath.addEventListener("input", syncAddEnabled);
  addDialog.querySelectorAll('input[name="add-mode"]').forEach(function (input) {
    input.addEventListener("change", syncAddEnabled);
  });
  addDialog.addEventListener("cancel", function (event) {
    event.preventDefault();
    closeAddDialog();
  });

  sortSelect.addEventListener("change", function () {
    sort = sortSelect.value;
    document.body.dataset.sort = sort;
    putSettings({ sort: sort, dir: dir });
    fingerprint = "";
    loadGrid();
  });
  dirSelect.addEventListener("change", function () {
    dir = dirSelect.value;
    document.body.dataset.dir = dir;
    putSettings({ sort: sort, dir: dir });
    fingerprint = "";
    loadGrid();
  });
  zoomSlider.addEventListener("input", function () {
    const next = LEVELS[Number(zoomSlider.value)] || "years";
    if (next === zoomLevel) {
      return;
    }
    const rect = main.getBoundingClientRect();
    const anchorId = centralVisibleItem();
    zoomLevel = next;
    document.body.dataset.zoomLevel = zoomLevel;
    putSettings({ zoomLevel: zoomLevel });
    loadGrid(anchorId, { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  });

  async function boot() {
    try {
      const resp = await fetch("/api/settings");
      if (resp.ok) {
        const settings = await resp.json();
        if (settings.sort === "date" || settings.sort === "location" || settings.sort === "name") {
          sort = settings.sort;
        }
        if (settings.dir === "asc" || settings.dir === "desc") {
          dir = settings.dir;
        }
        if (LEVELS.indexOf(settings.zoomLevel) >= 0) {
          zoomLevel = settings.zoomLevel;
        }
        if (typeof settings.addFolderDefault === "string") {
          addFolderDefault = settings.addFolderDefault;
        }
      }
    } catch (err) {
      return;
    }
    sortSelect.value = sort;
    dirSelect.value = dir;
    zoomSlider.value = String(LEVELS.indexOf(zoomLevel));
    document.body.dataset.sort = sort;
    document.body.dataset.dir = dir;
    document.body.dataset.zoomLevel = zoomLevel;
    await loadGrid();
  }

  boot();
  setInterval(function () {
    loadGrid();
  }, 1000);
})();
