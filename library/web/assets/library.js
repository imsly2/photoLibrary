(function () {
  const main = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  const viewerOriginal = document.getElementById("viewer-original");
  const viewerVideo = document.getElementById("viewer-video");
  const viewerBack = document.getElementById("viewer-back");
  const viewerCrumb = document.getElementById("viewer-crumb");
  const viewerPrev = document.getElementById("viewer-prev");
  const viewerNext = document.getElementById("viewer-next");
  const viewerZoomSlider = document.getElementById("viewer-zoom-slider");
  const viewerRotate = document.getElementById("viewer-rotate");
  const viewerFavorite = document.getElementById("viewer-favorite");
  const viewerSlideshow = document.getElementById("viewer-slideshow");
  const viewerFullscreen = document.getElementById("viewer-fullscreen");
  const viewerInfo = document.getElementById("viewer-info");
  const viewerInfoPanel = document.getElementById("viewer-info-panel");
  const viewerFacts = document.getElementById("viewer-facts");
  const slideshowEmpty = document.getElementById("slideshow-empty");
  const unavailableBanner = document.getElementById("unavailable-banner");
  const disconnectedBanner = document.getElementById("disconnected-banner");
  const reconnectRetry = document.getElementById("reconnect-retry");
  const addBrowse = document.getElementById("add-browse");
  const viewerPlaceholder = document.getElementById("viewer-placeholder");
  const revealOriginalBtn = document.getElementById("reveal-original");
  const openOriginalBtn = document.getElementById("open-original");
  const revealError = document.getElementById("reveal-error");
  const playPreviewBtn = document.getElementById("play-preview");
  const viewerScrubWrap = document.getElementById("viewer-scrub-wrap");
  const viewerScrub = document.getElementById("viewer-scrub");
  const viewerScrubTime = document.getElementById("viewer-scrub-time");
  const updateLibraryBtn = document.getElementById("update-library");
  const updateStatus = document.getElementById("update-status");
  const libraryVersion = document.getElementById("library-version");
  const searchInput = document.getElementById("search");
  const searchChips = document.getElementById("search-chips");
  const inspector = document.getElementById("inspector");
  const inspectorName = document.getElementById("inspector-name");
  const inspectorCount = document.getElementById("inspector-count");
  const inspectorFiles = document.getElementById("inspector-filenames");
  const peopleLabels = document.getElementById("viewer-people");
  const placeLabels = document.getElementById("viewer-place");
  const thingsLabels = document.getElementById("viewer-things");
  const personField = document.getElementById("person-field");
  const placeField = document.getElementById("place-field");
  const thingField = document.getElementById("thing-field");
  const annotateError = document.getElementById("annotate-error");
  const addFolderBtn = document.getElementById("add-folder-btn");
  const addDialog = document.getElementById("add-folder");
  const addPath = document.getElementById("add-path");
  const addSubmit = document.getElementById("add-submit");
  const addCancel = document.getElementById("add-cancel");
  const addError = document.getElementById("add-error");
  const sortSelect = document.getElementById("sort");
  const dirSelect = document.getElementById("dir");
  const sortPresentable = document.getElementById("sort-presentable");
  const sizeSlider = document.getElementById("size-slider");
  const dateGroupSelect = document.getElementById("date-group");
  const viewerZoomPct = document.getElementById("viewer-zoom-pct");
  const filterAll = document.getElementById("filter-all");
  const filterPhotos = document.getElementById("filter-photos");
  const filterVideos = document.getElementById("filter-videos");
  const filterFavorites = document.getElementById("filter-favorites");
  const removeItemBtn = document.getElementById("remove-item");
  const deleteFileBtn = document.getElementById("delete-file");
  const scanStatus = document.getElementById("scan-status");
  const scanStatusText = document.getElementById("scan-status-text");
  const scanErrorText = document.getElementById("scan-error-text");
  const scanRetry = document.getElementById("scan-retry");
  const confirmRemove = document.getElementById("confirm-remove");
  const confirmDeleteFile = document.getElementById("confirm-delete-file");
  const viewLibrary = document.getElementById("view-library");
  const viewGlobe = document.getElementById("view-globe");
  const workspace = document.querySelector(".workspace");
  const globeView = document.getElementById("globe-view");
  if (!main || !viewer || !viewerImage || !viewerVideo || !addFolderBtn || !addDialog) {
    return;
  }
  if (!unavailableBanner || !viewerPlaceholder || !playPreviewBtn || !viewerBack) {
    return;
  }
  if (!viewerPrev || !viewerNext || !viewerZoomSlider || !viewerRotate) {
    return;
  }
  if (!viewerFavorite || !revealOriginalBtn || !openOriginalBtn || !viewerInfo || !viewerInfoPanel) {
    return;
  }
  if (!viewerSlideshow || !viewerFullscreen || !viewerFacts || !slideshowEmpty) {
    return;
  }

  const PLACEHOLDER = "Preview is not available";
  const LEVELS = ["years", "months", "days", "all"];
  const DATE_MODES = ["years", "months", "days", "off"];
  const SIZE_STEPS = [72, 104, 144, 192, 256, 336, 420, 520];
  const DEFAULT_SIZE = { years: 0, months: 1, days: 3, all: 6 };
  const HEART_MIN = 144;
  const EMPTY = "No pictures yet";
  const EMPTY_SEARCH = "No matches";
  const PLAY_ICON = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 2.1v7.8L10.2 6z"/></svg>';
  const HEART_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.4S2.6 10 1.5 7.1C.6 5.1 1.6 3 3.8 3c1.2 0 2 .7 2.3 1.2C6.4 3.7 7.2 3 8.4 3c2.2 0 3.2 2.1 2.3 4.1C9.6 10 8 13.4 8 13.4z"/></svg>';
  const SLIDESHOW_EMPTY = "Add photos first";
  const NO_CAMERA_INFO = "No camera info for this file.";
  const SLIDESHOW_MS = 5000;

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
  let viewerItemId = null;
  let savedScroll = 0;
  let savedLevel = "years";
  let savedFilter = { q: "", scope: "", person: "", place: "", thing: "", kind: "", favorite: "" };
  let savedSearch = "";
  let filter = { q: "", scope: "", person: "", place: "", thing: "", kind: "", favorite: "" };
  let selectedId = null;
  let pendingRemoveId = null;
  let lastSources = [];
  let gridSize = 0;
  let groupDates = true;
  let favoritesOpen = true;
  let searchTimer = 0;
  let annotateBusy = false;
  let pollTimer = 0;
  let scanning = false;
  let levelWheelLock = false;
  let panning = false;
  let panMoved = false;
  let panLastX = 0;
  let panLastY = 0;
  let scale = 1;
  let fitScale = 1;
  let tx = 0;
  let ty = 0;
  let naturalW = 0;
  let naturalH = 0;
  let layoutW = 0;
  let layoutH = 0;
  let rotation = 0;
  let originalPreload = null;
  let originalPreloadId = null;
  let scrubbingViewer = false;
  let showingOriginal = false;
  let fitOnLoad = false;
  const MIN_ZOOM_FACTOR = 0.25;
  const MAX_ZOOM_FACTOR = 16;
  let renderKey = "";
  let loadGen = 0;
  let currentView = "library";
  let appFullscreen = false;
  let slideshowActive = false;
  let slideshowPaused = false;
  let slideshowTimer = 0;
  let fullscreenExitRequested = false;

  function currentDateMode() {
    if (!groupDates) {
      return "off";
    }
    return settings.zoomLevel === "all" ? "days" : settings.zoomLevel;
  }

  function viewerBox() {
    const stage = document.getElementById("viewer-stage") || viewer;
    return { w: stage.clientWidth, h: stage.clientHeight };
  }

  function queryString(extra) {
    const params = new URLSearchParams();
    params.set("sort", settings.sort);
    params.set("dir", settings.dir);
    const merged = {};
    if (filter.q) {
      merged.q = filter.q;
    }
    if (filter.scope) {
      merged.scope = filter.scope;
    }
    if (filter.person) {
      merged.person = filter.person;
    }
    if (filter.place) {
      merged.place = filter.place;
    }
    if (filter.thing) {
      merged.thing = filter.thing;
    }
    if (filter.kind) {
      merged.kind = filter.kind;
    }
    if (filter.favorite) {
      merged.favorite = filter.favorite;
    }
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        merged[key] = extra[key];
      });
    }
    Object.keys(merged).forEach(function (key) {
      if (merged[key] !== "" && merged[key] != null) {
        params.set(key, merged[key]);
      }
    });
    return params.toString();
  }

  function syncViewerIndex() {
    if (!viewerItemId) {
      viewerIndex = -1;
      return null;
    }
    const idx = items.findIndex(function (item) {
      return item.id === viewerItemId;
    });
    viewerIndex = idx;
    return idx >= 0 ? items[idx] : null;
  }

  function hasActiveFilter() {
    return !!(filter.q || filter.scope || filter.person || filter.place || filter.thing || filter.kind || filter.favorite);
  }

  function emptySearchText() {
    const q = (filter.q || "").trim();
    if (q) {
      return "No matches for " + q;
    }
    return EMPTY_SEARCH;
  }

  function copyFilter(src) {
    return {
      q: src.q || "",
      scope: src.scope || "",
      person: src.person || "",
      place: src.place || "",
      thing: src.thing || "",
      kind: src.kind || "",
      favorite: src.favorite || "",
    };
  }

  function filtersEqual(a, b) {
    return a.q === b.q && a.scope === b.scope && a.person === b.person && a.place === b.place && a.thing === b.thing && a.kind === b.kind && a.favorite === b.favorite;
  }

  function syncFilterDataset() {
    main.dataset.q = filter.q;
    main.dataset.scope = filter.scope;
    main.dataset.person = filter.person;
    main.dataset.place = filter.place;
    main.dataset.thing = filter.thing;
    main.dataset.kind = filter.kind;
    main.dataset.favorite = filter.favorite;
    const allOn = !filter.kind && !filter.favorite;
    if (filterAll) {
      filterAll.setAttribute("aria-pressed", allOn ? "true" : "false");
    }
    if (filterPhotos) {
      filterPhotos.setAttribute("aria-pressed", filter.kind === "photo,live" ? "true" : "false");
    }
    if (filterVideos) {
      filterVideos.setAttribute("aria-pressed", filter.kind === "video" ? "true" : "false");
    }
    if (filterFavorites) {
      filterFavorites.setAttribute("aria-pressed", filter.favorite === "1" ? "true" : "false");
    }
  }

  function presentableSortValue() {
    if (settings.sort === "name") {
      return "name";
    }
    if (settings.sort === "location") {
      return "location";
    }
    return settings.dir === "asc" ? "oldest" : "newest";
  }

  function syncPresentableSort() {
    if (sortPresentable) {
      sortPresentable.value = presentableSortValue();
    }
    if (sortSelect) {
      sortSelect.value = settings.sort;
    }
    if (dirSelect) {
      dirSelect.value = settings.dir;
    }
  }

  function applyPresentableSort(value) {
    if (value === "oldest") {
      settings.sort = "date";
      settings.dir = "asc";
    } else if (value === "name") {
      settings.sort = "name";
      settings.dir = "asc";
    } else if (value === "location") {
      settings.sort = "location";
    } else {
      settings.sort = "date";
      settings.dir = "desc";
    }
    syncPresentableSort();
  }

  function syncSelectionChrome() {
    const id = viewerItemId || selectedId;
    const enabled = !!id;
    if (removeItemBtn) {
      removeItemBtn.disabled = !enabled;
    }
    if (deleteFileBtn) {
      deleteFileBtn.disabled = !enabled;
    }
  }

  function syncChips() {
    if (!searchChips) {
      return;
    }
    searchChips.querySelectorAll("button[data-scope]").forEach(function (btn) {
      const on = filter.scope === btn.getAttribute("data-scope");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function hideInspector() {
    if (!inspector) {
      return;
    }
    inspector.hidden = true;
    inspector.removeAttribute("data-entity-id");
    inspector.removeAttribute("data-kind");
    inspector.removeAttribute("data-count");
    if (inspectorName) {
      inspectorName.textContent = "";
    }
    if (inspectorCount) {
      inspectorCount.textContent = "";
    }
    if (inspectorFiles) {
      inspectorFiles.innerHTML = "";
    }
  }

  function showInspector(kind, id, name, matchingItems) {
    if (!inspector || !inspectorName || !inspectorCount || !inspectorFiles) {
      return;
    }
    const seen = {};
    const filenames = [];
    let count = 0;
    (matchingItems || []).forEach(function (item) {
      if (!item || !item.id || seen[item.id]) {
        return;
      }
      seen[item.id] = true;
      count += 1;
      filenames.push(item.filename || "");
    });
    inspector.hidden = false;
    inspector.dataset.entityId = id;
    inspector.dataset.kind = kind;
    inspector.dataset.count = String(count);
    inspectorName.textContent = name || "";
    inspectorCount.textContent = String(count);
    inspectorFiles.innerHTML = "";
    filenames.forEach(function (filename) {
      const li = document.createElement("li");
      li.textContent = filename;
      inspectorFiles.appendChild(li);
    });
  }

  function refreshInspectorFromItems() {
    let kind = "";
    let id = "";
    if (filter.person) {
      kind = "person";
      id = filter.person;
    } else if (filter.place) {
      kind = "place";
      id = filter.place;
    } else if (filter.thing) {
      kind = "thing";
      id = filter.thing;
    }
    if (!kind || !id) {
      hideInspector();
      return;
    }
    let name = "";
    items.forEach(function (item) {
      const entities = (item && item.entities) || {};
      const list = kind === "person" ? entities.people : kind === "place" ? entities.places : entities.things;
      (list || []).forEach(function (rec) {
        if (rec && rec.id === id && rec.name) {
          name = rec.name;
        }
      });
    });
    showInspector(kind, id, name, items);
  }

  function showView(name) {
    if (name !== "library" && name !== "globe") {
      return;
    }
    if (name === "globe" && viewer && !viewer.hidden) {
      hideViewerChrome();
    }
    currentView = name;
    document.body.dataset.view = name;
    if (workspace) {
      workspace.hidden = name !== "library";
    }
    if (globeView) {
      globeView.hidden = name !== "globe";
    }
    if (viewLibrary) {
      viewLibrary.setAttribute("aria-pressed", name === "library" ? "true" : "false");
    }
    if (viewGlobe) {
      viewGlobe.setAttribute("aria-pressed", name === "globe" ? "true" : "false");
    }
    if (window.libraryGlobe && window.libraryGlobe.setActive) {
      window.libraryGlobe.setActive(name === "globe");
    }
    if (name === "library") {
      renderKey = "";
      loadCatalog();
    }
  }

  function openCluster(placeIds) {
    const ids = (placeIds || []).filter(Boolean);
    if (!ids.length) {
      return Promise.resolve();
    }
    applyFilterState({ q: "", scope: "", person: "", place: ids.join(","), thing: "", kind: "" }, "");
    renderKey = "";
    showView("library");
    return loadCatalog().then(function () {
      const newest = items[0];
      if (newest && newest.id) {
        openViewer(newest.id);
      }
    });
  }

  function applyFilterState(next, searchValue) {
    filter = copyFilter(next);
    if (searchInput) {
      searchInput.value = searchValue != null ? searchValue : filter.q;
    }
    syncChips();
    syncFilterDataset();
    if (!(filter.person || filter.place || filter.thing)) {
      hideInspector();
    }
    if (filterVideos) {
      filterVideos.setAttribute("aria-pressed", filter.kind === "video" ? "true" : "false");
    }
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
    syncPresentableSort();
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
    hideSlideshowEmpty();
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
    if (scanStatusText) {
      scanStatusText.textContent = text;
    } else {
      scanStatus.textContent = text;
    }
  }

  function showDisconnected(on) {
    if (!disconnectedBanner) {
      return;
    }
    disconnectedBanner.hidden = !on;
    if (reconnectRetry) {
      reconnectRetry.hidden = !on;
    }
    const wrap = document.getElementById("disconnected-wrap");
    if (wrap) {
      wrap.classList.toggle("is-on", !!on);
    }
  }

  function firstScanFailure(sources) {
    let found = null;
    (sources || []).forEach(function (source) {
      if (found) {
        return;
      }
      const scan = source.scan || {};
      const errs = scan.errors || [];
      if (scan.state === "error" || errs.length) {
        const first = errs[0] || {};
        const origin = source.origin || {};
        found = {
          path: origin.lastKnownPath || first.path || "",
          error: first.error || "scan failed",
          mode: source.mode || "serve-from-there",
        };
      }
    });
    return found;
  }

  function syncScanRetry(sources) {
    const fail = firstScanFailure(sources);
    if (!scanRetry || !scanErrorText) {
      return;
    }
    if (!fail || (sources || []).some(function (source) {
      return (source.scan || {}).state === "running";
    })) {
      scanRetry.hidden = true;
      scanErrorText.hidden = true;
      scanErrorText.textContent = "";
      delete scanRetry.dataset.path;
      delete scanRetry.dataset.mode;
      return;
    }
    const bits = [];
    if (fail.path) {
      bits.push(fail.path);
    }
    if (fail.error) {
      bits.push(fail.error);
    }
    scanErrorText.textContent = bits.join(" — ");
    scanErrorText.hidden = !bits.length;
    scanRetry.hidden = false;
    scanRetry.dataset.path = fail.path || "";
    scanRetry.dataset.mode = fail.mode || "serve-from-there";
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
    if (!groupDates) {
      return true;
    }
    return level === "days" || level === "all";
  }

  let hoverVideo = null;
  let hoverCell = null;
  let lastHoverId = null;
  let lastHoverTime = 0;

  function rememberHoverTime(id, video) {
    if (!id || !video) {
      return;
    }
    const t = Number(video.currentTime);
    if (!isFinite(t) || t < 0) {
      return;
    }
    lastHoverId = id;
    lastHoverTime = t;
  }

  function hoverPreviewTime(id) {
    if (hoverVideo && hoverCell && hoverCell.dataset.id === id) {
      rememberHoverTime(id, hoverVideo);
    }
    if (lastHoverId === id && isFinite(lastHoverTime) && lastHoverTime >= 0) {
      return lastHoverTime;
    }
    return 0;
  }

  function stopHover() {
    if (hoverCell) {
      hoverCell.querySelectorAll(".tile-scrub").forEach(function (el) {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      });
    }
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
      hoverCell = null;
    }
  }

  function bindTileScrub(video, cell) {
    const scrub = document.createElement("input");
    scrub.type = "range";
    scrub.className = "tile-scrub";
    scrub.min = "0";
    scrub.max = "1000";
    scrub.value = "0";
    scrub.setAttribute("aria-label", "Preview position");
    function stopOpen(event) {
      event.stopPropagation();
    }
    ["click", "mousedown", "pointerdown", "mouseup", "pointerup", "touchstart"].forEach(function (name) {
      scrub.addEventListener(name, stopOpen);
    });
    scrub.addEventListener("input", function (event) {
      event.stopPropagation();
      if (!video.duration) {
        return;
      }
      video.currentTime = (Number(scrub.value) / 1000) * video.duration;
      rememberHoverTime(cell && cell.dataset.id, video);
    });
    video.addEventListener("timeupdate", function () {
      const id = cell && cell.dataset.id;
      rememberHoverTime(id, video);
      if (!video.duration || document.activeElement === scrub) {
        return;
      }
      scrub.value = String(Math.round((video.currentTime / video.duration) * 1000));
    });
    cell.appendChild(scrub);
  }

  function startHover(cell, item) {
    stopHover();
    if (!hoverAllowed() || !item || (item.kind !== "video" && item.kind !== "live")) {
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
    video.setAttribute("autoplay", "");
    video.src = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    cell.appendChild(video);
    bindTileScrub(video, cell);
    hoverVideo = video;
    hoverCell = cell;
    lastHoverId = item.id;
    lastHoverTime = 0;
    const play = video.play();
    if (play && play.catch) {
      play.catch(function () {});
    }
  }

  function rearmHover() {
    if (!hoveredId) {
      return;
    }
    const cell = main.querySelector('.cell[data-slot="grid"][data-id="' + hoveredId + '"]')
      || main.querySelector('.cell[data-id="' + hoveredId + '"]');
    if (!cell) {
      return;
    }
    startHover(cell, itemById(hoveredId));
  }

  function requestStill(cell, id) {
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    const item = itemById(id);
    const which = stillWhich(item);
    const url = "/api/media/" + encodeURIComponent(id) + "?which=" + which;
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
        img.hidden = false;
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

  function mediaTransform() {
    let transform = "translate(" + tx + "px, " + ty + "px) scale(" + scale + ")";
    if (rotation) {
      const cx = naturalW / 2;
      const cy = naturalH / 2;
      transform += " translate(" + cx + "px, " + cy + "px) rotate(" + rotation + "deg) translate(" + (-cx) + "px, " + (-cy) + "px)";
    }
    return transform;
  }

  function applyMediaBox(el) {
    if (!el) {
      return;
    }
    el.style.transformOrigin = "0 0";
    el.style.transform = mediaTransform();
    if (naturalW && naturalH) {
      el.style.width = naturalW + "px";
      el.style.height = naturalH + "px";
    }
  }

  function applyTransform() {
    applyMediaBox(viewerImage);
    applyMediaBox(viewerOriginal);
    applyMediaBox(viewerVideo);
  }

  function fitViewer() {
    const box = viewerBox();
    const sw = box.w;
    const sh = box.h;
    if (!naturalW || !naturalH || !sw || !sh) {
      return;
    }
    const oriented = rotation % 180 === 0;
    const boxW = oriented ? naturalW : naturalH;
    const boxH = oriented ? naturalH : naturalW;
    fitScale = Math.min(sw / boxW, sh / boxH);
    if (!isFinite(fitScale) || fitScale <= 0) {
      fitScale = 1;
    }
    scale = fitScale;
    tx = (sw - naturalW * scale) / 2;
    ty = (sh - naturalH * scale) / 2;
    applyTransform();
    syncZoomChrome();
  }

  function itemPixelSize(item) {
    const meta = (item && item.metadata) || {};
    const w = Number(meta.width) || 0;
    const h = Number(meta.height) || 0;
    if (w > 0 && h > 0) {
      return { w: w, h: h };
    }
    return null;
  }

  function adoptMediaSize(item, el) {
    const meta = itemPixelSize(item);
    if (meta) {
      naturalW = meta.w;
      naturalH = meta.h;
      return true;
    }
    if (el && el.videoWidth > 0 && el.videoHeight > 0) {
      naturalW = el.videoWidth;
      naturalH = el.videoHeight;
      return true;
    }
    if (el && el.naturalWidth > 0 && el.naturalHeight > 0) {
      naturalW = el.naturalWidth;
      naturalH = el.naturalHeight;
      return true;
    }
    return false;
  }

  function resetViewTransform() {
    rotation = 0;
    scale = 1;
    fitScale = 1;
    tx = 0;
    ty = 0;
    naturalW = 0;
    naturalH = 0;
    layoutW = 0;
    layoutH = 0;
    showingOriginal = false;
    panning = false;
    panMoved = false;
    if (viewer) {
      viewer.dataset.rotation = "0";
    }
    syncOriginalChrome();
    syncZoomChrome();
  }

  function cancelOriginalPreload() {
    if (originalPreload) {
      originalPreload.oncanplay = null;
      originalPreload.onerror = null;
      originalPreload.removeAttribute("src");
      originalPreload.load();
    }
    originalPreload = null;
    originalPreloadId = null;
  }

  function lockLayoutSize(item, el) {
    if (layoutW > 0 && layoutH > 0) {
      naturalW = layoutW;
      naturalH = layoutH;
      return true;
    }
    const meta = itemPixelSize(item);
    if (meta) {
      layoutW = meta.w;
      layoutH = meta.h;
      naturalW = layoutW;
      naturalH = layoutH;
      return true;
    }
    if (el && el.videoWidth > 0 && el.videoHeight > 0) {
      layoutW = el.videoWidth;
      layoutH = el.videoHeight;
      naturalW = layoutW;
      naturalH = layoutH;
      return true;
    }
    if (el && el.naturalWidth > 0 && el.naturalHeight > 0) {
      layoutW = el.naturalWidth;
      layoutH = el.naturalHeight;
      naturalW = layoutW;
      naturalH = layoutH;
      return true;
    }
    return false;
  }

  function zoomRange() {
    return {
      min: fitScale * MIN_ZOOM_FACTOR,
      max: fitScale * MAX_ZOOM_FACTOR,
    };
  }

  function zoomAt(factor, cx, cy) {
    if (!naturalW || viewer.hidden) {
      return;
    }
    fitOnLoad = false;
    const range = zoomRange();
    const next = Math.min(range.max, Math.max(range.min, scale * factor));
    if (next === scale) {
      syncZoomChrome();
      return;
    }
    const ix = (cx - tx) / scale;
    const iy = (cy - ty) / scale;
    scale = next;
    tx = cx - ix * scale;
    ty = cy - iy * scale;
    applyTransform();
    syncZoomChrome();
  }

  function rotateDisplay() {
    if (viewer.hidden) {
      return;
    }
    rotation = (rotation + 90) % 360;
    viewer.dataset.rotation = String(rotation);
    fitViewer();
  }

  function syncNavChrome() {
    const item = viewerIndex >= 0 ? items[viewerIndex] : null;
    if (viewerCrumb) {
      viewerCrumb.textContent = item && item.filename ? item.filename : "";
    }
    viewerPrev.disabled = viewerIndex <= 0;
    viewerNext.disabled = viewerIndex < 0 || viewerIndex >= items.length - 1;
    syncFavoriteChrome(item);
  }

  function syncZoomChrome() {
    if (!viewerZoomSlider || !fitScale) {
      return;
    }
    const pct = Math.round((scale / fitScale) * 100);
    const clamped = Math.max(25, Math.min(1600, pct));
    if (Number(viewerZoomSlider.value) !== clamped) {
      viewerZoomSlider.value = String(clamped);
    }
    viewerZoomSlider.disabled = !(naturalW > 0 && naturalH > 0);
    if (viewerZoomPct) {
      viewerZoomPct.textContent = clamped + "%";
    }
  }

  function setZoomPercent(percent, cx, cy) {
    if (!naturalW || viewer.hidden || !fitScale) {
      return;
    }
    const range = zoomRange();
    const next = Math.min(range.max, Math.max(range.min, fitScale * (percent / 100)));
    if (next === scale) {
      syncZoomChrome();
      return;
    }
    const ix = (cx - tx) / scale;
    const iy = (cy - ty) / scale;
    scale = next;
    tx = cx - ix * scale;
    ty = cy - iy * scale;
    applyTransform();
    syncZoomChrome();
  }

  function isZoomed() {
    return fitScale > 0 && scale > fitScale + 0.001;
  }

  function hideSlideshowEmpty() {
    slideshowEmpty.hidden = true;
    slideshowEmpty.textContent = SLIDESHOW_EMPTY;
  }

  function showSlideshowEmpty() {
    slideshowEmpty.hidden = false;
    slideshowEmpty.textContent = SLIDESHOW_EMPTY;
  }

  function syncFullscreenChrome() {
    const on = appFullscreen || !!document.fullscreenElement;
    viewer.dataset.fullscreen = on ? "1" : "0";
    document.body.dataset.fullscreen = on ? "1" : "0";
    viewerFullscreen.setAttribute("aria-pressed", on ? "true" : "false");
  }

  function enterFullscreen() {
    if (viewer.hidden) {
      return false;
    }
    appFullscreen = true;
    syncFullscreenChrome();
    const root = document.documentElement;
    if (root.requestFullscreen && !document.fullscreenElement) {
      const req = root.requestFullscreen();
      if (req && req.catch) {
        req.catch(function () {});
      }
    }
    return true;
  }

  function exitFullscreen() {
    const nativeOn = !!document.fullscreenElement;
    const was = appFullscreen || nativeOn;
    if (!was) {
      return false;
    }
    if (fullscreenExitRequested && !appFullscreen) {
      return false;
    }
    appFullscreen = false;
    if (nativeOn && document.exitFullscreen) {
      fullscreenExitRequested = true;
      const done = document.exitFullscreen();
      if (done && done.catch) {
        done.catch(function () {
          fullscreenExitRequested = false;
        });
      }
    }
    syncFullscreenChrome();
    return true;
  }

  function toggleFullscreen() {
    if (appFullscreen || document.fullscreenElement) {
      exitFullscreen();
      return;
    }
    enterFullscreen();
  }

  function syncSlideshowChrome() {
    viewer.dataset.slideshow = slideshowActive ? "1" : "0";
    viewer.dataset.slideshowPaused = slideshowActive && slideshowPaused ? "1" : "0";
    viewerSlideshow.setAttribute("aria-pressed", slideshowActive ? "true" : "false");
  }

  function clearSlideshowTimer() {
    if (slideshowTimer) {
      window.clearTimeout(slideshowTimer);
      slideshowTimer = 0;
    }
  }

  function stopSlideshow() {
    const was = slideshowActive;
    clearSlideshowTimer();
    slideshowActive = false;
    slideshowPaused = false;
    syncSlideshowChrome();
    return was;
  }

  function playSlideshowProxy(item) {
    if (!item || (item.kind !== "video" && item.kind !== "live") || !proxyReady(item)) {
      return;
    }
    const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    resetViewerVideo();
    showViewerPlaceholder(false);
    viewerImage.hidden = true;
    resetViewerOriginal();
    showingOriginal = false;
    syncOriginalChrome();
    viewerVideo.hidden = false;
    viewerVideo.setAttribute("data-using-proxy", "1");
    viewerVideo.setAttribute("data-source-ready", item.id);
    viewerVideo.onloadedmetadata = function () {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      layoutVideo(item);
    };
    viewerVideo.src = proxyUrl;
    layoutVideo(item);
    const play = viewerVideo.play();
    if (play && play.catch) {
      play.catch(function () {});
    }
  }

  function scheduleSlideshow() {
    clearSlideshowTimer();
    if (!slideshowActive || slideshowPaused) {
      return;
    }
    slideshowTimer = window.setTimeout(function () {
      slideshowTimer = 0;
      slideshowAdvance();
    }, SLIDESHOW_MS);
  }

  function slideshowAdvance() {
    if (!slideshowActive || slideshowPaused || viewer.hidden) {
      return;
    }
    syncViewerIndex();
    if (!items.length) {
      stopSlideshow();
      return;
    }
    const next = viewerIndex < 0 ? 0 : (viewerIndex + 1) % items.length;
    openViewerAt(next);
    const item = items[next];
    playSlideshowProxy(item);
    scheduleSlideshow();
  }

  function startSlideshow() {
    hideSlideshowEmpty();
    if (!items.length) {
      showSlideshowEmpty();
      return false;
    }
    if (viewer.hidden) {
      openViewer(items[0].id);
    }
    if (viewer.hidden) {
      showSlideshowEmpty();
      return false;
    }
    setInfoOpen(false);
    slideshowActive = true;
    slideshowPaused = false;
    syncSlideshowChrome();
    const item = syncViewerIndex();
    playSlideshowProxy(item);
    scheduleSlideshow();
    return true;
  }

  function toggleSlideshowPause() {
    if (!slideshowActive) {
      return false;
    }
    slideshowPaused = !slideshowPaused;
    if (slideshowPaused) {
      clearSlideshowTimer();
    } else {
      scheduleSlideshow();
    }
    syncSlideshowChrome();
    return true;
  }

  function formatDateTaken(value) {
    if (!value || typeof value !== "string") {
      return "";
    }
    return value.replace("T", " ").replace(/Z$/, "").replace(/\.\d+$/, "");
  }

  function formatFileSize(bytes) {
    const n = Number(bytes);
    if (!isFinite(n) || n < 0) {
      return "";
    }
    if (n < 1024) {
      return String(n) + " B";
    }
    if (n < 1024 * 1024) {
      return (n / 1024).toFixed(1) + " KB";
    }
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatGps(lat, lon) {
    if (lat == null || lon == null) {
      return "";
    }
    const latitude = Number(lat);
    const longitude = Number(lon);
    if (!isFinite(latitude) || !isFinite(longitude)) {
      return "";
    }
    const ns = latitude >= 0 ? "N" : "S";
    const ew = longitude >= 0 ? "E" : "W";
    return Math.abs(latitude).toFixed(5) + "°" + ns + ", " + Math.abs(longitude).toFixed(5) + "°" + ew;
  }

  function primaryLocation(item) {
    const locs = (item && item.locations) || [];
    const want = item && item.kind === "video" ? "motion" : "still";
    let fallback = null;
    for (let i = 0; i < locs.length; i += 1) {
      const loc = locs[i];
      if (!loc) {
        continue;
      }
      if (loc.current && loc.component === want && loc.role === "primary") {
        return loc;
      }
      if (loc.current && !fallback) {
        fallback = loc;
      }
    }
    return fallback || locs[0] || null;
  }

  function appendFact(list, label, value) {
    if (!value) {
      return;
    }
    const row = document.createElement("div");
    row.className = "info-fact";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    row.appendChild(dt);
    row.appendChild(dd);
    list.appendChild(row);
  }

  function renderFacts(item) {
    viewerFacts.innerHTML = "";
    const heading = document.createElement("p");
    heading.className = "info-heading";
    heading.textContent = "File";
    viewerFacts.appendChild(heading);
    const list = document.createElement("dl");
    list.className = "info-fact-list";
    list.id = "viewer-fact-list";
    const meta = (item && item.metadata) || {};
    const loc = primaryLocation(item);
    appendFact(list, "Date taken", formatDateTaken(item && item.capturedAt));
    appendFact(list, "Camera", (meta.camera && String(meta.camera).trim()) || NO_CAMERA_INFO);
    const width = Number(meta.width) || 0;
    const height = Number(meta.height) || 0;
    if (width > 0 && height > 0) {
      appendFact(list, "Dimensions", width + " × " + height);
    }
    if (loc) {
      appendFact(list, "Size", formatFileSize(loc.sizeBytes));
      appendFact(list, "Path", loc.lastKnownPath || loc.libraryRelativePath || "");
    }
    appendFact(list, "GPS", formatGps(meta.latitude, meta.longitude));
    viewerFacts.appendChild(list);
  }

  function zoomActual() {
    if (!naturalW || viewer.hidden) {
      return;
    }
    fitOnLoad = false;
    const box = viewerBox();
    const sw = box.w;
    const sh = box.h;
    scale = 1;
    tx = (sw - naturalW * scale) / 2;
    ty = (sh - naturalH * scale) / 2;
    applyTransform();
    syncZoomChrome();
  }

  function zoomByStep(direction) {
    if (viewer.hidden || !naturalW) {
      return;
    }
    const box = viewerBox();
    const cx = box.w / 2;
    const cy = box.h / 2;
    zoomAt(direction > 0 ? 1.1 : 1 / 1.1, cx, cy);
  }

  function syncFavoriteChrome(item) {
    const on = !!(item && item.favorite);
    viewerFavorite.textContent = on ? "♥" : "♡";
    viewerFavorite.setAttribute("aria-pressed", on ? "true" : "false");
    viewerFavorite.setAttribute("aria-label", on ? "Unfavorite" : "Favorite");
  }

  function infoOpen() {
    return !!(viewerInfoPanel && !viewerInfoPanel.hidden);
  }

  function setInfoOpen(open) {
    if (!viewerInfoPanel || !viewerInfo) {
      return;
    }
    viewerInfoPanel.hidden = !open;
    viewerInfo.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function syncOriginalChrome() {
    openOriginalBtn.textContent = "Open";
    openOriginalBtn.removeAttribute("aria-pressed");
    viewer.dataset.showingOriginal = showingOriginal ? "1" : "0";
  }

  function stepViewer(delta) {
    syncViewerIndex();
    if (!items.length) {
      return;
    }
    let next = viewerIndex + delta;
    if (slideshowActive) {
      next = ((next % items.length) + items.length) % items.length;
    } else if (next < 0 || next >= items.length) {
      return;
    }
    openViewerAt(next);
    if (slideshowActive && !slideshowPaused) {
      playSlideshowProxy(items[next]);
      scheduleSlideshow();
    }
  }

  function resetViewerOriginal() {
    if (!viewerOriginal) {
      return;
    }
    viewerOriginal.onload = null;
    viewerOriginal.onerror = null;
    viewerOriginal.removeAttribute("src");
    viewerOriginal.hidden = true;
  }

  function resetViewerVideo() {
    cancelOriginalPreload();
    viewerVideo.pause();
    viewerVideo.onloadedmetadata = null;
    viewerVideo.onloadeddata = null;
    viewerVideo.onerror = null;
    viewerVideo.removeAttribute("src");
    viewerVideo.removeAttribute("poster");
    viewerVideo.removeAttribute("data-source-ready");
    viewerVideo.removeAttribute("data-using-proxy");
    viewerVideo.load();
    viewerVideo.hidden = true;
    hideViewerScrub();
  }

  function hideViewerScrub() {
    if (viewerScrubWrap) {
      viewerScrubWrap.hidden = true;
    }
    if (viewerScrub) {
      viewerScrub.value = "0";
    }
    if (viewerScrubTime) {
      viewerScrubTime.textContent = "0:00";
    }
  }

  function showViewerScrub() {
    if (viewerScrubWrap) {
      viewerScrubWrap.hidden = false;
    }
    syncViewerScrub();
  }

  function syncViewerScrub() {
    if (!viewerScrub || viewerVideo.hidden) {
      return;
    }
    const duration = viewerVideo.duration;
    if (!isFinite(duration) || duration <= 0) {
      if (viewerScrubTime) {
        viewerScrubTime.textContent = formatDuration(viewerVideo.currentTime || 0);
      }
      return;
    }
    if (!scrubbingViewer) {
      viewerScrub.value = String(Math.round((viewerVideo.currentTime / duration) * 1000));
    }
    if (viewerScrubTime) {
      viewerScrubTime.textContent = formatDuration(viewerVideo.currentTime) + " / " + formatDuration(duration);
    }
  }

  function loadViewerOriginal(item) {
    if (!viewerOriginal || !item || item.available === false || item.kind === "video") {
      resetViewerOriginal();
      showingOriginal = false;
      syncOriginalChrome();
      return;
    }
    const itemId = item.id;
    const url = "/api/media/" + encodeURIComponent(itemId) + "?which=original";
    const probe = new Image();
    probe.onload = function () {
      if (viewerIndex < 0 || !items[viewerIndex] || items[viewerIndex].id !== itemId || viewer.hidden) {
        return;
      }
      viewerOriginal.onload = function () {
        if (viewerIndex < 0 || !items[viewerIndex] || items[viewerIndex].id !== itemId || viewer.hidden) {
          return;
        }
        viewerOriginal.hidden = false;
        showingOriginal = true;
        applyTransform();
        syncOriginalChrome();
      };
      viewerOriginal.onerror = function () {
        resetViewerOriginal();
        showingOriginal = false;
        syncOriginalChrome();
      };
      viewerOriginal.src = url;
      viewerOriginal.setAttribute("data-which", "original");
    };
    probe.onerror = function () {};
    probe.src = url;
  }

  function proxyReady(item) {
    return !!item && ((item.renditions || {}).status || {}).proxy === "ready";
  }

  function stillPreviewReady(item) {
    if (!item) {
      return false;
    }
    const status = (item.renditions || {}).status || {};
    if (item.kind === "video") {
      return status.poster === "ready";
    }
    return status.preview === "ready";
  }

  function showRevealFailed() {
    unavailableBanner.hidden = false;
    if (revealError) {
      revealError.hidden = false;
      revealError.textContent = "Original is not on this computer";
    }
    revealOriginalBtn.disabled = true;
    openOriginalBtn.disabled = true;
  }

  function clearRevealFailed() {
    if (revealError) {
      revealError.hidden = true;
    }
  }

  function syncViewerChrome(item) {
    const available = !!(item && item.available);
    unavailableBanner.hidden = available;
    revealOriginalBtn.disabled = !available;
    openOriginalBtn.disabled = !available;
    if (available) {
      clearRevealFailed();
    }
    playPreviewBtn.disabled = true;
    syncNavChrome();
    syncOriginalChrome();
    syncZoomChrome();
    if (!item || !proxyReady(item)) {
      return;
    }
    const itemId = item.id;
    fetch("/api/media/" + encodeURIComponent(itemId) + "?which=proxy", { method: "HEAD" }).then(function (res) {
      if (viewerIndex < 0 || !items[viewerIndex] || items[viewerIndex].id !== itemId) {
        return;
      }
      playPreviewBtn.disabled = !res.ok;
    }).catch(function () {
      if (viewerIndex < 0 || !items[viewerIndex] || items[viewerIndex].id !== itemId) {
        return;
      }
      playPreviewBtn.disabled = true;
    });
  }

  function showViewerPlaceholder(show) {
    viewerPlaceholder.hidden = !show;
    if (show) {
      viewerImage.hidden = true;
      resetViewerOriginal();
    }
  }

  function clearAnnotateError() {
    if (!annotateError) {
      return;
    }
    annotateError.hidden = true;
    annotateError.textContent = "";
  }

  function clearAnnotateFields() {
    [personField, placeField, thingField].forEach(function (field) {
      if (!field) {
        return;
      }
      field.value = "";
      delete field.dataset.committed;
    });
  }

  function hideViewerChrome() {
    stopSlideshow();
    exitFullscreen();
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
    viewerImage.hidden = false;
    resetViewerOriginal();
    resetViewerVideo();
    resetViewTransform();
    unavailableBanner.hidden = true;
    viewerPlaceholder.hidden = true;
    clearRevealFailed();
    revealOriginalBtn.disabled = true;
    openOriginalBtn.disabled = true;
    setInfoOpen(false);
    playPreviewBtn.disabled = true;
    hideViewerScrub();
    syncFavoriteChrome(null);
    viewerIndex = -1;
    viewerItemId = null;
    panning = false;
    panMoved = false;
    if (viewerCrumb) {
      viewerCrumb.textContent = "";
    }
    clearAnnotateError();
    clearAnnotateFields();
    viewerFacts.innerHTML = "";
    if (peopleLabels) {
      peopleLabels.innerHTML = "";
    }
    if (placeLabels) {
      placeLabels.innerHTML = "";
    }
    if (thingsLabels) {
      thingsLabels.innerHTML = "";
    }
  }

  function closeViewer() {
    const restoreLevel = savedLevel;
    const restoreScroll = savedScroll;
    const restoreFilter = copyFilter(savedFilter);
    const restoreSearch = savedSearch;
    const filterChanged = !filtersEqual(filter, restoreFilter);
    hideViewerChrome();
    if (!skipHistory) {
      stayOnLiveOrigin({ library: true, view: "grid" }, "", true);
    }
    applyFilterState(restoreFilter, restoreSearch);
    function finish() {
      refreshInspectorFromItems();
      window.requestAnimationFrame(function () {
        main.scrollTop = restoreScroll;
      });
    }
    if (settings.zoomLevel !== restoreLevel) {
      setLevel(restoreLevel, true, true).then(finish);
    } else if (filterChanged) {
      renderKey = "";
      loadCatalog().then(finish);
    } else {
      finish();
    }
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

  function scheduleOriginalSwap(item, originalUrl, startTime) {
    cancelOriginalPreload();
    if (!item || item.available === false || !browserCanPlayOriginal(item)) {
      return;
    }
    const preload = document.createElement("video");
    preload.preload = "auto";
    preload.muted = true;
    originalPreload = preload;
    originalPreloadId = item.id;
    preload.onerror = function () {
      if (originalPreloadId === item.id) {
        cancelOriginalPreload();
      }
    };
    preload.oncanplay = function () {
      if (originalPreloadId !== item.id || viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      const t = Math.max(viewerVideo.currentTime || 0, Number(startTime) || 0);
      const paused = viewerVideo.paused;
      const rate = viewerVideo.playbackRate || 1;
      viewerVideo.onloadeddata = function () {
        if (viewerItemId !== item.id || viewer.hidden) {
          return;
        }
        try {
          if (isFinite(t)) {
            viewerVideo.currentTime = t;
          }
        } catch (err) {}
        viewerVideo.playbackRate = rate;
        layoutVideo(item);
        if (!paused) {
          const play = viewerVideo.play();
          if (play && play.catch) {
            play.catch(function () {});
          }
        }
        syncViewerScrub();
      };
      viewerVideo.removeAttribute("data-using-proxy");
      viewerVideo.src = originalUrl;
    };
    preload.src = originalUrl;
  }

  function applyViewerStartTime(startTime) {
    const seekTo = Number(startTime);
    if (!isFinite(seekTo) || seekTo <= 0) {
      return;
    }
    const duration = viewerVideo.duration;
    let next = seekTo;
    if (isFinite(duration) && duration > 0) {
      next = Math.min(seekTo, Math.max(0, duration - 0.05));
    }
    try {
      viewerVideo.currentTime = next;
    } catch (err) {}
  }

  function playOriginalOrProxy(item, startTime, autoplay) {
    const originalUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=original";
    const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    viewerVideo.hidden = false;
    showViewerPlaceholder(false);
    function afterReady() {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      applyViewerStartTime(startTime);
      layoutVideo(item);
      showViewerScrub();
      if (autoplay) {
        const play = viewerVideo.play();
        if (play && play.catch) {
          play.catch(function () {});
        }
      }
    }
    if (viewerVideo.getAttribute("data-source-ready") === item.id && (viewerVideo.currentSrc || viewerVideo.getAttribute("src"))) {
      afterReady();
      return;
    }
    viewerVideo.onerror = function () {
      if (viewerVideo.getAttribute("data-using-proxy") === "1") {
        return;
      }
      viewerVideo.setAttribute("data-using-proxy", "1");
      viewerVideo.src = proxyUrl;
    };
    viewerVideo.onloadedmetadata = function () {
      afterReady();
    };
    viewerVideo.setAttribute("data-source-ready", item.id);
    viewerVideo.setAttribute("data-using-proxy", "1");
    viewerVideo.src = proxyUrl;
    layoutVideo(item);
    showViewerScrub();
    scheduleOriginalSwap(item, originalUrl, startTime);
  }

  function liveMotionPlayable(item) {
    if (!item || item.kind !== "live") {
      return false;
    }
    if (item.motionAvailable) {
      return true;
    }
    return proxyReady(item);
  }

  function showLiveMotion(item) {
    viewerImage.hidden = true;
    resetViewerOriginal();
    viewerVideo.hidden = false;
    const originalUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=original&component=motion";
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
    if (item.motionAvailable) {
      viewerVideo.src = originalUrl;
      return;
    }
    useProxy();
  }

  function toggleViewerPlay() {
    if (viewer.hidden) {
      return;
    }
    const item = syncViewerIndex();
    if (!item) {
      return;
    }
    if (item.kind === "live") {
      if (!liveMotionPlayable(item)) {
        return;
      }
      showLiveMotion(item);
      showViewerScrub();
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
      return;
    }
    if (item.kind !== "video") {
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

  function renderViewerLabels(item) {
    renderFacts(item);
    if (peopleLabels) {
      peopleLabels.innerHTML = "";
    }
    if (placeLabels) {
      placeLabels.innerHTML = "";
    }
    if (thingsLabels) {
      thingsLabels.innerHTML = "";
    }
    if (!item) {
      return;
    }
    const entities = item.entities || {};
    function addLabels(node, kind, records) {
      if (!node) {
        return;
      }
      (records || []).forEach(function (rec) {
        if (!rec || !rec.id || !rec.name) {
          return;
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "entity-label";
        btn.dataset.entityKind = kind;
        btn.dataset.entityId = rec.id;
        btn.textContent = rec.name;
        btn.addEventListener("click", function () {
          filterByEntity(kind, rec.id);
        });
        node.appendChild(btn);
      });
    }
    addLabels(peopleLabels, "person", entities.people);
    addLabels(placeLabels, "place", entities.places);
    addLabels(thingsLabels, "thing", entities.things);
    function fillEmpty(node) {
      if (!node || node.childNodes.length) {
        return;
      }
      const empty = document.createElement("p");
      empty.className = "info-empty";
      empty.textContent = "None yet";
      node.appendChild(empty);
    }
    fillEmpty(peopleLabels);
    fillEmpty(placeLabels);
    fillEmpty(thingsLabels);
  }

  function openStillViewer(item, index) {
    resetViewerVideo();
    resetViewerOriginal();
    resetViewTransform();
    viewerIndex = index;
    viewerItemId = item.id;
    syncViewerChrome(item);
    renderViewerLabels(item);
    const url = "/api/media/" + encodeURIComponent(item.id) + "?which=preview";
    const same = viewerItemId === item.id && !viewer.hidden && viewerImage.getAttribute("src") === url;
    viewerIndex = index;
    viewerItemId = item.id;
    viewer.hidden = false;
    viewerImage.draggable = false;
    rotation = 0;
    if (!stillPreviewReady(item)) {
      viewerImage.removeAttribute("src");
      showViewerPlaceholder(true);
      if (item.available !== false) {
        loadViewerOriginal(item);
      }
      return;
    }
    showViewerPlaceholder(false);
    viewerImage.hidden = false;
    if (same && viewerImage.complete && viewerImage.naturalWidth > 0) {
      loadViewerOriginal(item);
      return;
    }
    fitOnLoad = true;
    viewerImage.onload = function () {
      showViewerPlaceholder(false);
      viewerImage.hidden = false;
      naturalW = viewerImage.naturalWidth;
      naturalH = viewerImage.naturalHeight;
      if (fitOnLoad) {
        fitViewer();
        fitOnLoad = false;
      }
      loadViewerOriginal(item);
    };
    viewerImage.onerror = function () {
      viewerImage.removeAttribute("src");
      showViewerPlaceholder(true);
    };
    viewerImage.src = url;
    viewerImage.setAttribute("data-which", "preview");
  }

  function layoutVideo(item, forceFit) {
    const had = layoutW > 0 && layoutH > 0;
    if (!lockLayoutSize(item, viewerVideo)) {
      return;
    }
    if (!had || forceFit) {
      fitViewer();
      return;
    }
    applyTransform();
    syncZoomChrome();
  }

  function openVideoViewer(item, index, startTime, autoplay) {
    viewerImage.removeAttribute("src");
    viewerImage.hidden = true;
    resetViewerOriginal();
    resetViewerVideo();
    resetViewTransform();
    showingOriginal = false;
    viewerIndex = index;
    viewerItemId = item.id;
    syncViewerChrome(item);
    renderViewerLabels(item);
    viewerIndex = index;
    viewerItemId = item.id;
    viewer.hidden = false;
    rotation = 0;
    if (!stillPreviewReady(item)) {
      showViewerPlaceholder(true);
      viewerVideo.hidden = true;
      return;
    }
    showViewerPlaceholder(false);
    viewerVideo.hidden = false;
    viewerVideo.poster = "/api/media/" + encodeURIComponent(item.id) + "?which=poster";
    viewerVideo.onloadedmetadata = function () {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      layoutVideo(item);
    };
    layoutVideo(item);
    if (autoplay) {
      playOriginalOrProxy(item, startTime, true);
    }
  }

  function openViewerAt(index, startTime, autoplay) {
    if (index < 0 || index >= items.length) {
      return;
    }
    const item = items[index];
    if (item.kind === "video") {
      openVideoViewer(item, index, startTime, autoplay);
      return;
    }
    openStillViewer(item, index);
  }

  function openViewer(id) {
    hideSlideshowEmpty();
    const index = items.findIndex(function (item) {
      return item.id === id;
    });
    if (index < 0) {
      return;
    }
    savedScroll = main.scrollTop;
    savedLevel = settings.zoomLevel;
    savedFilter = copyFilter(filter);
    savedSearch = searchInput ? searchInput.value : filter.q;
    selectedId = id;
    syncSelectionChrome();
    openViewerAt(index, hoverPreviewTime(id), true);
    if (!skipHistory) {
      stayOnLiveOrigin({ library: true, view: "viewer", id: id }, "#item/" + encodeURIComponent(id), false);
    }
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

  function formatDuration(sec) {
    if (sec == null || !isFinite(Number(sec))) {
      return "";
    }
    const n = Math.max(0, Math.round(Number(sec)));
    const m = Math.floor(n / 60);
    const s = n % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function syncHeartButton(btn, on) {
    if (!btn) {
      return;
    }
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.setAttribute("aria-label", on ? "Remove favorite" : "Favorite");
  }

  function setItemFavorite(id, on) {
    items.forEach(function (item) {
      if (item.id === id) {
        item.favorite = on;
      }
    });
    main.querySelectorAll('.cell[data-id="' + id + '"]').forEach(function (cell) {
      syncHeartButton(cell.querySelector(".heart"), on);
    });
    renderKey = "";
    render();
  }

  function toggleFavorite(event, item) {
    event.preventDefault();
    event.stopPropagation();
    const next = !item.favorite;
    fetch("/api/items/" + encodeURIComponent(item.id) + "/favorite", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ favorite: next }),
    }).then(readJson).then(function (updated) {
      setItemFavorite(item.id, !!(updated && updated.favorite));
    }).catch(function () {});
  }

  function makeCell(item, slot) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "cell";
    cell.dataset.id = item.id;
    cell.dataset.filename = item.filename || "";
    cell.dataset.kind = item.kind || "";
    cell.dataset.slot = slot || "grid";
    const placeholder = document.createElement("span");
    placeholder.className = "placeholder";
    placeholder.textContent = PLACEHOLDER;
    const img = document.createElement("img");
    img.alt = "";
    img.hidden = true;
    cell.appendChild(placeholder);
    cell.appendChild(img);
    const badges = document.createElement("div");
    badges.className = "tile-badges";
    if (item.kind === "live") {
      const badge = document.createElement("span");
      badge.className = "live-badge tile-badge";
      badge.textContent = "LIVE";
      badges.appendChild(badge);
    } else if (item.kind === "video") {
      const badge = document.createElement("span");
      badge.className = "video-badge tile-badge";
      const duration = formatDuration((item.metadata || {}).durationSec);
      badge.innerHTML = PLAY_ICON + "<span>VIDEO</span>" + (duration ? "<span>" + duration + "</span>" : "");
      badges.appendChild(badge);
    }
    const heart = document.createElement("span");
    heart.className = "heart";
    heart.setAttribute("role", "button");
    heart.tabIndex = 0;
    heart.innerHTML = HEART_ICON;
    syncHeartButton(heart, !!item.favorite);
    heart.addEventListener("click", function (event) {
      toggleFavorite(event, itemById(item.id));
    });
    heart.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        toggleFavorite(event, itemById(item.id));
      }
    });
    badges.appendChild(heart);
    cell.appendChild(badges);
    cell.addEventListener("mouseenter", function () {
      hoveredId = item.id;
      startHover(cell, itemById(item.id));
    });
    cell.addEventListener("mouseleave", function () {
      if (hoveredId === item.id) {
        hoveredId = null;
      }
      stopHover();
    });
    cell.addEventListener("focus", function () {
      selectedId = item.id;
      syncSelectionChrome();
    });
    cell.addEventListener("click", function () {
      selectedId = item.id;
      if (hoverVideo && hoverCell === cell) {
        rememberHoverTime(item.id, hoverVideo);
      }
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

  function currentCellSize() {
    return SIZE_STEPS[gridSize] || SIZE_STEPS[0];
  }

  function applyGridMetrics() {
    const level = settings.zoomLevel;
    const size = currentCellSize();
    const dateMode = currentDateMode();
    main.dataset.level = level;
    main.dataset.size = String(size);
    main.dataset.groupDates = groupDates ? "on" : "off";
    main.dataset.dateGroup = dateMode;
    main.dataset.hearts = size >= HEART_MIN ? "on" : "off";
    main.className = "level-" + level + (groupDates ? "" : " wall");
    main.style.setProperty("--cell", size + "px");
    if (sizeSlider) {
      sizeSlider.value = String(gridSize);
    }
    if (dateGroupSelect && dateGroupSelect.value !== dateMode) {
      dateGroupSelect.value = dateMode;
    }
  }

  function groupsFromItems(list, level) {
    const out = [];
    const seen = {};
    (list || []).forEach(function (item) {
      const captured = (item && item.capturedAt) || "";
      let key = captured.slice(0, 10);
      if (level === "years") {
        key = captured.slice(0, 4);
      } else if (level === "months") {
        key = captured.slice(0, 7);
      }
      if (seen[key] == null) {
        seen[key] = out.length;
        out.push({ key: key, itemIds: [item.id] });
      } else {
        out[seen[key]].itemIds.push(item.id);
      }
    });
    return out;
  }

  function collectCells() {
    const map = {};
    main.querySelectorAll(".cell").forEach(function (cell) {
      map[(cell.dataset.slot || "grid") + ":" + cell.dataset.id] = cell;
    });
    return map;
  }

  function takeCell(existing, id, slot) {
    const key = (slot || "grid") + ":" + id;
    let cell = existing[key];
    if (cell) {
      delete existing[key];
      const item = itemById(id);
      syncHeartButton(cell.querySelector(".heart"), !!(item && item.favorite));
      return cell;
    }
    return makeCell(itemById(id), slot);
  }

  function makeFavoritesSection(existing, mosaic) {
    const hearted = items.filter(function (item) {
      return item && item.favorite;
    });
    if (!hearted.length) {
      return null;
    }
    const section = document.createElement("section");
    section.id = "favorites";
    section.className = "group favorites" + (favoritesOpen ? "" : " collapsed");
    const heading = document.createElement("h2");
    heading.className = "group-key";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "favorites-toggle";
    toggle.textContent = "Favorites";
    toggle.setAttribute("aria-expanded", favoritesOpen ? "true" : "false");
    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      favoritesOpen = !favoritesOpen;
      section.classList.toggle("collapsed", !favoritesOpen);
      toggle.setAttribute("aria-expanded", favoritesOpen ? "true" : "false");
    });
    heading.appendChild(toggle);
    section.appendChild(heading);
    const list = document.createElement("div");
    list.className = mosaic ? "mosaic" : "item-list";
    hearted.forEach(function (item) {
      list.appendChild(takeCell(existing, item.id, "fav"));
    });
    section.appendChild(list);
    return section;
  }

  function render() {
    const level = settings.zoomLevel;
    applyGridMetrics();
    syncPresentableSort();
    syncFilterDataset();
    syncSelectionChrome();
    if (!items.length) {
      stopHover();
      if (hasActiveFilter()) {
        main.innerHTML = "<p>" + emptySearchText() + "</p>";
        renderKey = "empty-search:" + emptySearchText();
      } else {
        main.innerHTML = '<div class="empty-state" id="empty-library"><p>' + EMPTY + '</p><button type="button" id="empty-add-folder">Add folder</button></div>';
        const emptyAdd = document.getElementById("empty-add-folder");
        if (emptyAdd) {
          emptyAdd.addEventListener("click", openAddDialog);
        }
        renderKey = "empty";
      }
      applyGridMetrics();
      return;
    }
    const favKey = items.filter(function (item) {
      return item.favorite;
    }).map(function (item) {
      return item.id;
    }).join(",");
    const key = level + "|" + (groupDates ? "dates" : "wall") + "|" + favKey + "|" + settings.sort + "|" + settings.dir + "|" + queryString() + "|" + groups.map(function (group) {
      return group.key + ":" + (group.itemIds || []).join(",");
    }).join(";");
    if (key === renderKey) {
      main.querySelectorAll(".cell").forEach(function (cell) {
        requestStill(cell, cell.dataset.id);
      });
      return;
    }
    const anchor = visibleAnchorId();
    const existing = collectCells();
    const mosaic = groupDates && (level === "years" || level === "months");
    const fragment = document.createDocumentFragment();
    const fav = makeFavoritesSection(existing, mosaic);
    if (fav) {
      fragment.appendChild(fav);
    }
    if (!groupDates) {
      const list = document.createElement("div");
      list.className = "item-list wall-list";
      items.forEach(function (item) {
        list.appendChild(takeCell(existing, item.id, "grid"));
      });
      fragment.appendChild(list);
    } else {
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
          list.appendChild(takeCell(existing, id, "grid"));
        });
        section.appendChild(list);
        fragment.appendChild(section);
      });
    }
    Object.keys(existing).forEach(function (keyName) {
      const leftover = existing[keyName];
      if (leftover && leftover.parentNode) {
        leftover.parentNode.removeChild(leftover);
      }
    });
    main.innerHTML = "";
    main.appendChild(fragment);
    applyGridMetrics();
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
      lastSources = sources;
      applySettings(parts[3]);
      const status = sourcesStatus(sources);
      scanning = status.running;
      if (sources.length) {
        showStatus(status.text, true);
        syncScanRetry(sources);
      } else {
        showStatus("", false);
        syncScanRetry([]);
      }
      showDisconnected(false);
      items = nextItems;
      groups = nextGroups;
      const open = syncViewerIndex();
      if (open) {
        renderViewerLabels(open);
        syncViewerChrome(open);
      } else if (!viewer.hidden) {
        syncNavChrome();
      }
      render();
      if (filter.person || filter.place || filter.thing) {
        refreshInspectorFromItems();
      }
    }).catch(function () {
      showDisconnected(true);
    });
  }

  function setLevel(level, persistChange, keepSize) {
    if (LEVELS.indexOf(level) === -1) {
      return Promise.resolve();
    }
    const same = level === settings.zoomLevel;
    const anchor = visibleAnchorId();
    settings.zoomLevel = level;
    if (!keepSize) {
      gridSize = DEFAULT_SIZE[level] != null ? DEFAULT_SIZE[level] : 0;
    }
    applyGridMetrics();
    if (!same) {
      groups = groupsFromItems(items, level);
      renderKey = "";
      render();
      scrollIdIntoView(anchor || hoveredId);
    }
    const done = persistChange && !same ? persist({ zoomLevel: level }) : Promise.resolve();
    return done.then(function () {
      if (same) {
        return;
      }
      return loadCatalog();
    }).then(function () {
      scrollIdIntoView(anchor || hoveredId);
      rearmHover();
    });
  }

  function setDateMode(mode, persistChange) {
    if (DATE_MODES.indexOf(mode) === -1) {
      return Promise.resolve();
    }
    if (mode === "off") {
      if (!groupDates) {
        applyGridMetrics();
        return Promise.resolve();
      }
      groupDates = false;
      applyGridMetrics();
      renderKey = "";
      render();
      rearmHover();
      return Promise.resolve();
    }
    const wasOff = !groupDates;
    groupDates = true;
    const level = mode === "days" && settings.zoomLevel === "all" ? "all" : mode;
    if (wasOff && level === settings.zoomLevel) {
      applyGridMetrics();
      renderKey = "";
      render();
      rearmHover();
      return Promise.resolve();
    }
    return setLevel(level, persistChange, true);
  }

  function setGridSize(index) {
    const next = Math.max(0, Math.min(SIZE_STEPS.length - 1, Number(index)));
    if (next === gridSize) {
      applyGridMetrics();
      rearmHover();
      return;
    }
    gridSize = next;
    applyGridMetrics();
    rearmHover();
  }

  function stepGridSize(delta) {
    setGridSize(gridSize + delta);
  }

  function handleGridWheel(event) {
    if (levelWheelLock) {
      return;
    }
    levelWheelLock = true;
    window.setTimeout(function () {
      levelWheelLock = false;
    }, 80);
    stepGridSize(event.deltaY < 0 ? 1 : -1);
  }

  function handleViewerZoom(event) {
    const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    zoomAt(factor, event.clientX, event.clientY);
  }

  function textFocused() {
    const node = document.activeElement;
    if (!node) {
      return false;
    }
    const tag = (node.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || node.isContentEditable;
  }

  function filterByEntity(kind, id) {
    if (!id) {
      return;
    }
    filter.q = "";
    filter.scope = "";
    filter.person = "";
    filter.place = "";
    filter.thing = "";
    filter.kind = "";
    filter.favorite = "";
    if (kind === "person") {
      filter.person = id;
    } else if (kind === "place") {
      filter.place = id;
    } else if (kind === "thing") {
      filter.thing = id;
    }
    if (searchInput) {
      searchInput.value = "";
    }
    syncChips();
    syncFilterDataset();
    renderKey = "";
    if (!viewer.hidden) {
      hideViewerChrome();
      if (!skipHistory) {
        stayOnLiveOrigin({ library: true, view: "grid" }, "", true);
      }
    }
    return loadCatalog().then(function () {
      refreshInspectorFromItems();
    });
  }

  function applySearchFromBox() {
    filter.q = searchInput ? searchInput.value : "";
    filter.person = "";
    filter.place = "";
    filter.thing = "";
    hideInspector();
    syncChips();
    syncFilterDataset();
    renderKey = "";
    return loadCatalog();
  }

  function commitAnnotate(field, kind) {
    if (!field || annotateBusy || viewerIndex < 0 || viewer.hidden) {
      return;
    }
    const item = syncViewerIndex();
    if (!item) {
      return;
    }
    const value = field.value.trim();
    if (!value) {
      return;
    }
    if (field.dataset.committed === value) {
      return;
    }
    const payload = {};
    if (kind === "person") {
      payload.people = [{ name: value }];
    } else if (kind === "place") {
      payload.places = [{ name: value }];
    } else if (kind === "thing") {
      payload.things = [{ name: value }];
    } else {
      return;
    }
    clearAnnotateError();
    annotateBusy = true;
    fetch("/api/items/" + encodeURIComponent(item.id) + "/annotations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(readJson).then(function (updated) {
      annotateBusy = false;
      field.dataset.committed = value;
      field.value = "";
      delete field.dataset.committed;
      if (viewerIndex >= 0) {
        items[viewerIndex] = updated;
        renderViewerLabels(updated);
      }
    }).catch(function (err) {
      annotateBusy = false;
      if (annotateError) {
        annotateError.hidden = false;
        annotateError.textContent = (err && err.body && err.body.error) || "invalid-argument";
      }
    });
  }

  function afterAddAccepted() {
    closeAddDialog();
    showStatus("Folder added", true);
    renderKey = "";
    return loadCatalog();
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
      return afterAddAccepted();
    }).catch(function (err) {
      if (err && (err.status === 409 || (err.body && err.body.error === "busy"))) {
        return afterAddAccepted();
      }
      addError.hidden = false;
      addError.textContent = (err && err.body && err.body.error) || "invalid-argument";
    });
  }

  function browseFolder() {
    fetch("/api/pick-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(function (res) {
      return res.json().catch(function () {
        return {};
      }).then(function (body) {
        if (res.status === 404 && body && body.error === "picker-unavailable") {
          return;
        }
        if (res.ok && body && body.path) {
          addPath.value = body.path;
          syncAddEnabled();
        }
      });
    }).catch(function () {});
  }

  function askRemove(id) {
    pendingRemoveId = id;
    if (confirmRemove && confirmRemove.showModal) {
      confirmRemove.showModal();
      return;
    }
    if (window.confirm("Remove from Library? The file stays on disk.")) {
      performRemove(id);
    }
  }

  function askDeleteFile(id) {
    pendingRemoveId = id;
    if (confirmDeleteFile && confirmDeleteFile.showModal) {
      confirmDeleteFile.showModal();
      return;
    }
    if (window.confirm("Delete this file from disk?")) {
      performDeleteFile(id);
    }
  }

  function afterItemGone(id) {
    if (viewerItemId === id) {
      hideViewerChrome();
      stayOnLiveOrigin({ library: true, view: "grid" }, "", true);
    }
    if (selectedId === id) {
      selectedId = null;
    }
    pendingRemoveId = null;
    syncSelectionChrome();
    renderKey = "";
    return loadCatalog();
  }

  function performRemove(id) {
    return fetch("/api/items/" + encodeURIComponent(id) + "/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      return afterItemGone(id);
    }).catch(function () {});
  }

  function performDeleteFile(id) {
    return fetch("/api/items/" + encodeURIComponent(id) + "/delete-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      return afterItemGone(id);
    }).catch(function () {});
  }

  if (removeItemBtn) {
    removeItemBtn.addEventListener("click", function () {
      const id = viewerItemId || selectedId;
      if (id) {
        askRemove(id);
      }
    });
  }
  if (deleteFileBtn) {
    deleteFileBtn.addEventListener("click", function () {
      const id = viewerItemId || selectedId;
      if (id) {
        askDeleteFile(id);
      }
    });
  }
  if (confirmRemove) {
    const cancel = document.getElementById("confirm-remove-cancel");
    const ok = document.getElementById("confirm-remove-ok");
    if (cancel) {
      cancel.addEventListener("click", function () {
        confirmRemove.close();
      });
    }
    if (ok) {
      ok.addEventListener("click", function () {
        const id = pendingRemoveId;
        confirmRemove.close();
        if (id) {
          performRemove(id);
        }
      });
    }
  }
  if (confirmDeleteFile) {
    const cancel = document.getElementById("confirm-delete-cancel");
    const ok = document.getElementById("confirm-delete-ok");
    if (cancel) {
      cancel.addEventListener("click", function () {
        confirmDeleteFile.close();
      });
    }
    if (ok) {
      ok.addEventListener("click", function () {
        const id = pendingRemoveId;
        confirmDeleteFile.close();
        if (id) {
          performDeleteFile(id);
        }
      });
    }
  }
  if (scanRetry) {
    scanRetry.addEventListener("click", function () {
      const path = scanRetry.dataset.path || "";
      const mode = scanRetry.dataset.mode || "serve-from-there";
      if (!path) {
        return;
      }
      scanRetry.disabled = true;
      fetch("/api/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, mode: mode }),
      }).then(readJson).then(function () {
        scanRetry.disabled = false;
        showStatus("Retrying scan", true);
        renderKey = "";
        return loadCatalog();
      }).catch(function () {
        scanRetry.disabled = false;
        return loadCatalog();
      });
    });
  }
  if (reconnectRetry) {
    reconnectRetry.addEventListener("click", function () {
      fetch("/api/health").then(function (res) {
        if (!res.ok) {
          showDisconnected(true);
          return;
        }
        showDisconnected(false);
        return loadCatalog();
      }).catch(function () {
        showDisconnected(true);
      });
    });
  }

  hideSlideshowEmpty();
  syncFullscreenChrome();
  syncSlideshowChrome();
  addFolderBtn.addEventListener("click", openAddDialog);
  addCancel.addEventListener("click", closeAddDialog);
  addSubmit.addEventListener("click", submitAdd);
  if (addBrowse) {
    addBrowse.addEventListener("click", browseFolder);
  }
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

  function persistSort() {
    persist({ sort: settings.sort, dir: settings.dir }).then(function () {
      renderKey = "";
      return loadCatalog();
    });
  }
  if (sortPresentable) {
    sortPresentable.addEventListener("change", function () {
      applyPresentableSort(sortPresentable.value);
      persistSort();
    });
  }
  sortSelect.addEventListener("change", function () {
    settings.sort = sortSelect.value;
    syncPresentableSort();
    persistSort();
  });
  dirSelect.addEventListener("change", function () {
    settings.dir = dirSelect.value;
    syncPresentableSort();
    persistSort();
  });

  function setKindFilter(kind, favorite) {
    filter.kind = kind || "";
    filter.favorite = favorite || "";
    syncFilterDataset();
    renderKey = "";
    loadCatalog();
  }
  if (filterAll) {
    filterAll.addEventListener("click", function () {
      setKindFilter("", "");
    });
  }
  if (filterPhotos) {
    filterPhotos.addEventListener("click", function () {
      setKindFilter("photo,live", "");
    });
  }
  if (sizeSlider) {
    sizeSlider.addEventListener("input", function () {
      setGridSize(Number(sizeSlider.value));
    });
  }
  if (filterVideos) {
    filterVideos.addEventListener("click", function () {
      setKindFilter(filter.kind === "video" ? "" : "video", "");
    });
  }
  if (filterFavorites) {
    filterFavorites.addEventListener("click", function () {
      setKindFilter("", filter.favorite === "1" ? "" : "1");
    });
  }
  if (dateGroupSelect) {
    dateGroupSelect.addEventListener("change", function () {
      setDateMode(dateGroupSelect.value, true);
    });
  }

  function wheelTargetIsChrome(event) {
    const node = event.target;
    if (!node || !node.closest) {
      return false;
    }
    return !!node.closest("input, select, textarea, button, label, a, #viewer-info-panel");
  }

  viewer.addEventListener("wheel", function (event) {
    if (viewer.hidden) {
      return;
    }
    if (wheelTargetIsChrome(event)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (!naturalW) {
      const item = syncViewerIndex();
      lockLayoutSize(item, viewerVideo && !viewerVideo.hidden ? viewerVideo : viewerImage);
    }
    handleViewerZoom(event);
  }, { passive: false, capture: true });

  window.addEventListener("wheel", function (event) {
    if (!event.ctrlKey) {
      return;
    }
    event.preventDefault();
    if (!viewer.hidden) {
      if (wheelTargetIsChrome(event)) {
        return;
      }
      handleViewerZoom(event);
      return;
    }
    if (currentView !== "library") {
      return;
    }
    handleGridWheel(event);
  }, { passive: false });

  document.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && (event.key === "f" || event.key === "F")) {
      if (searchInput) {
        event.preventDefault();
        searchInput.focus();
      }
      return;
    }
    if (event.key === "F5") {
      event.preventDefault();
      startSlideshow();
      return;
    }
    if (event.key === "Escape") {
      if (confirmRemove && confirmRemove.open) {
        event.preventDefault();
        confirmRemove.close();
        return;
      }
      if (confirmDeleteFile && confirmDeleteFile.open) {
        event.preventDefault();
        confirmDeleteFile.close();
        return;
      }
      if (addDialog.open) {
        return;
      }
      if (!slideshowEmpty.hidden) {
        hideSlideshowEmpty();
        event.preventDefault();
        return;
      }
      if (window.libraryGlobe && window.libraryGlobe.stopTour && window.libraryGlobe.stopTour()) {
        event.preventDefault();
        return;
      }
      if (!viewer.hidden && infoOpen()) {
        event.preventDefault();
        setInfoOpen(false);
        return;
      }
      if (stopSlideshow()) {
        event.preventDefault();
        return;
      }
      if (exitFullscreen()) {
        event.preventDefault();
        return;
      }
      if (!viewer.hidden) {
        closeViewer();
      }
      return;
    }
    if (event.key === "Delete" && !textFocused()) {
      if ((confirmRemove && confirmRemove.open) || (confirmDeleteFile && confirmDeleteFile.open)) {
        return;
      }
      const target = viewerItemId || selectedId;
      if (!target) {
        return;
      }
      event.preventDefault();
      askRemove(target);
      return;
    }
    if (textFocused()) {
      return;
    }
    const accel = event.ctrlKey || event.metaKey;
    if (!viewer.hidden && accel) {
      const plus = event.key === "+" || event.key === "=" || event.code === "Equal" || event.code === "NumpadAdd";
      const minus = event.key === "-" || event.key === "_" || event.code === "Minus" || event.code === "NumpadSubtract";
      if (plus) {
        event.preventDefault();
        zoomByStep(1);
        return;
      }
      if (minus) {
        event.preventDefault();
        zoomByStep(-1);
        return;
      }
      if (event.key === "0") {
        event.preventDefault();
        fitViewer();
        return;
      }
      if (event.key === "1") {
        event.preventDefault();
        zoomActual();
        return;
      }
      if (event.key === "r" || event.key === "R") {
        event.preventDefault();
        rotateDisplay();
        return;
      }
    }
    if (!viewer.hidden && !accel && !event.altKey && (event.key === "F11" || event.key === "f" || event.key === "F")) {
      event.preventDefault();
      toggleFullscreen();
      return;
    }
    if (viewer.hidden) {
      return;
    }
    if (event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      if (slideshowActive) {
        toggleSlideshowPause();
        return;
      }
      toggleViewerPlay();
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepViewer(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      stepViewer(1);
    }
  });

  document.addEventListener("mousedown", function (event) {
    if (event.button === 1) {
      event.preventDefault();
    }
  }, true);

  function startPan(event) {
    if (viewer.hidden) {
      return;
    }
    fitOnLoad = false;
    panning = true;
    panMoved = false;
    panLastX = event.clientX;
    panLastY = event.clientY;
  }

  viewer.addEventListener("mousedown", function (event) {
    if (viewer.hidden) {
      return;
    }
    if (event.button === 1) {
      event.preventDefault();
      startPan(event);
      return;
    }
    if (event.button !== 0) {
      return;
    }
    if (event.target.closest("button, input, label, a, select, textarea")) {
      return;
    }
    const item = syncViewerIndex();
    const still = !!(item && item.kind !== "video" && item.kind !== "live");
    if (!isZoomed() && !still) {
      return;
    }
    event.preventDefault();
    startPan(event);
  });
  window.addEventListener("mousemove", function (event) {
    if (!panning || viewer.hidden) {
      return;
    }
    event.preventDefault();
    const dx = event.clientX - panLastX;
    const dy = event.clientY - panLastY;
    if (dx || dy) {
      panMoved = true;
    }
    tx += dx;
    ty += dy;
    panLastX = event.clientX;
    panLastY = event.clientY;
    applyTransform();
  });
  window.addEventListener("mouseup", function () {
    panning = false;
  });
  viewer.addEventListener("auxclick", function (event) {
    if (event.button === 1) {
      event.preventDefault();
    }
  });
  viewerVideo.addEventListener("click", function (event) {
    event.preventDefault();
    if (panMoved) {
      panMoved = false;
      return;
    }
    toggleViewerPlay();
  });
  viewerVideo.addEventListener("timeupdate", syncViewerScrub);
  viewerVideo.addEventListener("durationchange", syncViewerScrub);
  viewerVideo.addEventListener("seeked", syncViewerScrub);
  if (viewerScrub) {
    viewerScrub.addEventListener("pointerdown", function () {
      scrubbingViewer = true;
    });
    viewerScrub.addEventListener("pointerup", function () {
      scrubbingViewer = false;
      syncViewerScrub();
    });
    viewerScrub.addEventListener("input", function () {
      if (!viewerVideo.duration || !isFinite(viewerVideo.duration)) {
        return;
      }
      viewerVideo.currentTime = (Number(viewerScrub.value) / 1000) * viewerVideo.duration;
    });
  }
  const viewerStage = document.getElementById("viewer-stage");
  if (viewerStage) {
    viewerStage.addEventListener("click", function (event) {
      if (event.target === viewerVideo) {
        return;
      }
      if (panMoved) {
        panMoved = false;
        return;
      }
      const item = syncViewerIndex();
      if (!item || item.kind !== "live") {
        return;
      }
      event.preventDefault();
      toggleViewerPlay();
    });
  }
  if (viewLibrary) {
    viewLibrary.addEventListener("click", function () {
      showView("library");
    });
  }
  if (viewGlobe) {
    viewGlobe.addEventListener("click", function () {
      showView("globe");
    });
  }

  window.libraryApp = {
    openCluster: openCluster,
    currentView: function () {
      return currentView;
    },
    slideshowState: function () {
      return {
        active: slideshowActive,
        paused: slideshowPaused,
        intervalMs: SLIDESHOW_MS,
      };
    },
    advanceSlideshow: function () {
      slideshowAdvance();
    },
    startSlideshow: startSlideshow,
    stopSlideshow: stopSlideshow,
  };

  viewerBack.addEventListener("click", function () {
    closeViewer();
  });
  viewerPrev.addEventListener("click", function () {
    stepViewer(-1);
  });
  viewerNext.addEventListener("click", function () {
    stepViewer(1);
  });
  viewerZoomSlider.addEventListener("input", function () {
    const stage = document.getElementById("viewer-stage") || viewer;
    const rect = stage.getBoundingClientRect();
    setZoomPercent(Number(viewerZoomSlider.value), rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  viewerRotate.addEventListener("click", function () {
    rotateDisplay();
  });
  viewerInfo.addEventListener("click", function (event) {
    event.stopPropagation();
    setInfoOpen(!infoOpen());
  });
  document.addEventListener("click", function (event) {
    if (!infoOpen()) {
      return;
    }
    const wrap = document.getElementById("viewer-info-wrap");
    if (wrap && wrap.contains(event.target)) {
      return;
    }
    setInfoOpen(false);
  });
  viewerSlideshow.addEventListener("click", function () {
    if (slideshowActive) {
      stopSlideshow();
      return;
    }
    startSlideshow();
  });
  viewerFullscreen.addEventListener("click", function () {
    toggleFullscreen();
  });
  document.addEventListener("fullscreenchange", function () {
    if (!document.fullscreenElement) {
      appFullscreen = false;
      fullscreenExitRequested = false;
    } else {
      appFullscreen = true;
      fullscreenExitRequested = false;
    }
    syncFullscreenChrome();
  });
  viewerFavorite.addEventListener("click", function () {
    const item = syncViewerIndex();
    if (!item) {
      return;
    }
    const next = !item.favorite;
    viewerFavorite.disabled = true;
    fetch("/api/items/" + encodeURIComponent(item.id) + "/favorite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ favorite: next }),
    }).then(readJson).then(function (updated) {
      viewerFavorite.disabled = false;
      const on = !!(updated && updated.favorite);
      setItemFavorite(item.id, on);
      if (viewerIndex >= 0 && items[viewerIndex] && items[viewerIndex].id === item.id) {
        items[viewerIndex] = updated;
        syncFavoriteChrome(updated);
      }
    }).catch(function () {
      viewerFavorite.disabled = false;
    });
  });
  revealOriginalBtn.addEventListener("click", function () {
    if (revealOriginalBtn.disabled) {
      return;
    }
    const item = syncViewerIndex();
    if (!item || item.available === false) {
      showRevealFailed();
      return;
    }
    fetch("/api/items/" + encodeURIComponent(item.id) + "/reveal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      clearRevealFailed();
    }).catch(function () {
      showRevealFailed();
    });
  });
  openOriginalBtn.addEventListener("click", function () {
    if (openOriginalBtn.disabled) {
      return;
    }
    const item = syncViewerIndex();
    if (!item || item.available === false) {
      showRevealFailed();
      return;
    }
    fetch("/api/items/" + encodeURIComponent(item.id) + "/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      clearRevealFailed();
    }).catch(function () {
      showRevealFailed();
    });
  });
  function applyVersion(body) {
    if (!libraryVersion) {
      return;
    }
    const sha = (body && (body.git_sha || body.revision || body.label)) || "";
    if (!sha) {
      libraryVersion.hidden = true;
      libraryVersion.textContent = "";
      libraryVersion.removeAttribute("title");
      return;
    }
    libraryVersion.hidden = false;
    libraryVersion.textContent = sha;
    const bits = [];
    if (body && body.git_branch) {
      bits.push(body.git_branch);
    }
    if (body && body.git_date) {
      bits.push(body.git_date);
    }
    if (body && body.git_subject) {
      bits.push(body.git_subject);
    }
    if (bits.length) {
      libraryVersion.title = bits.join(" · ");
    } else {
      libraryVersion.removeAttribute("title");
    }
  }

  function loadVersion() {
    fetch("/api/version").then(readJson).then(applyVersion).catch(function () {});
  }

  if (updateLibraryBtn) {
    updateLibraryBtn.addEventListener("click", function () {
      updateLibraryBtn.disabled = true;
      if (updateStatus) {
        updateStatus.hidden = false;
        updateStatus.textContent = "Updating…";
        updateStatus.removeAttribute("data-ok");
      }
      fetch("/api/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }).then(readJson).then(function (body) {
        updateLibraryBtn.disabled = false;
        if (updateStatus) {
          updateStatus.hidden = false;
          updateStatus.textContent = (body && body.message) || (body && body.updated ? "Updated" : "Already up to date");
          updateStatus.setAttribute("data-ok", body && body.ok ? "true" : "false");
        }
        if (body && body.ok) {
          applyVersion(body);
        } else {
          loadVersion();
        }
      }).catch(function (err) {
        updateLibraryBtn.disabled = false;
        if (updateStatus) {
          updateStatus.hidden = false;
          updateStatus.textContent = (err && err.body && err.body.error) || "update-unavailable";
          updateStatus.setAttribute("data-ok", "false");
        }
      });
    });
  }
  playPreviewBtn.addEventListener("click", function () {
    if (playPreviewBtn.disabled) {
      return;
    }
    const item = syncViewerIndex();
    if (!item || !proxyReady(item)) {
      return;
    }
    showViewerPlaceholder(false);
    viewerImage.hidden = true;
    resetViewerOriginal();
    showingOriginal = false;
    syncOriginalChrome();
    playOriginalOrProxy(item);
    if (viewerVideo.paused) {
      const play = viewerVideo.play();
      if (play && play.catch) {
        play.catch(function () {});
      }
    } else {
      viewerVideo.pause();
    }
  });

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(applySearchFromBox, 150);
    });
    searchInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        window.clearTimeout(searchTimer);
        applySearchFromBox();
      }
    });
  }
  if (searchChips) {
    searchChips.querySelectorAll("button[data-scope]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const scope = btn.getAttribute("data-scope") || "";
        filter.scope = filter.scope === scope ? "" : scope;
        filter.person = "";
        filter.place = "";
        filter.thing = "";
        hideInspector();
        syncChips();
        syncFilterDataset();
        renderKey = "";
        loadCatalog();
      });
    });
  }
  function bindAnnotateField(field, kind) {
    if (!field) {
      return;
    }
    field.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        commitAnnotate(field, kind);
      }
    });
    field.addEventListener("blur", function () {
      commitAnnotate(field, kind);
    });
  }
  bindAnnotateField(personField, "person");
  bindAnnotateField(placeField, "place");
  bindAnnotateField(thingField, "thing");

  document.body.dataset.view = "library";

  var skipHistory = false;

  function liveHref(hash) {
    return (window.location.pathname || "/") + (window.location.search || "") + (hash || "");
  }

  function stayOnLiveOrigin(state, hash, replace) {
    var next = state || { library: true, view: "grid" };
    try {
      if (replace) {
        history.replaceState(next, "", liveHref(hash));
      } else {
        history.pushState(next, "", liveHref(hash));
      }
    } catch (err) {}
  }

  stayOnLiveOrigin({ library: true, view: "grid" }, "", true);
  stayOnLiveOrigin({ library: true, view: "grid" }, "", false);

  window.addEventListener("popstate", function (event) {
    var state = event.state;
    if (!state || !state.library) {
      stayOnLiveOrigin(
        { library: true, view: viewer.hidden ? "grid" : "viewer", id: viewerItemId },
        viewer.hidden ? "" : ("#item/" + encodeURIComponent(viewerItemId || "")),
        false
      );
      return;
    }
    skipHistory = true;
    try {
      if (state.view === "viewer" && state.id) {
        if (viewer.hidden || viewerItemId !== state.id) {
          openViewer(state.id);
        }
      } else if (!viewer.hidden) {
        closeViewer();
      } else {
        stayOnLiveOrigin({ library: true, view: "grid" }, "", false);
      }
    } finally {
      skipHistory = false;
    }
  });

  fetch("/api/settings").then(readJson).then(function (data) {
    applySettings(data);
    syncPresentableSort();
    gridSize = DEFAULT_SIZE[settings.zoomLevel] != null ? DEFAULT_SIZE[settings.zoomLevel] : 0;
    applyGridMetrics();
    showDisconnected(false);
    loadVersion();
    return loadCatalog();
  }).catch(function () {
    showDisconnected(true);
    loadVersion();
    return loadCatalog();
  });

  pollTimer = window.setInterval(function () {
    fetch("/api/health").then(function (res) {
      if (!res.ok) {
        showDisconnected(true);
        return;
      }
      showDisconnected(false);
      return loadCatalog();
    }).catch(function () {
      showDisconnected(true);
    });
  }, 1000);
  window.addEventListener("beforeunload", function () {
    window.clearInterval(pollTimer);
  });
})();
