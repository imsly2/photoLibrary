(function () {
  const main = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  const viewerOriginal = document.getElementById("viewer-original");
  const viewerVideo = document.getElementById("viewer-video");
  const viewerBack = document.getElementById("viewer-back");
  const unavailableBanner = document.getElementById("unavailable-banner");
  const viewerPlaceholder = document.getElementById("viewer-placeholder");
  const openOriginalBtn = document.getElementById("open-original");
  const playPreviewBtn = document.getElementById("play-preview");
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
  const zoomSlider = document.getElementById("zoom-slider");
  const sizeSlider = document.getElementById("size-slider");
  const filterVideos = document.getElementById("filter-videos");
  const groupDatesBtn = document.getElementById("group-dates");
  const scanStatus = document.getElementById("scan-status");
  const viewLibrary = document.getElementById("view-library");
  const viewGlobe = document.getElementById("view-globe");
  const workspace = document.querySelector(".workspace");
  const globeView = document.getElementById("globe-view");
  if (!main || !viewer || !viewerImage || !viewerVideo || !addFolderBtn || !addDialog) {
    return;
  }
  if (!unavailableBanner || !viewerPlaceholder || !openOriginalBtn || !playPreviewBtn || !viewerBack) {
    return;
  }

  const PLACEHOLDER = "Preview is not available";
  const LEVELS = ["years", "months", "days", "all"];
  const SIZE_STEPS = [72, 104, 144, 192, 256, 336, 420, 520];
  const DEFAULT_SIZE = { years: 0, months: 1, days: 3, all: 6 };
  const HEART_MIN = 144;
  const EMPTY = "No pictures yet";
  const EMPTY_SEARCH = "No matching pictures";
  const PLAY_ICON = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 2.1v7.8L10.2 6z"/></svg>';
  const HEART_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.4S2.6 10 1.5 7.1C.6 5.1 1.6 3 3.8 3c1.2 0 2 .7 2.3 1.2C6.4 3.7 7.2 3 8.4 3c2.2 0 3.2 2.1 2.3 4.1C9.6 10 8 13.4 8 13.4z"/></svg>';

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
  let savedFilter = { q: "", scope: "", person: "", place: "", thing: "", kind: "" };
  let savedSearch = "";
  let filter = { q: "", scope: "", person: "", place: "", thing: "", kind: "" };
  let gridSize = 0;
  let groupDates = true;
  let favoritesOpen = true;
  let searchTimer = 0;
  let annotateBusy = false;
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
  let currentView = "library";

  function levelIndex(level) {
    const idx = LEVELS.indexOf(level);
    return idx === -1 ? 0 : idx;
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
    return !!(filter.q || filter.scope || filter.person || filter.place || filter.thing || filter.kind);
  }

  function copyFilter(src) {
    return {
      q: src.q || "",
      scope: src.scope || "",
      person: src.person || "",
      place: src.place || "",
      thing: src.thing || "",
      kind: src.kind || "",
    };
  }

  function filtersEqual(a, b) {
    return a.q === b.q && a.scope === b.scope && a.person === b.person && a.place === b.place && a.thing === b.thing && a.kind === b.kind;
  }

  function syncFilterDataset() {
    main.dataset.q = filter.q;
    main.dataset.scope = filter.scope;
    main.dataset.person = filter.person;
    main.dataset.place = filter.place;
    main.dataset.thing = filter.thing;
    main.dataset.kind = filter.kind;
    if (filterVideos) {
      filterVideos.setAttribute("aria-pressed", filter.kind === "video" ? "true" : "false");
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
      hoverCell = null;
    }
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
    video.src = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
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

  function applyTransform() {
    const transform = "translate(" + tx + "px, " + ty + "px) scale(" + scale + ")";
    viewerImage.style.transformOrigin = "0 0";
    viewerImage.style.transform = transform;
    viewerImage.style.width = naturalW + "px";
    viewerImage.style.height = naturalH + "px";
    if (viewerOriginal) {
      viewerOriginal.style.transformOrigin = "0 0";
      viewerOriginal.style.transform = transform;
      viewerOriginal.style.width = naturalW + "px";
      viewerOriginal.style.height = naturalH + "px";
    }
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
    viewerVideo.pause();
    viewerVideo.removeAttribute("src");
    viewerVideo.removeAttribute("poster");
    viewerVideo.removeAttribute("data-source-ready");
    viewerVideo.removeAttribute("data-using-proxy");
    viewerVideo.load();
    viewerVideo.hidden = true;
  }

  function loadViewerOriginal(item) {
    if (!viewerOriginal || !item || item.available === false || item.kind === "video") {
      resetViewerOriginal();
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
        applyTransform();
      };
      viewerOriginal.onerror = function () {
        resetViewerOriginal();
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

  function syncViewerChrome(item) {
    const available = !!(item && item.available);
    unavailableBanner.hidden = available;
    openOriginalBtn.disabled = !available;
    playPreviewBtn.disabled = true;
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
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
    viewerImage.hidden = false;
    resetViewerOriginal();
    resetViewerVideo();
    unavailableBanner.hidden = true;
    viewerPlaceholder.hidden = true;
    openOriginalBtn.disabled = true;
    playPreviewBtn.disabled = true;
    viewerIndex = -1;
    viewerItemId = null;
    panning = false;
    clearAnnotateError();
    clearAnnotateFields();
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
    applyFilterState(restoreFilter, restoreSearch);
    function finish() {
      refreshInspectorFromItems();
      window.requestAnimationFrame(function () {
        main.scrollTop = restoreScroll;
      });
    }
    if (settings.zoomLevel !== restoreLevel) {
      setLevel(restoreLevel, true).then(finish);
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
  }

  function openStillViewer(item, index) {
    resetViewerVideo();
    resetViewerOriginal();
    syncViewerChrome(item);
    renderViewerLabels(item);
    const url = "/api/media/" + encodeURIComponent(item.id) + "?which=preview";
    const same = viewerItemId === item.id && !viewer.hidden && viewerImage.getAttribute("src") === url;
    viewerIndex = index;
    viewerItemId = item.id;
    viewer.hidden = false;
    viewerImage.draggable = false;
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

  function openVideoViewer(item, index) {
    viewerImage.removeAttribute("src");
    viewerImage.hidden = true;
    resetViewerOriginal();
    resetViewerVideo();
    syncViewerChrome(item);
    renderViewerLabels(item);
    viewerIndex = index;
    viewerItemId = item.id;
    viewer.hidden = false;
    if (!stillPreviewReady(item)) {
      showViewerPlaceholder(true);
      viewerVideo.hidden = true;
      return;
    }
    showViewerPlaceholder(false);
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
    savedFilter = copyFilter(filter);
    savedSearch = searchInput ? searchInput.value : filter.q;
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

  function currentCellSize() {
    return SIZE_STEPS[gridSize] || SIZE_STEPS[0];
  }

  function applyGridMetrics() {
    const level = settings.zoomLevel;
    const size = currentCellSize();
    main.dataset.level = level;
    main.dataset.size = String(size);
    main.dataset.groupDates = groupDates ? "on" : "off";
    main.dataset.hearts = size >= HEART_MIN ? "on" : "off";
    main.className = "level-" + level + (groupDates ? "" : " wall");
    main.style.setProperty("--cell", size + "px");
    zoomSlider.value = String(levelIndex(level));
    if (sizeSlider) {
      sizeSlider.value = String(gridSize);
    }
    if (groupDatesBtn) {
      groupDatesBtn.setAttribute("aria-pressed", groupDates ? "true" : "false");
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
    sortSelect.value = settings.sort;
    dirSelect.value = settings.dir;
    syncFilterDataset();
    if (!items.length) {
      stopHover();
      main.innerHTML = "<p>" + (hasActiveFilter() ? EMPTY_SEARCH : EMPTY) + "</p>";
      applyGridMetrics();
      renderKey = hasActiveFilter() ? "empty-search" : "empty";
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
    const mosaic = level === "years" || level === "months";
    const fragment = document.createDocumentFragment();
    const fav = makeFavoritesSection(existing, mosaic);
    if (fav) {
      fragment.appendChild(fav);
    }
    if (!groupDates) {
      const list = document.createElement("div");
      list.className = (mosaic ? "mosaic" : "item-list") + " wall-list";
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
      const open = syncViewerIndex();
      if (open) {
        renderViewerLabels(open);
      }
      render();
      if (filter.person || filter.place || filter.thing) {
        refreshInspectorFromItems();
      }
    });
  }

  function setLevel(level, persistChange) {
    if (LEVELS.indexOf(level) === -1) {
      return Promise.resolve();
    }
    const same = level === settings.zoomLevel;
    const anchor = visibleAnchorId();
    settings.zoomLevel = level;
    gridSize = DEFAULT_SIZE[level] != null ? DEFAULT_SIZE[level] : 0;
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
    });
  }

  function setGridSize(index) {
    const next = Math.max(0, Math.min(SIZE_STEPS.length - 1, Number(index)));
    if (next === gridSize) {
      applyGridMetrics();
      return;
    }
    gridSize = next;
    applyGridMetrics();
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

  function filterByEntity(kind, id) {
    if (!id) {
      return;
    }
    filter.q = "";
    filter.scope = "";
    filter.person = "";
    filter.place = "";
    filter.thing = "";
    filter.kind = filter.kind || "";
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
    const keepId = viewerItemId;
    return loadCatalog().then(function () {
      refreshInspectorFromItems();
      if (keepId && !viewer.hidden) {
        const index = items.findIndex(function (item) {
          return item.id === keepId;
        });
        if (index >= 0) {
          viewerIndex = index;
          viewerItemId = keepId;
          renderViewerLabels(items[index]);
        }
      }
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
  if (sizeSlider) {
    sizeSlider.addEventListener("input", function () {
      setGridSize(Number(sizeSlider.value));
    });
  }
  if (filterVideos) {
    filterVideos.addEventListener("click", function () {
      filter.kind = filter.kind === "video" ? "" : "video";
      syncFilterDataset();
      renderKey = "";
      loadCatalog();
    });
  }
  if (groupDatesBtn) {
    groupDatesBtn.addEventListener("click", function () {
      groupDates = !groupDates;
      applyGridMetrics();
      renderKey = "";
      render();
    });
  }

  window.addEventListener("wheel", function (event) {
    if (!event.ctrlKey) {
      return;
    }
    event.preventDefault();
    if (!viewer.hidden) {
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
    if (event.key === "Escape") {
      if (addDialog.open) {
        return;
      }
      if (window.libraryGlobe && window.libraryGlobe.stopTour && window.libraryGlobe.stopTour()) {
        event.preventDefault();
        return;
      }
      if (!viewer.hidden) {
        closeViewer();
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
      syncViewerIndex();
      if (viewerIndex > 0) {
        openViewerAt(viewerIndex - 1);
      }
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      syncViewerIndex();
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
  const viewerStage = document.getElementById("viewer-stage");
  if (viewerStage) {
    viewerStage.addEventListener("click", function (event) {
      if (event.target === viewerVideo) {
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
  };

  viewerBack.addEventListener("click", function () {
    closeViewer();
  });
  openOriginalBtn.addEventListener("click", function () {
    if (openOriginalBtn.disabled) {
      return;
    }
    const item = syncViewerIndex();
    if (!item || item.available === false) {
      return;
    }
    const originalUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=original";
    if (item.kind === "video") {
      playOriginalOrProxy(item);
      const play = viewerVideo.play();
      if (play && play.catch) {
        play.catch(function () {});
      }
      return;
    }
    showViewerPlaceholder(false);
    viewerImage.hidden = false;
    viewerImage.src = originalUrl;
  });
  playPreviewBtn.addEventListener("click", function () {
    if (playPreviewBtn.disabled) {
      return;
    }
    const item = syncViewerIndex();
    if (!item || !proxyReady(item)) {
      return;
    }
    const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    resetViewerVideo();
    showViewerPlaceholder(false);
    viewerImage.hidden = true;
    resetViewerOriginal();
    viewerVideo.hidden = false;
    viewerVideo.setAttribute("data-using-proxy", "1");
    viewerVideo.setAttribute("data-source-ready", item.id);
    viewerVideo.src = proxyUrl;
    const play = viewerVideo.play();
    if (play && play.catch) {
      play.catch(function () {});
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

  fetch("/api/settings").then(readJson).then(function (data) {
    applySettings(data);
    sortSelect.value = settings.sort;
    dirSelect.value = settings.dir;
    gridSize = DEFAULT_SIZE[settings.zoomLevel] != null ? DEFAULT_SIZE[settings.zoomLevel] : 0;
    applyGridMetrics();
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
