(function () {
  const main = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  const viewerOriginal = document.getElementById("viewer-original");
  const viewerVideo = document.getElementById("viewer-video");
  const viewerBack = document.getElementById("viewer-back");
  const viewerCrumb = document.getElementById("viewer-crumb");
  const viewerSource = document.getElementById("viewer-source");
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
  const viewerMute = document.getElementById("viewer-mute");
  const viewerVolumeSlider = document.getElementById("viewer-volume");
  const updateLibraryBtn = document.getElementById("update-library");
  const updateStatus = document.getElementById("update-status");
  const libraryVersion = document.getElementById("library-version");
  const searchInput = document.getElementById("search");
  const searchChips = document.getElementById("search-chips");
  const languageSelect = document.getElementById("language");
  const I18N = window.LibraryI18n || {
    t: function (key) { return key; },
    setLanguage: function () { return "en"; },
    getLanguage: function () { return "en"; },
    applyStatic: function () {},
    queueLabel: function (id, fallback) { return fallback || id; },
    formatDateGroup: function (key) { return key; },
    normalize: function (code) { return code === "zh-Hans" ? "zh-Hans" : "en"; },
  };
  function t(key, vars) {
    return I18N.t(key, vars);
  }
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
  const filterBar = document.getElementById("filter-bar");
  const activeFilters = document.getElementById("active-filters");
  const clearFiltersBtn = document.getElementById("clear-filters");
  const arrangeSelect = document.getElementById("arrange");
  const tagNewInput = document.getElementById("tag-new");
  const tagCreateBtn = document.getElementById("tag-create");
  const tagPick = document.getElementById("tag-pick");
  const tagApplyBtn = document.getElementById("tag-apply");
  const tagRemoveBtn = document.getElementById("tag-remove");
  const tagsList = document.getElementById("tags-list");
  const tagsEmpty = document.getElementById("tags-empty");
  const viewerTags = document.getElementById("viewer-tags");
  const removeItemBtn = document.getElementById("remove-item");
  const deleteFileBtn = document.getElementById("delete-file");
  const selectionBar = document.getElementById("selection-bar");
  const selectionCount = document.getElementById("selection-count");
  const selectionFavoriteBtn = document.getElementById("selection-favorite");
  const selectionCompareBtn = document.getElementById("selection-compare");
  const selectionMoveBtn = document.getElementById("selection-move");
  const selectionRemoveBtn = document.getElementById("selection-remove");
  const selectionClearBtn = document.getElementById("selection-clear");
  const moveFolder = document.getElementById("move-folder");
  const moveFolderSources = document.getElementById("move-folder-sources");
  const moveFolderPath = document.getElementById("move-folder-path");
  const moveFolderBrowse = document.getElementById("move-folder-browse");
  const moveFolderConfirm = document.getElementById("move-folder-confirm");
  const moveFolderError = document.getElementById("move-folder-error");
  const moveFolderReport = document.getElementById("move-folder-report");
  const moveFolderCancel = document.getElementById("move-folder-cancel");
  const moveFolderOk = document.getElementById("move-folder-ok");
  const filterDuplicatesBtn = document.getElementById("filter-duplicates");
  const duplicateCompare = document.getElementById("duplicate-compare");
  const duplicateCompareSides = document.getElementById("duplicate-compare-sides");
  const duplicateCompareEmpty = document.getElementById("duplicate-compare-empty");
  const duplicateCompareMeta = document.getElementById("duplicate-compare-meta");
  const duplicateCompareNav = document.getElementById("duplicate-compare-nav");
  const duplicateCompareIndex = document.getElementById("duplicate-compare-index");
  const duplicateComparePrev = document.getElementById("duplicate-compare-prev");
  const duplicateCompareNext = document.getElementById("duplicate-compare-next");
  const duplicateCompareApply = document.getElementById("duplicate-compare-apply");
  const duplicateCompareCancel = document.getElementById("duplicate-compare-cancel");
  const confirmRemoveTitle = document.getElementById("confirm-remove-title");
  const confirmRemoveHelp = document.getElementById("confirm-remove-help");
  const scanStatus = document.getElementById("scan-status");
  const scanStatusText = document.getElementById("scan-status-text");
  const scanErrorText = document.getElementById("scan-error-text");
  const scanRetry = document.getElementById("scan-retry");
  const confirmRemove = document.getElementById("confirm-remove");
  const confirmDeleteFile = document.getElementById("confirm-delete-file");
  const viewLibrary = document.getElementById("view-library");
  const viewGlobe = document.getElementById("view-globe");
  const viewSettings = document.getElementById("view-settings");
  const settingsView = document.getElementById("settings-view");
  const settingsSources = document.getElementById("settings-sources");
  const settingsSourcesEmpty = document.getElementById("settings-sources-empty");
  const settingsAddFolder = document.getElementById("settings-add-folder");
  const settingsRenditionNote = document.getElementById("settings-rendition-note");
  const confirmRemoveSource = document.getElementById("confirm-remove-source");
  const workspace = document.querySelector(".workspace");
  const globeView = document.getElementById("globe-view");
  const librarySide = document.getElementById("library-side");
  const librarySplitter = document.getElementById("library-splitter");
  const sideCollapse = document.getElementById("side-collapse");
  const peopleToggle = document.getElementById("people-toggle");
  const tagsToggle = document.getElementById("tags-toggle");
  const sideVsplit = document.getElementById("side-vsplit");
  const peopleList = document.getElementById("people-list");
  const peopleEmpty = document.getElementById("people-empty");
  const personProfile = document.getElementById("person-profile");
  const personNameInput = document.getElementById("person-name");
  const personFaces = document.getElementById("person-faces");
  const peopleMergeBtn = document.getElementById("people-merge");
  const confirmMerge = document.getElementById("confirm-merge");
  const confirmMergeTitle = document.getElementById("confirm-merge-title");
  const confirmMergeHelp = document.getElementById("confirm-merge-help");
  const viewerFaceCrops = document.getElementById("viewer-face-crops");
  const jobsStatus = document.getElementById("jobs-status");
  const jobsQueues = document.getElementById("jobs-queues");
  const jobsPause = document.getElementById("jobs-pause");
  const jobsResume = document.getElementById("jobs-resume");
  const jobsRerunFaces = document.getElementById("jobs-rerun-faces");
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
  const PLAY_ICON = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 2.1v7.8L10.2 6z"/></svg>';
  const HEART_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.4S2.6 10 1.5 7.1C.6 5.1 1.6 3 3.8 3c1.2 0 2 .7 2.3 1.2C6.4 3.7 7.2 3 8.4 3c2.2 0 3.2 2.1 2.3 4.1C9.6 10 8 13.4 8 13.4z"/></svg>';
  const SLIDESHOW_MS = 5000;

  let settings = {
    sort: "date",
    dir: "desc",
    zoomLevel: "years",
    addFolderDefault: "ask",
    playProxies: "days-and-all",
    language: "en",
  };
  let language = "en";
  let catalogInFlight = null;
  let catalogQueued = false;
  let catalogReady = false;
  let lastJobs = null;
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
  let pendingRemoveIds = [];
  let lastSources = [];
  let gridSize = 0;
  let groupDates = true;
  let favoritesOpen = true;
  let togetherOpen = true;
  let togetherSolosOpen = {};
  let extraById = {};
  let togetherByPerson = {};
  let pendingMerge = null;
  let peopleCatalog = [];
  let pendingThumb = null;
  let personOfInterestMin = 3;
  let tagsCatalog = [];
  let arrangeBy = "dates";
  let collapsedGroups = {};
  let selectedIds = [];
  let lastClickedId = null;
  let compareGroups = [];
  let compareIndex = 0;
  let compareChoices = {};
  let sideOpen = true;
  let sideWidth = 264;
  let splitDragging = false;
  let vSplitDragging = false;
  let peopleOpen = true;
  let tagsOpen = false;
  let peopleShare = 0.62;
  let searchTimer = 0;
  let annotateBusy = false;
  let namingPersonId = "";
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
  let originalSwapTimer = 0;
  let videoSourceState = "";
  let viewerWantPlay = false;
  const ORIGINAL_SWAP_MS = 20000;
  const PLAYBACK_WAIT_MS = 90000;
  const PLAYBACK_POLL_MS = 750;
  function sourceLabel(state) {
    if (state === "loading") {
      return t("loadingFull");
    }
    if (state === "original") {
      return t("original");
    }
    if (state === "full") {
      return t("full");
    }
    if (state === "unavailable") {
      return t("previewFullUnavailable");
    }
    return t("preview");
  }
  let scrubbingViewer = false;
  let showingOriginal = false;
  let fitOnLoad = false;
  const MIN_ZOOM_FACTOR = 0.25;
  const MAX_ZOOM_FACTOR = 16;
  let renderKey = "";
  let loadGen = 0;
  let currentView = "library";
  let previousView = "library";
  let pendingSourceId = "";
  let settingsWired = false;
  let facesRerunNeeded = false;
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
      return t("noMatchesFor", { q: q });
    }
    return t("noMatches");
  }

  function catalogLooksPopulated() {
    if (lastSources.length) {
      return true;
    }
    if (peopleCatalog.some(function (person) { return person && person.visible !== false; })) {
      return true;
    }
    return tagsCatalog.length > 0;
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

  function selectedPeople() {
    return (filter.person || "").split(",").filter(Boolean);
  }

  function selectedThings() {
    return (filter.thing || "").split(",").filter(Boolean);
  }

  function selectedPlaces() {
    return (filter.place || "").split(",").filter(Boolean);
  }

  function csvWithout(csv, token) {
    return (csv || "").split(",").filter(function (part) {
      return part && part !== token;
    }).join(",");
  }

  function csvToggle(csv, token, additive) {
    const parts = (csv || "").split(",").filter(Boolean);
    const idx = parts.indexOf(token);
    if (additive) {
      if (idx >= 0) {
        parts.splice(idx, 1);
      } else {
        parts.push(token);
      }
      return parts.join(",");
    }
    if (idx >= 0) {
      parts.splice(idx, 1);
      return parts.join(",");
    }
    return token;
  }

  function entityName(kind, id) {
    if (!id) {
      return "";
    }
    if (kind === "person") {
      for (let i = 0; i < peopleCatalog.length; i += 1) {
        if (peopleCatalog[i].id === id) {
          return personDisplayName(peopleCatalog[i]);
        }
      }
    }
    if (kind === "thing") {
      for (let i = 0; i < tagsCatalog.length; i += 1) {
        if (tagsCatalog[i].id === id) {
          return tagsCatalog[i].name || id;
        }
      }
    }
    for (let i = 0; i < items.length; i += 1) {
      const entities = (items[i] && items[i].entities) || {};
      const list = kind === "person" ? entities.people : kind === "place" ? entities.places : entities.things;
      for (let j = 0; j < (list || []).length; j += 1) {
        if (list[j] && list[j].id === id) {
          return list[j].name || (kind === "person" ? t("unnamed") : id);
        }
      }
    }
    return id;
  }

  function renderActiveFilters() {
    if (!activeFilters) {
      return;
    }
    activeFilters.innerHTML = "";
    function addChip(kind, id, label) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "filter-chip";
      btn.dataset.kind = kind;
      btn.dataset.id = id;
      btn.setAttribute("aria-label", t("removeLabel", { name: label }));
      btn.textContent = label + " ";
      const x = document.createElement("span");
      x.className = "chip-x";
      x.setAttribute("aria-hidden", "true");
      x.textContent = "x";
      btn.appendChild(x);
      btn.addEventListener("click", function () {
        removeFilterToken(kind, id);
      });
      activeFilters.appendChild(btn);
    }
    selectedPeople().forEach(function (id) {
      addChip("person", id, t("personChip", { name: entityName("person", id) }));
    });
    selectedPlaces().forEach(function (id) {
      addChip("place", id, t("placeChip", { name: entityName("place", id) }));
    });
    selectedThings().forEach(function (id) {
      addChip("thing", id, t("tagChip", { name: entityName("thing", id) }));
    });
    if (filter.q) {
      addChip("q", filter.q, t("searchChip", { q: filter.q }));
    }
    if (filter.scope) {
      addChip("scope", filter.scope, t("scopeChip", { name: t(filter.scope) }));
    }
    const hasEntity = !!(filter.person || filter.place || filter.thing || filter.q || filter.scope || filter.kind || filter.favorite);
    if (clearFiltersBtn) {
      clearFiltersBtn.hidden = !hasEntity;
    }
    if (filterBar) {
      filterBar.dataset.active = hasEntity ? "1" : "0";
    }
  }

  function removeFilterToken(kind, token) {
    const next = copyFilter(filter);
    if (kind === "person") {
      next.person = csvWithout(next.person, token);
    } else if (kind === "place") {
      next.place = csvWithout(next.place, token);
    } else if (kind === "thing") {
      next.thing = csvWithout(next.thing, token);
    } else if (kind === "q") {
      next.q = "";
    } else if (kind === "scope") {
      next.scope = "";
    }
    applyFilterState(next, next.q);
    renderKey = "";
    loadCatalog();
  }

  function clearAllFilters() {
    applyFilterState({ q: "", scope: "", person: "", place: "", thing: "", kind: "", favorite: "" }, "");
    renderKey = "";
    return loadCatalog();
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
    renderActiveFilters();
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

  function selectionFavoriteOn() {
    const ids = selectedIds.length ? selectedIds : selectedItemIds();
    if (!ids.length) {
      return true;
    }
    return !ids.every(function (id) {
      return !!(itemById(id) && itemById(id).favorite);
    });
  }

  function syncRemoveConfirm() {
    const n = pendingRemoveIds.length || (pendingRemoveId ? 1 : 0);
    if (confirmRemoveTitle) {
      confirmRemoveTitle.textContent = n > 1 ? t("removeTitleMany", { n: n }) : t("removeTitle");
    }
    if (confirmRemoveHelp) {
      confirmRemoveHelp.textContent = n > 1 ? t("removeHelpMany") : t("removeHelp");
    }
  }

  function syncSelectionChrome() {
    const ids = selectedIds.slice();
    const viewerOpen = !!(viewer && !viewer.hidden);
    const showBar = ids.length >= 1 && !viewerOpen && currentView === "library";
    if (selectionBar) {
      selectionBar.hidden = !showBar;
    }
    if (selectionCount) {
      selectionCount.textContent = t("selectedCount", { n: ids.length });
    }
    if (selectionFavoriteBtn) {
      const on = selectionFavoriteOn();
      selectionFavoriteBtn.textContent = on ? t("favorite") : t("unfavorite");
      selectionFavoriteBtn.setAttribute("aria-pressed", on ? "false" : "true");
      selectionFavoriteBtn.disabled = !ids.length;
    }
    if (selectionMoveBtn) {
      selectionMoveBtn.disabled = !ids.length;
    }
    if (selectionRemoveBtn) {
      selectionRemoveBtn.disabled = !ids.length;
    }
    if (selectionCompareBtn) {
      const canCompare = ids.length >= 2 && !viewerOpen && currentView === "library";
      selectionCompareBtn.hidden = !canCompare;
      selectionCompareBtn.disabled = !canCompare;
    }
    const id = viewerItemId || selectedId || (ids.length === 1 ? ids[0] : null);
    if (removeItemBtn) {
      removeItemBtn.disabled = !(viewerItemId || ids.length || selectedId);
    }
    if (deleteFileBtn) {
      deleteFileBtn.disabled = !id || (!viewerItemId && ids.length > 1);
    }
  }

  function clearSelection() {
    selectedIds = [];
    selectedId = null;
    lastClickedId = null;
    paintSelection();
    syncSelectionChrome();
  }

  function pruneSelection() {
    const live = {};
    items.forEach(function (item) {
      live[item.id] = true;
    });
    Object.keys(extraById).forEach(function (id) {
      live[id] = true;
    });
    selectedIds = selectedIds.filter(function (id) {
      return live[id];
    });
    if (selectedId && !live[selectedId]) {
      selectedId = selectedIds.length ? selectedIds[selectedIds.length - 1] : null;
    }
    if (lastClickedId && !live[lastClickedId]) {
      lastClickedId = selectedId;
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
    inspectorName.textContent = name || (kind === "person" ? t("unnamed") : "");
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
        if (rec && rec.id === id) {
          name = rec.name || (kind === "person" ? t("unnamed") : "");
        }
      });
    });
    showInspector(kind, id, name, items);
  }

  function showView(name) {
    if (name !== "library" && name !== "globe" && name !== "settings") {
      return;
    }
    if (name === "globe" && viewer && !viewer.hidden) {
      hideViewerChrome();
    }
    if (name === "settings" && viewer && !viewer.hidden) {
      hideViewerChrome();
    }
    if (currentView !== name && currentView !== "settings") {
      previousView = currentView;
    }
    currentView = name;
    document.body.dataset.view = name;
    if (workspace) {
      workspace.hidden = name !== "library";
    }
    if (filterBar) {
      filterBar.hidden = name !== "library";
    }
    if (globeView) {
      globeView.hidden = name !== "globe";
    }
    if (settingsView) {
      settingsView.hidden = name !== "settings";
    }
    if (viewLibrary) {
      viewLibrary.setAttribute("aria-pressed", name === "library" ? "true" : "false");
    }
    if (viewGlobe) {
      viewGlobe.setAttribute("aria-pressed", name === "globe" ? "true" : "false");
    }
    if (viewSettings) {
      viewSettings.setAttribute("aria-pressed", name === "settings" ? "true" : "false");
    }
    if (window.libraryGlobe && window.libraryGlobe.setActive) {
      window.libraryGlobe.setActive(name === "globe");
    }
    if (name === "library") {
      renderKey = "";
      loadCatalog();
    }
    if (name === "settings") {
      renderSettingsSources(lastSources);
      fillSettingsForm(settings);
    }
    syncSelectionChrome();
  }

  function openSettings() {
    hideSlideshowEmpty();
    showView("settings");
    fetch("/api/settings").then(readJson).then(function (data) {
      applySettings(data);
      fillSettingsForm(data);
    }).catch(function () {});
    fetch("/api/sources").then(readJson).then(function (sources) {
      lastSources = Array.isArray(sources) ? sources : [];
      renderSettingsSources(lastSources);
    }).catch(function () {});
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
    renderPeople();
    renderTags();
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

  function applyLanguage(next, persistChange) {
    const lang = I18N.normalize(next);
    const changed = lang !== language;
    language = lang;
    settings.language = lang;
    I18N.setLanguage(lang);
    if (languageSelect && languageSelect.value !== lang) {
      languageSelect.value = lang;
    }
    document.title = t("library");
    if (slideshowEmpty) {
      slideshowEmpty.textContent = t("addPhotosFirst");
    }
    if (viewerPlaceholder) {
      viewerPlaceholder.textContent = t("previewUnavailable");
    }
    if (unavailableBanner) {
      unavailableBanner.textContent = t("originalMissing");
    }
    if (revealError) {
      revealError.textContent = t("originalMissing");
    }
    if (disconnectedBanner) {
      disconnectedBanner.textContent = t("disconnected");
    }
    const globeEmpty = document.getElementById("globe-empty");
    if (globeEmpty) {
      globeEmpty.textContent = t("noLocations");
    }
    renderKey = "";
    renderPeople();
    renderTags();
    applySectionLayout();
    if (lastJobs) {
      renderJobs(lastJobs);
    }
    render();
    if (compareOpen()) {
      paintCompare();
    }
    if (!viewer.hidden && infoOpen() && viewerItemId) {
      const openItem = findItemById(viewerItemId);
      if (openItem) {
        renderFacts(openItem);
      }
    }
    if (currentView === "settings") {
      renderSettingsSources(lastSources);
      fillSettingsForm(settings);
    }
    if (persistChange && changed) {
      return persist({ language: lang });
    }
    return Promise.resolve();
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
    settings.previewStore = data.previewStore || settings.previewStore;
    settings.unavailableItems = data.unavailableItems || settings.unavailableItems;
    settings.listenHost = data.listenHost || settings.listenHost;
    settings.port = data.port != null ? data.port : settings.port;
    settings.thumbPx = data.thumbPx != null ? data.thumbPx : settings.thumbPx;
    settings.previewPx = data.previewPx != null ? data.previewPx : settings.previewPx;
    settings.proxyWidth = data.proxyWidth != null ? data.proxyWidth : settings.proxyWidth;
    settings.placeMatchMeters = data.placeMatchMeters != null ? data.placeMatchMeters : settings.placeMatchMeters;
    settings.tourOrbitSec = data.tourOrbitSec != null ? data.tourOrbitSec : settings.tourOrbitSec;
    settings.tourPictures = data.tourPictures != null ? data.tourPictures : settings.tourPictures;
    settings.tourPictureSec = data.tourPictureSec != null ? data.tourPictureSec : settings.tourPictureSec;
    settings.faceMatchThreshold = data.faceMatchThreshold != null ? data.faceMatchThreshold : settings.faceMatchThreshold;
    settings.faceMinSidePx = data.faceMinSidePx != null ? data.faceMinSidePx : settings.faceMinSidePx;
    if (data.language) {
      settings.language = I18N.normalize(data.language);
    }
    main.dataset.playProxies = settings.playProxies;
    syncPresentableSort();
    if (settings.language && settings.language !== language) {
      applyLanguage(settings.language, false);
    } else if (languageSelect && languageSelect.value !== language) {
      languageSelect.value = language;
    }
    if (currentView === "settings") {
      fillSettingsForm(data);
    }
  }

  function setRadioGroup(name, value) {
    document.querySelectorAll('input[name="' + name + '"]').forEach(function (node) {
      node.checked = node.value === value;
    });
  }

  function setFieldValue(id, value) {
    const node = document.getElementById(id);
    if (node && document.activeElement !== node) {
      node.value = value == null ? "" : String(value);
    }
  }

  function fillSettingsForm(data) {
    if (!data || !settingsView) {
      return;
    }
    setRadioGroup("set-previewStore", data.previewStore);
    setRadioGroup("set-unavailableItems", data.unavailableItems);
    setRadioGroup("set-addFolderDefault", data.addFolderDefault);
    setRadioGroup("set-playProxies", data.playProxies);
    setRadioGroup("set-listenHost", data.listenHost);
    setFieldValue("set-thumbPx", data.thumbPx);
    setFieldValue("set-previewPx", data.previewPx);
    setFieldValue("set-proxyWidth", data.proxyWidth);
    setFieldValue("set-port", data.port);
    setFieldValue("set-placeMatchMeters", data.placeMatchMeters);
    setFieldValue("set-tourOrbitSec", data.tourOrbitSec);
    setFieldValue("set-tourPictures", data.tourPictures);
    setFieldValue("set-tourPictureSec", data.tourPictureSec);
    setFieldValue("set-sort", data.sort);
    setFieldValue("set-dir", data.dir);
    setFieldValue("set-zoomLevel", data.zoomLevel);
    setFieldValue("set-faceMatchThreshold", data.faceMatchThreshold);
    syncFaceThresholdOutput(data.faceMatchThreshold);
    setFieldValue("set-faceMinSidePx", data.faceMinSidePx);
    showFaceRerunNote(facesRerunNeeded);
    if (settingsRenditionNote) {
      settingsRenditionNote.textContent = data.previewStore === "with-source"
        ? t("previewWithSourceNote")
        : t("previewWithServerNote");
    }
  }

  function formatFaceThreshold(value) {
    const number = Number(value);
    return isFinite(number) ? number.toFixed(2) : "0.80";
  }

  function syncFaceThresholdOutput(value) {
    const out = document.getElementById("set-faceMatchThreshold-value");
    if (out) {
      out.textContent = formatFaceThreshold(value);
    }
  }

  function showFaceRerunNote(show) {
    const note = document.getElementById("settings-faces-rerun");
    if (note) {
      note.hidden = !show;
    }
  }

  function commitSetting(key, value, revert) {
    persist({ [key]: value }).then(function (next) {
      if (key === "faceMatchThreshold") {
        facesRerunNeeded = true;
      }
      fillSettingsForm(next);
    }).catch(function () {
      if (typeof revert === "function") {
        revert();
      } else {
        fillSettingsForm(settings);
      }
    });
  }

  function parseSettingNumber(key, raw) {
    if (raw === "" || raw == null) {
      return null;
    }
    if (key === "placeMatchMeters" || key === "tourOrbitSec" || key === "tourPictureSec" || key === "faceMatchThreshold") {
      const number = Number(raw);
      if (!isFinite(number) || number <= 0) {
        return null;
      }
      if (key === "faceMatchThreshold" && number > 1) {
        return null;
      }
      return number;
    }
    const integer = Number(raw);
    if (!Number.isInteger(integer) || integer <= 0) {
      return null;
    }
    if (key === "port" && (integer < 1 || integer > 65535)) {
      return null;
    }
    return integer;
  }

  function sourceModeLabel(mode) {
    return mode === "copy-here" ? t("copyHereMode") : t("serveThereMode");
  }

  function sourceScanLabel(scan) {
    const state = (scan && scan.state) || "idle";
    if (state === "running") {
      return t("scanRunning");
    }
    if (state === "error") {
      return t("scanError");
    }
    if (state === "complete") {
      return t("scanComplete");
    }
    return t("scanIdle");
  }

  function renderSettingsSources(sources) {
    if (!settingsSources) {
      return;
    }
    const list = Array.isArray(sources) ? sources : [];
    settingsSources.innerHTML = "";
    if (settingsSourcesEmpty) {
      settingsSourcesEmpty.hidden = list.length > 0;
    }
    list.forEach(function (source) {
      const li = document.createElement("li");
      li.className = "settings-source" + (source.available ? "" : " is-away");
      li.dataset.sourceId = source.id || "";
      const path = document.createElement("p");
      path.className = "source-path";
      path.textContent = source.path || (source.origin && source.origin.lastKnownPath) || source.name || source.id || "";
      const meta = document.createElement("p");
      const stats = source.stats || {};
      const counts = [
        t("photosCount", { n: Number(stats.photos || 0) }),
        t("videosCount", { n: Number(stats.videos || 0) }),
      ].join(" · ");
      meta.textContent = [
        source.available ? t("available") : t("unavailable"),
        sourceModeLabel(source.mode),
        counts,
        t("itemsCount", { n: Number(stats.total || 0) }),
      ].join(" · ");
      const process = document.createElement("p");
      process.textContent = t("previewsDone", {
        done: Number(stats.renditionsDone || 0),
        queued: Number(stats.renditionsQueued || 0),
        error: Number(stats.renditionsError || 0),
      });
      const scanLine = document.createElement("p");
      const scan = source.scan || {};
      const bits = [sourceScanLabel(scan)];
      if (scan.state === "complete" || scan.state === "error" || scan.state === "running") {
        bits.push(t("scanCounts", {
          added: Number(scan.added || 0),
          skipped: Number(scan.skipped || 0),
        }));
      }
      scanLine.textContent = bits.join(" · ");
      const actions = document.createElement("div");
      actions.className = "source-actions";
      const refresh = document.createElement("button");
      refresh.type = "button";
      refresh.className = "source-rescan";
      refresh.textContent = t("refresh");
      refresh.disabled = !!scanning || scan.state === "running";
      refresh.addEventListener("click", function () {
        rescanSource(source.id);
      });
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "source-remove";
      removeBtn.textContent = t("removeFolder");
      removeBtn.addEventListener("click", function () {
        askRemoveSource(source.id);
      });
      actions.appendChild(refresh);
      actions.appendChild(removeBtn);
      li.appendChild(path);
      li.appendChild(meta);
      li.appendChild(process);
      li.appendChild(scanLine);
      li.appendChild(actions);
      settingsSources.appendChild(li);
    });
  }

  function rescanSource(sourceId) {
    if (!sourceId) {
      return;
    }
    fetch("/api/sources/" + encodeURIComponent(sourceId) + "/rescan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      showStatus("Refreshing folder", true);
      return loadCatalog();
    }).catch(function (err) {
      if (err && (err.status === 409 || (err.body && err.body.error === "busy"))) {
        return loadCatalog();
      }
      return loadCatalog();
    });
  }

  function askRemoveSource(sourceId) {
    pendingSourceId = sourceId || "";
    if (confirmRemoveSource && confirmRemoveSource.showModal) {
      confirmRemoveSource.showModal();
    }
  }

  function performRemoveSource(sourceId) {
    if (!sourceId) {
      return;
    }
    fetch("/api/sources/" + encodeURIComponent(sourceId) + "/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function () {
      return loadCatalog();
    }).catch(function () {
      return loadCatalog();
    });
  }

  function wireSettingsForm() {
    if (settingsWired || !settingsView) {
      return;
    }
    settingsWired = true;
    settingsView.querySelectorAll("input[type='radio']").forEach(function (node) {
      node.addEventListener("change", function () {
        if (!node.checked) {
          return;
        }
        const key = (node.name || "").replace(/^set-/, "");
        if (!key) {
          return;
        }
        commitSetting(key, node.value);
      });
    });
    ["thumbPx", "previewPx", "proxyWidth", "port", "placeMatchMeters", "tourOrbitSec", "tourPictures", "tourPictureSec", "faceMatchThreshold", "faceMinSidePx"].forEach(function (key) {
      const node = document.getElementById("set-" + key);
      if (!node) {
        return;
      }
      if (key === "faceMatchThreshold") {
        node.addEventListener("input", function () {
          syncFaceThresholdOutput(node.value);
        });
      }
      node.addEventListener("change", function () {
        const parsed = parseSettingNumber(key, node.value);
        if (parsed == null) {
          fillSettingsForm(settings);
          return;
        }
        commitSetting(key, parsed);
      });
    });
    ["sort", "dir", "zoomLevel"].forEach(function (key) {
      const node = document.getElementById("set-" + key);
      if (!node) {
        return;
      }
      node.addEventListener("change", function () {
        commitSetting(key, node.value);
      });
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
    return true;
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
    const cell = hoverCell;
    const id = cell && cell.dataset.id;
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
    hoverCell = null;
    if (cell && cell.isConnected && id) {
      requestStill(cell, id);
    }
  }

  function bindTileScrub(video, cell) {
    const scrub = document.createElement("input");
    scrub.type = "range";
    scrub.className = "tile-scrub";
    scrub.min = "0";
    scrub.max = "1000";
    scrub.value = "0";
    scrub.setAttribute("aria-label", t("previewPosition"));
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
    if (!hoverAllowed() || !item || (item.kind !== "video" && item.kind !== "live")) {
      stopHover();
      return;
    }
    const proxyStatus = ((item.renditions || {}).status || {}).proxy;
    if (proxyStatus !== "ready") {
      stopHover();
      return;
    }
    const proxyUrl = "/api/media/" + encodeURIComponent(item.id) + "?which=proxy";
    if (hoverVideo && hoverCell === cell && hoverCell.isConnected) {
      const src = hoverVideo.getAttribute("src") || hoverVideo.currentSrc || "";
      if (src.indexOf(item.id) !== -1) {
        if (!cell.querySelector(".tile-scrub")) {
          bindTileScrub(hoverVideo, cell);
        }
        if (hoverVideo.paused) {
          const resume = hoverVideo.play();
          if (resume && resume.catch) {
            resume.catch(function () {});
          }
        }
        return;
      }
    }
    stopHover();
    const video = document.createElement("video");
    video.muted = true;
    video.defaultMuted = true;
    video.volume = 0;
    video.loop = true;
    video.playsInline = true;
    video.setAttribute("muted", "");
    video.setAttribute("playsinline", "");
    video.setAttribute("autoplay", "");
    video.style.objectFit = "cover";
    video.style.objectPosition = "center";
    video.style.width = "100%";
    video.style.height = "100%";
    video.src = proxyUrl;
    cell.appendChild(video);
    bindTileScrub(video, cell);
    hoverVideo = video;
    hoverCell = cell;
    lastHoverId = item.id;
    function tryPlay() {
      if (hoverVideo !== video) {
        return;
      }
      const play = video.play();
      if (play && play.catch) {
        play.catch(function () {});
      }
    }
    video.addEventListener("loadedmetadata", function () {
      if (hoverVideo !== video) {
        return;
      }
      if (lastHoverId === item.id && lastHoverTime > 0) {
        try {
          video.currentTime = lastHoverTime;
        } catch (err) {}
      }
    });
    video.addEventListener("canplay", tryPlay);
    video.addEventListener("loadeddata", tryPlay);
    tryPlay();
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

  function resumeHoverIfNeeded() {
    if (!hoveredId || !hoverAllowed()) {
      return;
    }
    if (hoverVideo && hoverCell && hoverCell.isConnected && hoverCell.dataset.id === hoveredId && !hoverVideo.paused) {
      return;
    }
    rearmHover();
  }

  const STILL_MAX = 12;
  const STILL_STALL_MS = 3500;
  let stillActive = 0;
  const stillQueue = [];
  let stillJobs = [];
  const stillOk = Object.create(null);

  function stillLooksGood(img, url) {
    if (!img || img.hidden || !img.complete || !(img.naturalWidth > 0)) {
      return false;
    }
    const shown = img.getAttribute("data-still") || "";
    return !url || shown === url;
  }

  function stillUrlFor(id) {
    return "/api/media/" + encodeURIComponent(id) + "?which=" + stillWhich(itemById(id));
  }

  function stillSlotStatus(id) {
    const item = itemById(id);
    return ((item.renditions || {}).status || {})[stillWhich(item)];
  }

  function stillAge(cell) {
    const started = Number(cell && cell.dataset.stillStarted || 0);
    return started ? Date.now() - started : 0;
  }

  function liveStillJob(cell) {
    let i;
    for (i = 0; i < stillJobs.length; i += 1) {
      if (!stillJobs[i].settled && stillJobs[i].cell === cell) {
        return stillJobs[i];
      }
    }
    return null;
  }

  function releaseStill(job, pump) {
    if (!job || job.settled) {
      return;
    }
    job.settled = true;
    stillActive = Math.max(0, stillActive - 1);
    if (pump !== false) {
      pumpStillQueue();
    }
  }

  function trimStillJobs() {
    if (stillJobs.length < 64) {
      return;
    }
    stillJobs = stillJobs.filter(function (job) {
      return !job.settled;
    });
  }

  function showStill(cell, img, placeholder, url) {
    if (!img || !placeholder) {
      return;
    }
    img.setAttribute("data-still", url);
    if (img.getAttribute("src") !== url) {
      img.src = url;
    }
    if (img.complete && img.naturalWidth > 0) {
      placeholder.hidden = true;
      img.hidden = false;
    }
  }

  function paintCachedStill(cell, id, url) {
    if (!stillOk[id] || stillOk[id] !== url) {
      return false;
    }
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    showStill(cell, img, placeholder, url);
    return stillLooksGood(cell.querySelector("img"), url) || !!img;
  }

  function paintGridStills() {
    const bounds = main.getBoundingClientRect();
    const cells = Array.prototype.slice.call(main.querySelectorAll(".cell"));
    cells.sort(function (a, b) {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      const av = ar.bottom > bounds.top && ar.top < bounds.bottom ? 0 : 1;
      const bv = br.bottom > bounds.top && br.top < bounds.bottom ? 0 : 1;
      return av - bv;
    });
    cells.forEach(function (cell) {
      requestStill(cell, cell.dataset.id);
    });
  }

  function enqueueStill(cell, id, url, forceReload) {
    cell.dataset.stillWanted = url;
    let i;
    for (i = 0; i < stillQueue.length; i += 1) {
      if (stillQueue[i].cell === cell) {
        stillQueue[i] = { cell: cell, id: id, url: url, force: !!forceReload };
        pumpStillQueue();
        return;
      }
    }
    stillQueue.push({ cell: cell, id: id, url: url, force: !!forceReload });
    pumpStillQueue();
  }

  function pumpStillQueue() {
    while (stillActive < STILL_MAX && stillQueue.length) {
      startStillJob(stillQueue.shift());
    }
  }

  function startStillJob(queued) {
    const cell = queued && queued.cell;
    const id = queued && queued.id;
    const url = queued && queued.url;
    if (!cell || !id || !url || !cell.isConnected || cell.dataset.id !== id) {
      pumpStillQueue();
      return;
    }
    const placeholder = cell.querySelector(".placeholder");
    let img = cell.querySelector("img");
    if (!placeholder || !img || !img.parentNode) {
      pumpStillQueue();
      return;
    }
    if (stillLooksGood(img, url)) {
      placeholder.hidden = true;
      img.hidden = false;
      pumpStillQueue();
      return;
    }
    const existing = liveStillJob(cell);
    const stalled = stillAge(cell) >= STILL_STALL_MS;
    if (existing && !queued.force && !stalled) {
      pumpStillQueue();
      return;
    }
    if (!queued.force && !stalled && img.getAttribute("data-still") === url && img.getAttribute("src") && !img.complete) {
      pumpStillQueue();
      return;
    }
    if (existing) {
      releaseStill(existing, false);
    }
    const item = itemById(id);
    const slotStatus = ((item.renditions || {}).status || {})[stillWhich(item)];
    const next = document.createElement("img");
    next.alt = "";
    next.hidden = true;
    next.setAttribute("data-still", url);
    img.parentNode.replaceChild(next, img);
    const gen = (Number(cell.dataset.stillGen) || 0) + 1;
    cell.dataset.stillGen = String(gen);
    cell.dataset.stillStarted = String(Date.now());
    const job = { cell: cell, id: id, url: url, gen: gen, settled: false };
    stillJobs.push(job);
    trimStillJobs();
    stillActive += 1;
    next.onload = function () {
      if (job.settled) {
        return;
      }
      if (cell.dataset.stillGen === String(gen) && cell.dataset.id === id) {
        delete cell.dataset.stillErrorTried;
        stillOk[id] = url;
        placeholder.hidden = true;
        next.hidden = false;
      }
      releaseStill(job);
    };
    next.onerror = function () {
      if (job.settled) {
        return;
      }
      if (cell.dataset.stillGen === String(gen) && cell.dataset.id === id) {
        next.hidden = true;
        placeholder.hidden = false;
        if (slotStatus === "error") {
          cell.dataset.stillErrorTried = url;
          releaseStill(job);
          return;
        }
      }
      releaseStill(job);
      window.setTimeout(function () {
        if (cell.isConnected && cell.dataset.id === id) {
          requestStill(cell, id, true);
        }
      }, 800);
    };
    next.src = url;
    window.setTimeout(function () {
      if (job.settled) {
        return;
      }
      releaseStill(job);
      if (!cell.isConnected || cell.dataset.id !== id) {
        return;
      }
      if (stillLooksGood(next, url)) {
        placeholder.hidden = true;
        next.hidden = false;
        return;
      }
      requestStill(cell, id, true);
    }, STILL_STALL_MS);
  }

  function requestStill(cell, id, forceReload) {
    if (!cell || !id) {
      return;
    }
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    if (!img || !placeholder) {
      return;
    }
    const url = stillUrlFor(id);
    if (hoverCell === cell && hoverVideo && hoverCell.contains(hoverVideo)) {
      return;
    }
    if (!forceReload && stillLooksGood(img, url)) {
      stillOk[id] = url;
      placeholder.hidden = true;
      img.hidden = false;
      return;
    }
    if (!forceReload && paintCachedStill(cell, id, url) && stillLooksGood(cell.querySelector("img"), url)) {
      return;
    }
    const slotStatus = stillSlotStatus(id);
    if (slotStatus === "not-applicable") {
      placeholder.hidden = false;
      img.hidden = true;
      return;
    }
    if (slotStatus === "error" && cell.dataset.stillErrorTried === url && !forceReload) {
      placeholder.hidden = false;
      img.hidden = true;
      return;
    }
    const live = liveStillJob(cell);
    const stalled = stillAge(cell) >= STILL_STALL_MS;
    if (!forceReload && live && !stalled) {
      return;
    }
    if (!forceReload && img.getAttribute("data-still") === url && img.getAttribute("src") && !img.complete && !stalled) {
      return;
    }
    enqueueStill(cell, id, url, forceReload);
  }

  function recoverStills() {
    let i = 0;
    while (i < stillQueue.length) {
      const queued = stillQueue[i];
      if (!queued.cell || !queued.cell.isConnected || queued.cell.dataset.id !== queued.id) {
        stillQueue.splice(i, 1);
      } else {
        i += 1;
      }
    }
    stillJobs.forEach(function (job) {
      if (job.settled) {
        return;
      }
      if (!job.cell || !job.cell.isConnected || job.cell.dataset.id !== job.id) {
        releaseStill(job, false);
      }
    });
    let live = 0;
    stillJobs.forEach(function (job) {
      if (!job.settled) {
        live += 1;
      }
    });
    if (stillActive !== live) {
      stillActive = live;
    }
    pumpStillQueue();
    paintGridStills();
  }

  function stillStats() {
    let live = 0;
    stillJobs.forEach(function (job) {
      if (!job.settled) {
        live += 1;
      }
    });
    return { active: stillActive, live: live, queued: stillQueue.length };
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
    if (el === viewerVideo) {
      el.style.objectFit = "fill";
      el.style.objectPosition = "center";
    }
  }

  function stagePoint(clientX, clientY) {
    const stage = document.getElementById("viewer-stage") || viewer;
    const rect = stage.getBoundingClientRect();
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  function snapshotViewTransform() {
    return {
      scale: scale,
      tx: tx,
      ty: ty,
      fitScale: fitScale,
      layoutW: layoutW,
      layoutH: layoutH,
      rotation: rotation,
    };
  }

  function restoreViewTransform(snap) {
    if (!snap) {
      return;
    }
    if (snap.layoutW > 0 && snap.layoutH > 0) {
      layoutW = snap.layoutW;
      layoutH = snap.layoutH;
      naturalW = layoutW;
      naturalH = layoutH;
    }
    rotation = snap.rotation || 0;
    fitScale = snap.fitScale || fitScale;
    scale = snap.scale;
    tx = snap.tx;
    ty = snap.ty;
    applyTransform();
    syncZoomChrome();
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
    if (originalSwapTimer) {
      window.clearTimeout(originalSwapTimer);
      originalSwapTimer = 0;
    }
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
    syncViewerSourceChrome();
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
    slideshowEmpty.textContent = t("addPhotosFirst");
  }

  function showSlideshowEmpty() {
    slideshowEmpty.hidden = false;
    slideshowEmpty.textContent = t("addPhotosFirst");
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
    setVideoSourceState("preview");
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
    heading.textContent = t("file");
    viewerFacts.appendChild(heading);
    const list = document.createElement("dl");
    list.className = "info-fact-list";
    list.id = "viewer-fact-list";
    const meta = (item && item.metadata) || {};
    const loc = primaryLocation(item);
    appendFact(list, t("dateTaken"), formatDateTaken(item && item.capturedAt));
    appendFact(list, t("camera"), (meta.camera && String(meta.camera).trim()) || t("noCamera"));
    const width = Number(meta.width) || 0;
    const height = Number(meta.height) || 0;
    if (width > 0 && height > 0) {
      appendFact(list, t("dimensions"), width + " × " + height);
    }
    if (loc) {
      appendFact(list, t("fileSize"), formatFileSize(loc.sizeBytes));
      appendFact(list, t("filePath"), loc.lastKnownPath || loc.libraryRelativePath || "");
      const hash = loc.sha256 || "";
      if (hash) {
        appendFact(list, t("fileHash"), hash);
      }
    }
    appendFact(list, t("gps"), formatGps(meta.latitude, meta.longitude));
    const extras = alsoAtPaths(item);
    if (extras.length) {
      appendFact(list, t("alsoAt"), extras.join(" · "));
    }
    viewerFacts.appendChild(list);
    if (extras.length || filenameSiblings(item).length > 1) {
      const compareBtn = document.createElement("button");
      compareBtn.type = "button";
      compareBtn.id = "info-compare-copies";
      compareBtn.className = "compare-copies";
      compareBtn.textContent = t("compareCopies");
      compareBtn.addEventListener("click", function () {
        openCompareForItem(item);
      });
      viewerFacts.appendChild(compareBtn);
    }
  }

  function alsoAtPaths(item) {
    const loc = primaryLocation(item);
    const primary = loc ? (loc.lastKnownPath || loc.libraryRelativePath || loc.pathFromVolumeRoot || "") : "";
    const extras = [];
    currentComponentLocations(item).forEach(function (row) {
      const path = row.lastKnownPath || row.libraryRelativePath || row.pathFromVolumeRoot || "";
      if (path && path !== primary && extras.indexOf(path) < 0) {
        extras.push(path);
      }
    });
    return extras;
  }

  function currentComponentLocations(item) {
    const locs = (item && item.locations) || [];
    const want = item && item.kind === "video" ? "motion" : "still";
    const current = [];
    const fallback = [];
    locs.forEach(function (row) {
      if (!row || !row.current) {
        return;
      }
      fallback.push(row);
      if (row.component === want) {
        current.push(row);
      }
    });
    return current.length ? current : fallback;
  }

  function filenameSiblings(item) {
    const name = ((item && item.filename) || "").toLowerCase();
    if (!name) {
      return item ? [item] : [];
    }
    return items.filter(function (row) {
      return ((row && row.filename) || "").toLowerCase() === name;
    });
  }

  function findItemById(id) {
    for (let i = 0; i < items.length; i += 1) {
      if (items[i] && items[i].id === id) {
        return items[i];
      }
    }
    return extraById[id] || null;
  }

  function sideFromItem(item, loc, index) {
    const meta = (item && item.metadata) || {};
    const row = loc || {};
    const path = row.lastKnownPath || row.libraryRelativePath || row.pathFromVolumeRoot || "";
    const folder = path ? path.replace(/[\\/][^\\/]+$/, "") : "";
    return {
      itemId: item && item.id,
      filename: item && item.filename,
      kind: item && item.kind,
      capturedAt: item && item.capturedAt,
      width: meta.width,
      height: meta.height,
      sizeBytes: row.sizeBytes,
      path: path,
      folder: folder,
      sha256: row.sha256 || ((item && item.id && String(item.id).indexOf("pending-") !== 0) ? item.id : ""),
      role: row.role,
      available: item && item.available,
      locationIndex: index
    };
  }

  function groupFromItems(list, reason, key) {
    const sides = [];
    const ids = [];
    (list || []).forEach(function (item) {
      if (!item || !item.id) {
        return;
      }
      if (ids.indexOf(item.id) < 0) {
        ids.push(item.id);
      }
      const locs = currentComponentLocations(item);
      if (reason === "hash" && locs.length > 1) {
        locs.forEach(function (loc, index) {
          sides.push(sideFromItem(item, loc, index));
        });
        return;
      }
      sides.push(sideFromItem(item, locs[0] || {}, 0));
    });
    return { key: key || reason, reason: reason, itemIds: ids, sides: sides };
  }

  function compareOpen() {
    return !!(duplicateCompare && duplicateCompare.open);
  }

  function closeCompare() {
    if (duplicateCompare && duplicateCompare.open) {
      duplicateCompare.close();
    }
  }

  function shortHash(value) {
    const text = value ? String(value) : "";
    if (text.length <= 16) {
      return text;
    }
    return text.slice(0, 12) + "…";
  }

  function compareMediaUrl(side) {
    const kind = side && side.kind;
    const which = kind === "video" ? "poster" : "preview";
    return "/api/media/" + encodeURIComponent(side.itemId) + "?which=" + which;
  }

  function paintCompare() {
    if (!duplicateCompareSides) {
      return;
    }
    const group = compareGroups[compareIndex];
    duplicateCompareSides.innerHTML = "";
    if (duplicateCompareEmpty) {
      duplicateCompareEmpty.hidden = !!group;
    }
    if (duplicateCompareApply) {
      duplicateCompareApply.hidden = !group;
    }
    if (duplicateCompareMeta) {
      if (!group) {
        duplicateCompareMeta.textContent = "";
      } else if (group.reason === "hash" && (group.itemIds || []).length === 1) {
        duplicateCompareMeta.textContent = t("sameLibraryItem");
      } else {
        duplicateCompareMeta.textContent = "";
      }
    }
    if (duplicateCompareNav) {
      duplicateCompareNav.hidden = compareGroups.length < 2;
    }
    if (duplicateCompareIndex) {
      duplicateCompareIndex.textContent = compareGroups.length
        ? t("compareGroup", { current: compareIndex + 1, total: compareGroups.length })
        : "";
    }
    if (duplicateComparePrev) {
      duplicateComparePrev.disabled = compareIndex <= 0;
    }
    if (duplicateCompareNext) {
      duplicateCompareNext.disabled = compareIndex >= compareGroups.length - 1;
    }
    if (!group) {
      return;
    }
    (group.sides || []).forEach(function (side, index) {
      const article = document.createElement("article");
      article.className = "compare-side";
      article.setAttribute("data-item-id", side.itemId || "");
      article.setAttribute("data-side", String(index));
      const img = document.createElement("img");
      img.alt = side.filename || "";
      img.src = compareMediaUrl(side);
      article.appendChild(img);
      const list = document.createElement("dl");
      list.className = "compare-stats info-fact-list";
      const width = Number(side.width) || 0;
      const height = Number(side.height) || 0;
      if (width > 0 && height > 0) {
        appendFact(list, t("dimensions"), width + " × " + height);
      }
      appendFact(list, t("fileSize"), formatFileSize(side.sizeBytes));
      appendFact(list, t("filePath"), side.path || "");
      appendFact(list, t("folder"), side.folder || "");
      appendFact(list, t("dateTaken"), formatDateTaken(side.capturedAt));
      appendFact(list, t("fileHash"), shortHash(side.sha256));
      article.appendChild(list);
      const choice = document.createElement("div");
      choice.className = "compare-choice";
      const itemId = side.itemId || ("side-" + index);
      const groupName = "compare-choice-" + itemId + "-" + index;
      const selected = compareChoices[itemId] || "keep";
      ["keep", "remove"].forEach(function (value) {
        const label = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = groupName;
        radio.value = value;
        radio.checked = selected === value;
        radio.addEventListener("change", function () {
          if (radio.checked) {
            compareChoices[itemId] = value;
            syncCompareChoiceRadios(itemId, value);
          }
        });
        label.appendChild(radio);
        label.appendChild(document.createTextNode(value === "keep" ? t("keep") : t("remove")));
        choice.appendChild(label);
      });
      article.appendChild(choice);
      duplicateCompareSides.appendChild(article);
    });
  }

  function syncCompareChoiceRadios(itemId, value) {
    if (!duplicateCompareSides) {
      return;
    }
    Array.from(duplicateCompareSides.querySelectorAll(".compare-side")).forEach(function (el) {
      if ((el.getAttribute("data-item-id") || "") !== itemId) {
        return;
      }
      Array.from(el.querySelectorAll('input[type="radio"]')).forEach(function (node) {
        node.checked = node.value === value;
      });
    });
  }

  function showCompare(groups) {
    compareGroups = (groups || []).filter(function (group) {
      return group && (group.sides || []).length;
    });
    compareIndex = 0;
    compareChoices = {};
    compareGroups.forEach(function (group) {
      (group.itemIds || []).forEach(function (id) {
        if (id && !compareChoices[id]) {
          compareChoices[id] = "keep";
        }
      });
    });
    paintCompare();
    if (duplicateCompare && duplicateCompare.showModal) {
      if (!duplicateCompare.open) {
        duplicateCompare.showModal();
      }
      return;
    }
  }

  function openDetectedCompare() {
    return fetch("/api/duplicates").then(readJson).then(function (body) {
      showCompare((body && body.groups) || []);
    }).catch(function () {
      showCompare([]);
    });
  }

  function openCompareForIds(ids) {
    const list = [];
    const seen = {};
    (ids || []).forEach(function (id) {
      const item = findItemById(id);
      if (item && !seen[item.id]) {
        seen[item.id] = true;
        list.push(item);
      }
    });
    if (list.length < 2) {
      return;
    }
    showCompare([groupFromItems(list, "selection", "selection")]);
  }

  function openCompareForItem(item) {
    if (!item) {
      return;
    }
    const groups = [];
    const locs = currentComponentLocations(item);
    if (locs.length > 1) {
      groups.push(groupFromItems([item], "hash", "hash:" + item.id));
    }
    const siblings = filenameSiblings(item);
    if (siblings.length > 1) {
      groups.push(groupFromItems(siblings, "filename", "name:" + String(item.filename || "").toLowerCase()));
    }
    if (!groups.length) {
      groups.push(groupFromItems([item], "item", "item:" + item.id));
    }
    showCompare(groups);
  }

  function applyCompareChoices() {
    const gone = {};
    Object.keys(compareChoices).forEach(function (id) {
      if (compareChoices[id] === "remove") {
        gone[id] = true;
      }
    });
    const ids = Object.keys(gone);
    closeCompare();
    if (!ids.length) {
      return;
    }
    askRemove(ids);
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
    viewerFavorite.setAttribute("aria-label", on ? t("unfavorite") : t("favorite"));
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
    openOriginalBtn.textContent = t("open");
    openOriginalBtn.removeAttribute("aria-pressed");
    viewer.dataset.showingOriginal = showingOriginal ? "1" : "0";
    syncViewerSourceChrome();
  }

  function setVideoSourceState(state) {
    videoSourceState = state || "";
    syncViewerSourceChrome();
  }

  function syncViewerSourceChrome() {
    if (!viewerSource) {
      return;
    }
    const item = viewerIndex >= 0 ? items[viewerIndex] : null;
    const isVideo = !!(item && (item.kind === "video" || item.kind === "live"));
    const hasSrc = !!(viewerVideo && (viewerVideo.currentSrc || viewerVideo.getAttribute("src")));
    if (viewer.hidden || !isVideo || (viewerVideo && viewerVideo.hidden) || !hasSrc) {
      viewerSource.hidden = true;
      viewerSource.textContent = "";
      delete viewerSource.dataset.state;
      return;
    }
    let state = videoSourceState || "preview";
    if (usingProxy() && state !== "loading" && state !== "unavailable") {
      state = "preview";
    } else if (usingPlayback() && state !== "loading") {
      state = "full";
    }
    viewerSource.hidden = false;
    viewerSource.textContent = sourceLabel(state);
    viewerSource.dataset.state = state;
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
    viewerVideo.removeAttribute("data-using-playback");
    viewerVideo.load();
    viewerVideo.hidden = true;
    videoSourceState = "";
    viewerWantPlay = false;
    hideViewerScrub();
    syncViewerSourceChrome();
  }

  let viewerMuted = false;
  let viewerVolume = 1;

  function applyViewerVolume() {
    if (viewerVideo) {
      viewerVideo.muted = viewerMuted || viewerVolume <= 0;
      viewerVideo.volume = viewerMuted ? 0 : viewerVolume;
    }
    if (viewerMute) {
      const muted = !!(viewerVideo && viewerVideo.muted);
      viewerMute.setAttribute("aria-pressed", muted ? "true" : "false");
      viewerMute.textContent = muted ? t("unmute") : t("mute");
      viewerMute.title = muted ? "Unmute" : "Mute";
    }
    if (viewerVolumeSlider) {
      viewerVolumeSlider.value = String(Math.round(viewerVolume * 100));
    }
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
    applyViewerVolume();
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
      revealError.textContent = t("originalMissing");
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
      delete field.dataset.renameId;
    });
    namingPersonId = "";
    if (personField) {
      personField.placeholder = t("person");
    }
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
    syncSelectionChrome();
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

  function playbackStatus(item) {
    return (((item && item.renditions) || {}).status || {}).playback || "";
  }

  function playbackReady(item) {
    return playbackStatus(item) === "ready";
  }

  function prefersDerivedPlayback(item) {
    const name = ((item && item.filename) || "").toLowerCase();
    return name.endsWith(".mov") || name.endsWith(".avi") || name.endsWith(".mkv");
  }

  function mediaWhichUrl(item, which) {
    return "/api/media/" + encodeURIComponent(item.id) + "?which=" + which;
  }

  function usingProxy() {
    return viewerVideo.getAttribute("data-using-proxy") === "1";
  }

  function usingPlayback() {
    return viewerVideo.getAttribute("data-using-playback") === "1";
  }

  function markVideoWhich(which) {
    if (which === "proxy") {
      viewerVideo.setAttribute("data-using-proxy", "1");
      viewerVideo.removeAttribute("data-using-playback");
      return;
    }
    if (which === "playback") {
      viewerVideo.removeAttribute("data-using-proxy");
      viewerVideo.setAttribute("data-using-playback", "1");
      return;
    }
    viewerVideo.removeAttribute("data-using-proxy");
    viewerVideo.removeAttribute("data-using-playback");
  }

  function swapViewerTo(item, url, state, startTime) {
    const t = Math.max(viewerVideo.currentTime || 0, Number(startTime) || 0);
    const paused = viewerVideo.paused && !viewerWantPlay;
    const rate = viewerVideo.playbackRate || 1;
    const snap = snapshotViewTransform();
    cancelOriginalPreload();
    viewerVideo.onloadedmetadata = function () {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      try {
        if (isFinite(t)) {
          viewerVideo.currentTime = t;
        }
      } catch (err) {}
      restoreViewTransform(snap);
    };
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
      restoreViewTransform(snap);
      layoutVideo(item);
      restoreViewTransform(snap);
      applyViewerVolume();
      setVideoSourceState(state);
      showViewerScrub();
      if (!paused) {
        const play = viewerVideo.play();
        if (play && play.catch) {
          play.catch(function () {});
        }
      }
      syncViewerScrub();
    };
    viewerVideo.onerror = function () {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      if (state === "original") {
        promoteToPlaybackOrUnavailable(item, t);
        return;
      }
      if (!usingProxy()) {
        markVideoWhich("proxy");
        viewerVideo.src = mediaWhichUrl(item, "proxy");
      }
      setVideoSourceState("unavailable");
    };
    markVideoWhich(state === "full" ? "playback" : state === "original" ? "original" : "proxy");
    viewerVideo.src = url;
  }

  function pollPlaybackReady(item, startTime) {
    cancelOriginalPreload();
    setVideoSourceState("loading");
    const started = Date.now();
    function tick() {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      if (usingPlayback() || videoSourceState === "original" || videoSourceState === "full") {
        return;
      }
      const live = items.find(function (row) {
        return row.id === item.id;
      }) || item;
      if (playbackReady(live)) {
        swapViewerTo(live, mediaWhichUrl(live, "playback"), "full", startTime);
        return;
      }
      const status = playbackStatus(live);
      if (status === "error" || status === "not-applicable") {
        setVideoSourceState("unavailable");
        return;
      }
      fetch(mediaWhichUrl(item, "playback"), { method: "HEAD" }).then(function (res) {
        if (viewerItemId !== item.id || viewer.hidden) {
          return;
        }
        if (res.ok) {
          swapViewerTo(item, mediaWhichUrl(item, "playback"), "full", startTime);
          return;
        }
        if (Date.now() - started > PLAYBACK_WAIT_MS) {
          setVideoSourceState("unavailable");
          return;
        }
        originalSwapTimer = window.setTimeout(tick, PLAYBACK_POLL_MS);
      }).catch(function () {
        if (Date.now() - started > PLAYBACK_WAIT_MS) {
          setVideoSourceState("unavailable");
          return;
        }
        originalSwapTimer = window.setTimeout(tick, PLAYBACK_POLL_MS);
      });
    }
    tick();
  }

  function promoteToPlaybackOrUnavailable(item, startTime) {
    const status = playbackStatus(item);
    if (status === "ready") {
      setVideoSourceState("loading");
      swapViewerTo(item, mediaWhichUrl(item, "playback"), "full", startTime);
      return;
    }
    if (status === "queued") {
      pollPlaybackReady(item, startTime);
      return;
    }
    setVideoSourceState("unavailable");
  }

  function maybePromoteFullSource(item) {
    if (viewer.hidden || viewerItemId !== item.id) {
      return;
    }
    if (usingPlayback() || videoSourceState === "original" || videoSourceState === "full") {
      return;
    }
    if (videoSourceState !== "loading" && videoSourceState !== "preview" && videoSourceState !== "unavailable") {
      return;
    }
    if (!playbackReady(item)) {
      return;
    }
    if (prefersDerivedPlayback(item) || videoSourceState === "loading" || videoSourceState === "unavailable") {
      swapViewerTo(item, mediaWhichUrl(item, "playback"), "full", viewerVideo.currentTime);
    }
  }

  function scheduleOriginalSwap(item, originalUrl, startTime) {
    cancelOriginalPreload();
    if (prefersDerivedPlayback(item)) {
      promoteToPlaybackOrUnavailable(item, startTime);
      return;
    }
    if (!item || item.available === false || !browserCanPlayOriginal(item)) {
      promoteToPlaybackOrUnavailable(item, startTime);
      return;
    }
    setVideoSourceState("loading");
    const preload = document.createElement("video");
    preload.preload = "auto";
    preload.muted = true;
    originalPreload = preload;
    originalPreloadId = item.id;
    preload.onerror = function () {
      if (originalPreloadId === item.id) {
        promoteToPlaybackOrUnavailable(item, startTime);
      }
    };
    preload.oncanplay = function () {
      if (originalPreloadId !== item.id || viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      swapViewerTo(item, originalUrl, "original", startTime);
    };
    originalSwapTimer = window.setTimeout(function () {
      if (originalPreloadId === item.id && usingProxy()) {
        promoteToPlaybackOrUnavailable(item, startTime);
      }
    }, ORIGINAL_SWAP_MS);
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
    const originalUrl = mediaWhichUrl(item, "original");
    const proxyUrl = mediaWhichUrl(item, "proxy");
    viewerVideo.hidden = false;
    showViewerPlaceholder(false);
    showViewerScrub();
    if (autoplay) {
      viewerWantPlay = true;
    }
    let appliedStart = false;
    function afterReady() {
      if (viewerItemId !== item.id || viewer.hidden) {
        return;
      }
      if (!appliedStart) {
        applyViewerStartTime(startTime);
        appliedStart = true;
      }
      layoutVideo(item);
      showViewerScrub();
      syncViewerSourceChrome();
      if (autoplay) {
        const play = viewerVideo.play();
        if (play && play.catch) {
          play.catch(function () {});
        }
      }
    }
    if (viewerVideo.getAttribute("data-source-ready") === item.id && (viewerVideo.currentSrc || viewerVideo.getAttribute("src"))) {
      if (usingPlayback()) {
        setVideoSourceState("full");
      } else if (usingProxy()) {
        if (!videoSourceState || videoSourceState === "original" || videoSourceState === "full") {
          setVideoSourceState("preview");
        }
      } else {
        setVideoSourceState("original");
      }
      afterReady();
      return;
    }
    setVideoSourceState("preview");
    viewerVideo.onerror = function () {
      if (usingProxy()) {
        return;
      }
      markVideoWhich("proxy");
      viewerVideo.src = proxyUrl;
      promoteToPlaybackOrUnavailable(item, startTime);
    };
    viewerVideo.onloadedmetadata = function () {
      afterReady();
      viewerVideo.onloadedmetadata = function () {
        if (viewerItemId !== item.id || viewer.hidden) {
          return;
        }
        layoutVideo(item);
        showViewerScrub();
      };
    };
    viewerVideo.setAttribute("data-source-ready", item.id);
    markVideoWhich("proxy");
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
    const originalUrl = mediaWhichUrl(item, "original") + "&component=motion";
    const proxyUrl = mediaWhichUrl(item, "proxy");
    if (viewerVideo.getAttribute("data-source-ready") === item.id) {
      return;
    }
    function useProxy() {
      if (usingProxy()) {
        return;
      }
      markVideoWhich("proxy");
      viewerVideo.src = proxyUrl;
      setVideoSourceState(item.motionAvailable ? "unavailable" : "preview");
    }
    function usePlayback() {
      markVideoWhich("playback");
      viewerVideo.src = mediaWhichUrl(item, "playback");
      setVideoSourceState("full");
    }
    viewerVideo.onerror = function () {
      if (usingPlayback()) {
        useProxy();
        return;
      }
      if (usingProxy()) {
        return;
      }
      if (playbackReady(item)) {
        usePlayback();
        return;
      }
      useProxy();
      if (playbackStatus(item) === "queued") {
        pollPlaybackReady(item, 0);
      }
    };
    viewerVideo.setAttribute("data-source-ready", item.id);
    if (playbackReady(item) && !item.motionAvailable) {
      usePlayback();
      return;
    }
    if (item.motionAvailable) {
      setVideoSourceState("loading");
      markVideoWhich("original");
      viewerVideo.src = originalUrl;
      viewerVideo.onloadeddata = function () {
        if (viewerItemId === item.id && !usingProxy() && !usingPlayback()) {
          setVideoSourceState("original");
        }
      };
      return;
    }
    useProxy();
    if (playbackStatus(item) === "queued") {
      pollPlaybackReady(item, 0);
    }
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
            const proxyUrl = mediaWhichUrl(item, "proxy");
            if (!usingProxy()) {
              markVideoWhich("proxy");
              viewerVideo.src = proxyUrl;
              promoteToPlaybackOrUnavailable(item, viewerVideo.currentTime);
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
    if (viewerVideo.paused) {
      viewerWantPlay = true;
    } else {
      viewerWantPlay = false;
    }
    playOriginalOrProxy(item);
    if (viewerVideo.paused) {
      const play = viewerVideo.play();
      if (play && play.catch) {
        play.catch(function () {
          const proxyUrl = mediaWhichUrl(item, "proxy");
          if (!usingProxy()) {
            markVideoWhich("proxy");
            viewerVideo.src = proxyUrl;
            promoteToPlaybackOrUnavailable(item, viewerVideo.currentTime);
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
    if (viewerTags) {
      viewerTags.innerHTML = "";
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
        if (!rec || !rec.id) {
          return;
        }
        if (kind !== "person" && !rec.name) {
          return;
        }
        const unnamed = kind === "person" && !rec.name;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = unnamed ? "entity-label unnamed" : "entity-label";
        btn.dataset.entityKind = kind;
        btn.dataset.entityId = rec.id;
        btn.textContent = rec.name || t("unnamed");
        if (unnamed && rec.id === namingPersonId) {
          btn.setAttribute("aria-pressed", "true");
        }
        btn.addEventListener("click", function () {
          if (unnamed) {
            namingPersonId = rec.id;
            if (personField) {
              personField.dataset.renameId = rec.id;
              personField.placeholder = t("unnamed");
              personField.focus();
            }
            renderViewerLabels(item);
            return;
          }
          filterByEntity(kind, rec.id);
        });
        node.appendChild(btn);
      });
    }
    addLabels(peopleLabels, "person", entities.people);
    renderViewerFaceCrops(item);
    addLabels(placeLabels, "place", entities.places);
    addLabels(thingsLabels, "thing", entities.things);
    if (viewerTags) {
      (entities.things || []).forEach(function (rec) {
        if (!rec || !rec.id || !rec.name) {
          return;
        }
        const wrap = document.createElement("span");
        wrap.className = "entity-label";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "entity-label";
        btn.dataset.entityKind = "thing";
        btn.dataset.entityId = rec.id;
        btn.textContent = rec.name;
        btn.addEventListener("click", function () {
          filterByEntity("thing", rec.id);
        });
        const drop = document.createElement("button");
        drop.type = "button";
        drop.className = "chip-x";
        drop.setAttribute("aria-label", "Remove tag " + rec.name);
        drop.textContent = "x";
        drop.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          applyTagsToItems([item.id], [], [rec.id]);
        });
        wrap.appendChild(btn);
        wrap.appendChild(drop);
        viewerTags.appendChild(wrap);
      });
    }
    function fillEmpty(node) {
      if (!node || node.childNodes.length) {
        return;
      }
      const empty = document.createElement("p");
      empty.className = "info-empty";
      empty.textContent = t("noneYet");
      node.appendChild(empty);
    }
    fillEmpty(peopleLabels);
    fillEmpty(placeLabels);
    fillEmpty(thingsLabels);
    fillEmpty(viewerTags);
  }

  function renderViewerFaceCrops(item) {
    if (!viewerFaceCrops) {
      return;
    }
    viewerFaceCrops.innerHTML = "";
    if (!item) {
      return;
    }
    ((item.faces) || []).forEach(function (face) {
      if (!face || !face.personId) {
        return;
      }
      const person = peopleCatalog.filter(function (row) { return row.id === face.personId; })[0] || { id: face.personId, name: null };
      const wrap = document.createElement("div");
      wrap.className = "viewer-face-crop";
      const crop = document.createElement("span");
      crop.className = "person-face";
      paintFace(crop, { itemId: item.id, box: face.box || null });
      wrap.appendChild(crop);
      const split = document.createElement("button");
      split.type = "button";
      split.className = "face-split";
      split.textContent = t("notThisPerson");
      split.title = t("notThisPerson");
      split.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        splitFace(face.personId, item.id, face.box || null);
      });
      wrap.appendChild(split);
      wrap.title = personDisplayName(person);
      viewerFaceCrops.appendChild(wrap);
    });
  }

  function openStillViewer(item, index) {
    if (viewerItemId !== item.id) {
      namingPersonId = "";
      if (personField) {
        delete personField.dataset.renameId;
        personField.placeholder = t("person");
      }
    }
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
    showViewerScrub();
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
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.setAttribute("role", "button");
    cell.tabIndex = 0;
    cell.dataset.id = item.id;
    cell.dataset.filename = item.filename || "";
    cell.dataset.kind = item.kind || "";
    cell.dataset.slot = slot || "grid";
    if (selectedIds.indexOf(item.id) >= 0) {
      cell.classList.add("selected");
    }
    const placeholder = document.createElement("span");
    placeholder.className = "placeholder";
    placeholder.textContent = t("previewUnavailable");
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
    cell.addEventListener("focus", function () {
      selectedId = item.id;
      syncSelectionChrome();
    });
    cell.addEventListener("keydown", function (event) {
      if (event.target !== cell) {
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        cell.click();
      }
    });
    cell.addEventListener("click", function (event) {
      if (event.metaKey || event.ctrlKey) {
        event.preventDefault();
        toggleSelectedId(item.id);
        return;
      }
      if (event.shiftKey && lastClickedId) {
        event.preventDefault();
        selectRange(lastClickedId, item.id);
        return;
      }
      selectedId = item.id;
      lastClickedId = item.id;
      selectedIds = [item.id];
      paintSelection();
      syncSelectionChrome();
      if (hoverVideo && hoverCell === cell) {
        rememberHoverTime(item.id, hoverVideo);
      }
      openViewer(item.id);
    });
    return cell;
  }

  function itemById(id) {
    for (let i = 0; i < items.length; i += 1) {
      if (items[i].id === id) {
        return items[i];
      }
    }
    if (extraById[id]) {
      return extraById[id];
    }
    return { id: id, filename: "" };
  }

  function leftoverCount() {
    let n = 0;
    Object.keys(togetherByPerson).forEach(function (id) {
      n += (togetherByPerson[id] || []).length;
    });
    return n;
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
    main.dataset.arrange = arrangeBy;
    main.dataset.hearts = size >= HEART_MIN ? "on" : "off";
    if (arrangeSelect && arrangeSelect.value !== arrangeBy) {
      arrangeSelect.value = arrangeBy;
    }
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

  function firstEntity(item, kind) {
    const list = ((item && item.entities) || {})[kind] || [];
    if (!list.length) {
      return null;
    }
    const ranked = list.slice().sort(function (a, b) {
      const an = a && a.name ? 0 : 1;
      const bn = b && b.name ? 0 : 1;
      if (an !== bn) {
        return an - bn;
      }
      return String((a && a.name) || "").localeCompare(String((b && b.name) || "")) || String((a && a.id) || "").localeCompare(String((b && b.id) || ""));
    });
    return ranked[0];
  }

  function displayGroupKey(group) {
    const key = (group && group.key) || "";
    if (arrangeBy === "dates") {
      return I18N.formatDateGroup(key);
    }
    if (key === "Unknown") {
      return t("unknown");
    }
    if (key === "No place") {
      return t("noPlace");
    }
    if (key === "Untagged") {
      return t("untagged");
    }
    if (key === "Unnamed") {
      return t("unnamed");
    }
    return key;
  }

  function groupsFromArrange(list, by) {
    if (by === "dates") {
      return groupsFromItems(list, settings.zoomLevel);
    }
    const leftoverKey = by === "people" ? "Unknown" : by === "places" ? "No place" : "Untagged";
    const buckets = {};
    const leftover = [];
    (list || []).forEach(function (item) {
      let chosen = null;
      if (by === "people") {
        chosen = firstEntity(item, "people");
      } else if (by === "places") {
        chosen = firstEntity(item, "places");
      } else {
        chosen = firstEntity(item, "things");
      }
      if (!chosen) {
        leftover.push(item.id);
        return;
      }
      const id = chosen.id;
      if (!buckets[id]) {
        buckets[id] = { key: chosen.name || (by === "people" ? "Unnamed" : id), id: id, itemIds: [item.id] };
      } else {
        buckets[id].itemIds.push(item.id);
      }
    });
    const out = Object.keys(buckets).map(function (id) {
      return buckets[id];
    }).sort(function (a, b) {
      return String(a.key).localeCompare(String(b.key)) || String(a.id).localeCompare(String(b.id));
    });
    if (leftover.length) {
      out.push({ key: leftoverKey, id: null, itemIds: leftover });
    }
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
      const placeholder = cell.querySelector(".placeholder");
      if (placeholder) {
        placeholder.textContent = t("previewUnavailable");
      }
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
    toggle.textContent = t("favorites");
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

  function makeTogetherSection(existing, mosaic) {
    const ids = selectedPeople();
    if (ids.length < 2) {
      delete main.dataset.together;
      return null;
    }
    const section = document.createElement("section");
    section.id = "photos-together";
    section.className = "group photos-together" + (togetherOpen ? "" : " collapsed");
    const heading = document.createElement("h2");
    heading.className = "group-key";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "photos-together-toggle";
    toggle.textContent = t("photosTogether", { n: items.length });
    toggle.setAttribute("aria-expanded", togetherOpen ? "true" : "false");
    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      togetherOpen = !togetherOpen;
      section.classList.toggle("collapsed", !togetherOpen);
      toggle.setAttribute("aria-expanded", togetherOpen ? "true" : "false");
    });
    heading.appendChild(toggle);
    section.appendChild(heading);
    const list = document.createElement("div");
    list.className = mosaic ? "mosaic" : "item-list";
    items.forEach(function (item) {
      list.appendChild(takeCell(existing, item.id, "together"));
    });
    section.appendChild(list);
    main.dataset.together = String(items.length);
    return section;
  }

  function makePersonSoloSections(existing, mosaic) {
    const ids = selectedPeople();
    if (ids.length < 2) {
      return [];
    }
    const out = [];
    ids.forEach(function (id) {
      const leftover = togetherByPerson[id] || [];
      if (!leftover.length) {
        return;
      }
      const person = peopleCatalog.filter(function (row) { return row.id === id; })[0] || { id: id, name: null };
      const open = togetherSolosOpen[id] !== false;
      const section = document.createElement("section");
      section.id = "photos-person-" + id;
      section.className = "group photos-person" + (open ? "" : " collapsed");
      section.dataset.personId = id;
      const heading = document.createElement("h2");
      heading.className = "group-key";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "photos-person-toggle";
      toggle.textContent = t("photosOfPerson", { name: personDisplayName(person), n: leftover.length });
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        const next = togetherSolosOpen[id] === false;
        togetherSolosOpen[id] = next;
        section.classList.toggle("collapsed", !next);
        toggle.setAttribute("aria-expanded", next ? "true" : "false");
      });
      heading.appendChild(toggle);
      section.appendChild(heading);
      const list = document.createElement("div");
      list.className = mosaic ? "mosaic" : "item-list";
      leftover.forEach(function (item) {
        list.appendChild(takeCell(existing, item.id, "solo-" + id));
      });
      section.appendChild(list);
      out.push(section);
    });
    return out;
  }

  function render() {
    const level = settings.zoomLevel;
    applyGridMetrics();
    syncPresentableSort();
    syncFilterDataset();
    syncSelectionChrome();
    if (!items.length && leftoverCount() === 0) {
      stopHover();
      if (hasActiveFilter()) {
        main.innerHTML = "<p>" + emptySearchText() + "</p>";
        renderKey = "empty-search:" + emptySearchText();
      } else if (!catalogReady && catalogLooksPopulated()) {
        main.innerHTML = '<p id="grid-loading">' + t("loadingPictures") + "</p>";
        renderKey = "loading";
      } else {
        main.innerHTML = '<div class="empty-state" id="empty-library"><p>' + t("emptyLibrary") + '</p><button type="button" id="empty-add-folder">' + t("addFolder") + '</button><p class="empty-hint">' + t("familyHint") + "</p></div>";
        const emptyAdd = document.getElementById("empty-add-folder");
        if (emptyAdd) {
          emptyAdd.setAttribute("aria-label", t("addPhotos"));
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
    const togetherKey = selectedPeople().join(",") + ":" + items.map(function (item) {
      return item.id;
    }).join(",") + ":" + Object.keys(togetherByPerson).map(function (id) {
      return id + "=" + (togetherByPerson[id] || []).map(function (item) { return item.id; }).join(",");
    }).join(";");
    const key = level + "|" + arrangeBy + "|" + (groupDates ? "dates" : "wall") + "|" + favKey + "|" + togetherKey + "|" + settings.sort + "|" + settings.dir + "|" + queryString() + "|" + groups.map(function (group) {
      return group.key + ":" + (group.itemIds || []).join(",");
    }).join(";");
    if (key === renderKey) {
      paintGridStills();
      resumeHoverIfNeeded();
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
    const together = makeTogetherSection(existing, mosaic);
    if (together) {
      fragment.appendChild(together);
    }
    if (!groupDates && arrangeBy === "dates") {
      const list = document.createElement("div");
      list.className = "item-list wall-list";
      items.forEach(function (item) {
        list.appendChild(takeCell(existing, item.id, "grid"));
      });
      fragment.appendChild(list);
    } else {
      const shown = (arrangeBy === "dates") ? groups : (groups.length ? groups : groupsFromArrange(items, arrangeBy));
      shown.forEach(function (group) {
        const section = document.createElement("section");
        const collapseKey = arrangeBy + ":" + (group.id || group.key);
        const collapsed = !!collapsedGroups[collapseKey];
        section.className = "group" + (collapsed ? " collapsed" : "");
        section.dataset.key = group.key;
        if (group.id) {
          section.dataset.id = group.id;
        }
        const heading = document.createElement("h2");
        heading.className = "group-key";
        heading.setAttribute("role", "button");
        heading.tabIndex = 0;
        heading.setAttribute("aria-expanded", collapsed ? "false" : "true");
        heading.textContent = displayGroupKey(group);
        heading.addEventListener("click", function () {
          collapsedGroups[collapseKey] = !collapsedGroups[collapseKey];
          section.classList.toggle("collapsed", !!collapsedGroups[collapseKey]);
          heading.setAttribute("aria-expanded", collapsedGroups[collapseKey] ? "false" : "true");
        });
        heading.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            heading.click();
          }
        });
        section.appendChild(heading);
        const list = document.createElement("div");
        list.className = mosaic && arrangeBy === "dates" ? "mosaic" : "item-list";
        (group.itemIds || []).forEach(function (id) {
          list.appendChild(takeCell(existing, id, "grid"));
        });
        section.appendChild(list);
        fragment.appendChild(section);
      });
    }
    makePersonSoloSections(existing, mosaic).forEach(function (section) {
      fragment.appendChild(section);
    });
    Object.keys(existing).forEach(function (keyName) {
      const leftover = existing[keyName];
      if (leftover && leftover.parentNode) {
        leftover.parentNode.removeChild(leftover);
      }
    });
    if (main.replaceChildren) {
      main.replaceChildren(fragment);
    } else {
      main.innerHTML = "";
      main.appendChild(fragment);
    }
    applyGridMetrics();
    paintSelection();
    renderKey = key;
    paintGridStills();
    if (anchor) {
      scrollIdIntoView(anchor);
    }
    resumeHoverIfNeeded();
  }

  function personDisplayName(person) {
    if (person && person.name) {
      return person.name;
    }
    return t("unnamed");
  }

  function faceBoxQuery(box) {
    return box.map(function (value) {
      return Number(value).toFixed(5);
    }).join(",");
  }

  function faceCrop(thumb) {
    const out = { src: "", left: "0%", top: "0%", width: "100%", height: "100%", kind: "empty" };
    if (!thumb || !thumb.itemId) {
      return out;
    }
    const box = thumb.box;
    if (box && box.length === 4 && box[2] > 0 && box[3] > 0) {
      out.src = "/api/media/" + encodeURIComponent(thumb.itemId) + "?which=face&box=" + faceBoxQuery(box);
      out.kind = "face";
      return out;
    }
    out.src = "/api/media/" + encodeURIComponent(thumb.itemId) + "?which=thumb";
    out.kind = "thumb";
    return out;
  }

  function applyFaceCrop(img, crop) {
    img.alt = "";
    img.draggable = false;
    img.style.left = "0";
    img.style.top = "0";
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.objectFit = "cover";
  }

  function scheduleFaceRefresh(node, thumb) {
    if (!thumb || !thumb.itemId || !node) {
      return;
    }
    const delays = [800, 2000, 5000, 10000];
    let attempt = 0;
    function retry() {
      if (!node.isConnected) {
        return;
      }
      const crop = faceCrop(thumb);
      if (!crop.src) {
        return;
      }
      if (crop.kind !== "face") {
        const faceItem = itemById(thumb.itemId);
        const faceStatus = faceItem ? ((faceItem.renditions || {}).status || {}).thumb : "";
        if (faceStatus && faceStatus !== "ready" && faceStatus !== "error") {
          attempt += 1;
          if (attempt < delays.length) {
            window.setTimeout(retry, delays[attempt]);
          }
          return;
        }
      }
      const img = document.createElement("img");
      applyFaceCrop(img, crop);
      img.onload = function () {
        node.classList.remove("person-face-pending");
        node.classList.remove("person-face-empty");
        node.innerHTML = "";
        node.appendChild(img);
      };
      img.onerror = function () {
        attempt += 1;
        if (attempt < delays.length) {
          window.setTimeout(retry, delays[attempt]);
        }
      };
      img.src = crop.src;
    }
    window.setTimeout(retry, delays[0]);
  }

  function paintFace(node, thumb) {
    node.innerHTML = "";
    node.classList.remove("person-face-empty");
    node.classList.remove("person-face-pending");
    const crop = faceCrop(thumb);
    if (!crop.src) {
      node.classList.add("person-face-empty");
      return;
    }
    if (crop.kind !== "face") {
      const faceItem = itemById(thumb.itemId);
      const faceStatus = faceItem ? ((faceItem.renditions || {}).status || {}).thumb : "";
      if (faceStatus !== "ready" && faceStatus !== "error") {
        node.classList.add("person-face-pending");
        scheduleFaceRefresh(node, thumb);
        return;
      }
    }
    const img = document.createElement("img");
    applyFaceCrop(img, crop);
    img.onload = function () {
      node.classList.remove("person-face-pending");
      node.classList.remove("person-face-empty");
    };
    img.onerror = function () {
      node.classList.add("person-face-pending");
      if (img.parentNode === node) {
        img.remove();
      }
      scheduleFaceRefresh(node, thumb);
    };
    img.src = crop.src;
    node.appendChild(img);
  }

  function visiblePeople() {
    const selected = {};
    selectedPeople().forEach(function (id) {
      selected[id] = true;
    });
    return peopleCatalog.filter(function (person) {
      if (selected[person.id]) {
        return true;
      }
      if (person.visible === false) {
        return false;
      }
      if (person.named) {
        return true;
      }
      return (person.itemCount || 0) >= personOfInterestMin;
    });
  }

  function collectPersonFaces(personId) {
    const seen = {};
    const faces = [];
    items.forEach(function (item) {
      ((item.faces) || []).forEach(function (face) {
        if (!face || face.personId !== personId) {
          return;
        }
        const key = item.id + ":" + JSON.stringify(face.box || null);
        if (seen[key]) {
          return;
        }
        seen[key] = true;
        faces.push({
          itemId: item.id,
          box: face.box || null,
          detScore: face.detScore,
          matchScore: face.matchScore,
        });
      });
    });
    return faces;
  }

  function renderPersonProfile() {
    if (!personProfile || !personNameInput || !personFaces) {
      return;
    }
    const peopleSel = selectedPeople();
    if (peopleSel.length !== 1) {
      personProfile.hidden = true;
      return;
    }
    const id = peopleSel[0];
    const person = peopleCatalog.filter(function (row) { return row.id === id; })[0] || { id: id, name: null };
    personProfile.hidden = false;
    if (document.activeElement !== personNameInput) {
      personNameInput.value = person.name || "";
      personNameInput.dataset.personId = id;
    }
    const thumbs = collectPersonFaces(id).sort(function (a, b) {
      const scoreA = Number(a.detScore || a.matchScore || 0);
      const scoreB = Number(b.detScore || b.matchScore || 0);
      const areaA = a.box && a.box.length === 4 ? a.box[2] * a.box[3] : 0;
      const areaB = b.box && b.box.length === 4 ? b.box[2] * b.box[3] : 0;
      return (scoreB - scoreA) || (areaB - areaA);
    });
    const nextKeys = thumbs.map(faceChoiceKey).join("|");
    if (personFaces.dataset.personId === id && personFaces.dataset.keys === nextKeys && personFaces.childNodes.length === thumbs.length) {
      syncFaceChoicePressed(id);
      return;
    }
    personFaces.dataset.personId = id;
    personFaces.dataset.keys = nextKeys;
    personFaces.innerHTML = "";
    thumbs.forEach(function (thumb) {
      const wrap = document.createElement("div");
      wrap.className = "person-face-wrap";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "person-face-choice";
      btn.dataset.itemId = thumb.itemId || "";
      btn.dataset.box = JSON.stringify(thumb.box || null);
      btn.setAttribute("aria-pressed", "false");
      btn.title = "Use this face as the thumbnail";
      btn.draggable = false;
      const crop = document.createElement("span");
      crop.className = "person-face";
      crop.style.width = "100%";
      crop.style.height = "100%";
      paintFace(crop, thumb);
      btn.appendChild(crop);
      function pick(event) {
        if (event.button != null && event.button !== 0) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (event.stopImmediatePropagation) {
          event.stopImmediatePropagation();
        }
        choosePersonThumb(id, thumb);
      }
      btn.addEventListener("pointerdown", pick);
      btn.addEventListener("click", pick);
      wrap.appendChild(btn);
      const split = document.createElement("button");
      split.type = "button";
      split.className = "face-split";
      split.textContent = t("notThisPerson");
      split.title = t("notThisPerson");
      split.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        splitFace(id, thumb.itemId, thumb.box || null);
      });
      wrap.appendChild(split);
      personFaces.appendChild(wrap);
    });
    syncFaceChoicePressed(id);
  }

  function faceChoiceKey(thumb) {
    return String((thumb && thumb.itemId) || "") + ":" + JSON.stringify((thumb && thumb.box) || null);
  }

  function boxesEqual(a, b) {
    if (!a || !b || a.length !== 4 || b.length !== 4) {
      return JSON.stringify(a || null) === JSON.stringify(b || null);
    }
    for (let i = 0; i < 4; i += 1) {
      if (Math.abs(Number(a[i]) - Number(b[i])) > 0.0001) {
        return false;
      }
    }
    return true;
  }

  function faceIsChosen(person, thumb) {
    if (!person || !thumb || !thumb.itemId) {
      return false;
    }
    if (pendingThumb && pendingThumb.personId === person.id) {
      if (pendingThumb.itemId !== thumb.itemId) {
        return false;
      }
      if (pendingThumb.box && thumb.box) {
        return boxesEqual(pendingThumb.box, thumb.box);
      }
      return !pendingThumb.box;
    }
    const chosenId = (person.thumbnail && person.thumbnail.itemId) || person.thumbnailItemId || "";
    if (!chosenId || thumb.itemId !== chosenId) {
      return false;
    }
    const chosenBox = person.thumbnail && person.thumbnail.box;
    if (chosenBox && thumb.box) {
      return boxesEqual(chosenBox, thumb.box);
    }
    return !chosenBox;
  }

  function renderPeople() {
    if (!peopleList) {
      return;
    }
    const rows = visiblePeople();
    if (peopleEmpty) {
      peopleEmpty.hidden = rows.length > 0;
    }
    peopleList.innerHTML = "";
    if (peopleMergeBtn) {
      peopleMergeBtn.hidden = selectedPeople().length < 2;
    }
    rows.forEach(function (person) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "person-row";
      btn.dataset.personId = person.id;
      btn.setAttribute("aria-pressed", selectedPeople().indexOf(person.id) >= 0 ? "true" : "false");
      const face = document.createElement("span");
      face.className = "person-face";
      paintFace(face, person.thumbnail);
      const meta = document.createElement("span");
      meta.className = "person-meta";
      const name = document.createElement("span");
      name.className = "person-name";
      name.textContent = personDisplayName(person);
      const count = document.createElement("span");
      count.className = "person-count";
      count.textContent = String(person.itemCount || 0);
      meta.appendChild(name);
      meta.appendChild(count);
      btn.appendChild(face);
      btn.appendChild(meta);
      btn.addEventListener("click", function (event) {
        if (event.target && event.target.closest && event.target.closest(".person-face-choice")) {
          event.stopPropagation();
          return;
        }
        selectPerson(person.id, event.metaKey || event.ctrlKey);
      });
      li.appendChild(btn);
      peopleList.appendChild(li);
    });
    renderPersonProfile();
  }

  function loadPeople() {
    return fetch("/api/people").then(readJson).then(function (body) {
      peopleCatalog = (body && body.people) || [];
      if (body && body.personOfInterestMin != null) {
        personOfInterestMin = Number(body.personOfInterestMin) || 3;
      }
      if (pendingThumb) {
        peopleCatalog.forEach(function (row) {
          if (row.id === pendingThumb.personId) {
            row.thumbnailItemId = pendingThumb.itemId;
            row.thumbnail = { itemId: pendingThumb.itemId, box: pendingThumb.box || null };
          }
        });
      }
      renderPeople();
      renderActiveFilters();
      return body;
    }).catch(function () {
      return null;
    });
  }

  function renderTags() {
    if (!tagsList) {
      return;
    }
    const rows = tagsCatalog.slice();
    if (tagsEmpty) {
      tagsEmpty.hidden = rows.length > 0;
    }
    tagsList.innerHTML = "";
    rows.forEach(function (tag) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag-row";
      btn.dataset.tagId = tag.id;
      btn.setAttribute("aria-pressed", selectedThings().indexOf(tag.id) >= 0 ? "true" : "false");
      const name = document.createElement("span");
      name.textContent = tag.name || tag.id;
      const count = document.createElement("span");
      count.textContent = String(tag.itemCount || 0);
      btn.appendChild(name);
      btn.appendChild(count);
      btn.addEventListener("click", function (event) {
        selectTag(tag.id, event.metaKey || event.ctrlKey);
      });
      li.appendChild(btn);
      tagsList.appendChild(li);
    });
    if (tagPick) {
      const current = tagPick.value;
      tagPick.innerHTML = "";
      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = t("tag");
      tagPick.appendChild(blank);
      rows.forEach(function (tag) {
        const opt = document.createElement("option");
        opt.value = tag.id;
        opt.textContent = tag.name || tag.id;
        tagPick.appendChild(opt);
      });
      if (current) {
        tagPick.value = current;
      }
    }
  }

  function loadTags() {
    return fetch("/api/tags").then(readJson).then(function (body) {
      tagsCatalog = (body && body.tags) || [];
      renderTags();
      renderActiveFilters();
      return body;
    }).catch(function () {
      return null;
    });
  }

  function selectTag(id, additive) {
    if (!id) {
      return;
    }
    const current = selectedThings();
    const already = current.indexOf(id) >= 0;
    const next = copyFilter(filter);
    if (additive) {
      next.thing = csvToggle(filter.thing, id, true);
    } else if (already) {
      next.thing = csvWithout(filter.thing, id);
    } else {
      next.q = "";
      next.scope = "";
      next.person = "";
      next.place = "";
      next.thing = id;
    }
    applyFilterState(next, next.q);
    renderKey = "";
    return loadCatalog();
  }

  function selectedItemIds() {
    if (selectedIds.length) {
      return selectedIds.slice();
    }
    if (viewerItemId) {
      return [viewerItemId];
    }
    if (selectedId) {
      return [selectedId];
    }
    return [];
  }

  function createTagFromBox() {
    if (!tagNewInput) {
      return Promise.resolve();
    }
    const name = tagNewInput.value.trim();
    if (!name) {
      return Promise.resolve();
    }
    return fetch("/api/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name }),
    }).then(readJson).then(function (row) {
      tagNewInput.value = "";
      return loadTags().then(function () {
        if (row && row.id && tagPick) {
          tagPick.value = row.id;
        }
        const ids = selectedItemIds();
        if (row && row.id && ids.length) {
          return applyTagsToItems(ids, [row.id], []);
        }
      });
    });
  }

  function applyTagsToItems(itemIds, add, remove) {
    if (!itemIds.length || (!add.length && !remove.length)) {
      return Promise.resolve();
    }
    return fetch("/api/items/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itemIds: itemIds, add: add, remove: remove }),
    }).then(readJson).then(function () {
      return Promise.all([loadTags(), loadCatalog()]);
    });
  }

  function pickTagId() {
    if (tagPick && tagPick.value) {
      return tagPick.value;
    }
    if (tagNewInput && tagNewInput.value.trim()) {
      return tagNewInput.value.trim();
    }
    return "";
  }

  function selectPerson(id, additive) {
    if (!id) {
      return;
    }
    const current = selectedPeople();
    const already = current.indexOf(id) >= 0;
    const next = copyFilter(filter);
    if (additive) {
      next.person = csvToggle(filter.person, id, true);
    } else if (already) {
      next.person = csvWithout(filter.person, id);
    } else {
      next.q = "";
      next.scope = "";
      next.place = "";
      next.thing = "";
      next.person = id;
    }
    applyFilterState(next, next.q);
    renderKey = "";
    return loadCatalog();
  }

  function savePerson(personId, payload) {
    return fetch("/api/people/" + encodeURIComponent(personId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(readJson).then(function (row) {
      if (payload && Object.prototype.hasOwnProperty.call(payload, "thumbnailItemId") && !Object.prototype.hasOwnProperty.call(payload, "name")) {
        return row;
      }
      return loadPeople();
    });
  }

  function syncFaceChoicePressed(personId) {
    if (!personFaces) {
      return;
    }
    const person = peopleCatalog.filter(function (row) { return row.id === personId; })[0] || { id: personId };
    let marked = false;
    Array.prototype.forEach.call(personFaces.querySelectorAll(".person-face-choice"), function (btn) {
      let box = null;
      try {
        box = JSON.parse(btn.dataset.box || "null");
      } catch (err) {
        box = null;
      }
      const on = !marked && faceIsChosen(person, { itemId: btn.dataset.itemId, box: box });
      if (on) {
        marked = true;
      }
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function choosePersonThumb(personId, thumb) {
    const itemId = thumb && thumb.itemId;
    if (!personId || !itemId) {
      return;
    }
    if (pendingThumb && pendingThumb.personId === personId && pendingThumb.itemId === itemId && boxesEqual(pendingThumb.box, thumb.box || null)) {
      syncFaceChoicePressed(personId);
      return;
    }
    pendingThumb = { personId: personId, itemId: itemId, box: thumb.box || null };
    peopleCatalog.forEach(function (row) {
      if (row.id === personId) {
        row.thumbnailItemId = itemId;
        row.thumbnail = { itemId: itemId, box: thumb.box || null };
      }
    });
    syncFaceChoicePressed(personId);
    const face = peopleList && peopleList.querySelector('.person-row[data-person-id="' + personId + '"] .person-face');
    if (face) {
      paintFace(face, { itemId: itemId, box: thumb.box || null });
    }
    savePerson(personId, { thumbnailItemId: itemId }).catch(function () {
      pendingThumb = null;
      loadPeople();
    });
  }

  function splitFace(personId, itemId, box) {
    if (!personId || !itemId) {
      return Promise.resolve();
    }
    const body = { personId: personId, itemId: itemId };
    if (box && box.length === 4) {
      body.box = box;
    }
    return fetch("/api/people/split", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(readJson).then(function (row) {
      const nextId = row && row.id;
      return loadPeople().then(function () {
        if (nextId) {
          return selectPerson(nextId);
        }
        return loadCatalog();
      });
    });
  }

  function joinPersonNames(list) {
    if (!list.length) {
      return "";
    }
    if (list.length === 1) {
      return list[0];
    }
    if (language === "zh-Hans") {
      return list.join("、");
    }
    if (list.length === 2) {
      return list[0] + " and " + list[1];
    }
    return list.slice(0, -1).join(", ") + ", and " + list[list.length - 1];
  }

  function askMergePeople() {
    const ids = selectedPeople();
    if (ids.length < 2) {
      return;
    }
    const keepId = ids[0];
    const dropIds = ids.slice(1);
    const keep = peopleCatalog.filter(function (row) { return row.id === keepId; })[0] || { id: keepId, name: null };
    const dropNames = dropIds.map(function (id) {
      const row = peopleCatalog.filter(function (person) { return person.id === id; })[0];
      return personDisplayName(row || { id: id, name: null });
    });
    pendingMerge = { keepId: keepId, dropIds: dropIds };
    if (confirmMergeTitle) {
      confirmMergeTitle.textContent = t("mergeTitle", { name: personDisplayName(keep) });
    }
    if (confirmMergeHelp) {
      confirmMergeHelp.textContent = t("mergeHelp", {
        name: personDisplayName(keep),
        names: joinPersonNames(dropNames),
      });
    }
    if (confirmMerge && confirmMerge.showModal) {
      confirmMerge.showModal();
      return;
    }
    if (window.confirm(t("mergeTitle", { name: personDisplayName(keep) }))) {
      runPendingMerge();
    }
  }

  function runPendingMerge() {
    const job = pendingMerge;
    pendingMerge = null;
    if (!job || !job.keepId || !job.dropIds || !job.dropIds.length) {
      return Promise.resolve();
    }
    let chain = Promise.resolve();
    job.dropIds.forEach(function (dropId) {
      chain = chain.then(function () {
        return fetch("/api/people/merge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keepId: job.keepId, dropId: dropId }),
        }).then(readJson);
      });
    });
    return chain.then(function () {
      const next = copyFilter(filter);
      next.person = job.keepId;
      applyFilterState(next, next.q);
      renderKey = "";
      return Promise.all([loadPeople(), loadCatalog()]);
    });
  }

  function commitPersonName() {
    if (!personNameInput) {
      return;
    }
    const personId = personNameInput.dataset.personId;
    if (!personId) {
      return;
    }
    const value = personNameInput.value.trim();
    const current = peopleCatalog.filter(function (row) { return row.id === personId; })[0];
    const existing = current && current.name ? current.name : "";
    if (value === existing) {
      return;
    }
    savePerson(personId, { name: value || null }).then(function () {
      return loadCatalog();
    });
  }

  function applySectionLayout() {
    if (librarySide) {
      librarySide.classList.toggle("people-collapsed", !peopleOpen);
      librarySide.classList.toggle("tags-collapsed", !tagsOpen);
      librarySide.style.setProperty("--people-share", String(peopleShare));
    }
    if (peopleToggle) {
      peopleToggle.setAttribute("aria-expanded", peopleOpen ? "true" : "false");
      peopleToggle.setAttribute("aria-label", t(peopleOpen ? "collapsePeople" : "expandPeople"));
    }
    if (tagsToggle) {
      tagsToggle.setAttribute("aria-expanded", tagsOpen ? "true" : "false");
      tagsToggle.setAttribute("aria-label", t(tagsOpen ? "collapseTags" : "expandTags"));
    }
    if (sideVsplit) {
      sideVsplit.hidden = !(peopleOpen && tagsOpen);
    }
  }

  function applySideLayout() {
    if (!workspace) {
      return;
    }
    workspace.classList.toggle("side-collapsed", !sideOpen);
    workspace.style.setProperty("--side-width", sideWidth + "px");
    if (librarySide) {
      librarySide.setAttribute("aria-hidden", sideOpen ? "false" : "true");
    }
    if (sideCollapse) {
      sideCollapse.setAttribute("aria-expanded", sideOpen ? "true" : "false");
      sideCollapse.textContent = t("hide");
    }
    if (librarySplitter) {
      librarySplitter.title = sideOpen ? t("resizePeople") : t("showPanel");
    }
    applySectionLayout();
  }

  function toggleSide(open) {
    sideOpen = open == null ? !sideOpen : !!open;
    applySideLayout();
  }

  function jobsLine(body) {
    if (!body || body.paused) {
      const pending = ((body && body.queues) || []).reduce(function (sum, q) {
        return sum + (q.pending || 0);
      }, 0);
      return pending ? t("pausedWaiting", { n: pending }) : t("paused");
    }
    if (body.processing) {
      const active = (body.queues || []).filter(function (q) { return q.state === "running"; });
      const bits = active.map(function (q) {
        return I18N.queueLabel(q.id, q.label) + " " + q.pending;
      });
      return bits.length ? t("processingLine", { bits: bits.join(" · ") }) : t("processing");
    }
    return t("idle");
  }

  function renderJobs(body) {
    lastJobs = body;
    if (!jobsStatus || !jobsQueues) {
      return;
    }
    jobsStatus.textContent = jobsLine(body);
    jobsStatus.dataset.state = body && body.paused ? "paused" : (body && body.processing ? "running" : "idle");
    jobsQueues.innerHTML = "";
    ((body && body.queues) || []).forEach(function (queue) {
      const li = document.createElement("li");
      li.dataset.id = queue.id;
      li.dataset.state = queue.state || "idle";
      const extra = queue.available ? "" : " (" + t("queued") + ")";
      li.textContent = I18N.queueLabel(queue.id, queue.label) + " · " + (queue.pending || 0) + " " + t("left") + extra;
      jobsQueues.appendChild(li);
    });
    const pending = ((body && body.queues) || []).some(function (q) { return (q.pending || 0) > 0; });
    if (jobsPause) {
      jobsPause.disabled = !(body && body.processing);
    }
    if (jobsResume) {
      jobsResume.disabled = !!(body && body.processing);
      jobsResume.textContent = body && body.paused ? t("resume") : t("start");
      if (!pending && !(body && body.paused)) {
        jobsResume.textContent = t("start");
      }
    }
  }

  function loadJobs() {
    return fetch("/api/jobs").then(readJson).then(function (body) {
      renderJobs(body);
      return body;
    }).catch(function () {
      return null;
    });
  }

  function postJobs(action) {
    return fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action }),
    }).then(readJson).then(function (body) {
      renderJobs(body);
      return body;
    });
  }

  function groupsQuery() {
    if (arrangeBy !== "dates") {
      return queryString({ by: arrangeBy });
    }
    return queryString({ level: settings.zoomLevel });
  }

  function catalogNeedsStills() {
    if (lastJobs && lastJobs.queues) {
      for (let i = 0; i < lastJobs.queues.length; i += 1) {
        const queue = lastJobs.queues[i];
        if (queue && queue.id === "renditions" && (queue.pending || 0) > 0) {
          return true;
        }
      }
    }
    const catalogItems = items.slice();
    Object.keys(extraById).forEach(function (id) {
      catalogItems.push(extraById[id]);
    });
    for (let i = 0; i < catalogItems.length; i += 1) {
      const item = catalogItems[i];
      const slot = stillWhich(item);
      const status = ((item.renditions || {}).status || {})[slot];
      if (status !== "ready" && status !== "error" && status !== "not-applicable") {
        return true;
      }
    }
    return false;
  }

  function loadCatalog() {
    if (catalogInFlight) {
      catalogQueued = true;
      return catalogInFlight;
    }
    const gen = loadGen + 1;
    loadGen = gen;
    const qs = queryString();
    const togetherIds = selectedPeople();
    loadJobs();
    loadPeople();
    loadTags();
    const leftoverFetches = togetherIds.length >= 2
      ? togetherIds.map(function (id) {
          return fetch("/api/items?" + queryString({ person: id })).then(readJson).catch(function () {
            return [];
          });
        })
      : [];
    catalogInFlight = Promise.all([
      fetch("/api/items?" + qs).then(readJson),
      fetch("/api/groups?" + groupsQuery()).then(readJson).catch(function () {
        return null;
      }),
      fetch("/api/sources").then(readJson).catch(function () {
        return [];
      }),
      fetch("/api/settings").then(readJson).catch(function () {
        return null;
      }),
      Promise.all(leftoverFetches),
    ]).then(function (parts) {
      const nextItems = Array.isArray(parts[0]) ? parts[0] : null;
      if (!nextItems) {
        throw new Error("items");
      }
      const nextGroups = Array.isArray(parts[1]) ? parts[1] : [];
      const sources = Array.isArray(parts[2]) ? parts[2] : [];
      lastSources = sources;
      if (currentView === "settings") {
        renderSettingsSources(lastSources);
      }
      if (parts[3]) {
        applySettings(parts[3]);
      }
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
      const prevIds = items.map(function (it) { return it.id; }).join("\n");
      const prevQs = queryString();
      items = nextItems;
      extraById = {};
      togetherByPerson = {};
      if (togetherIds.length >= 2) {
        const andIds = {};
        nextItems.forEach(function (item) {
          andIds[item.id] = true;
        });
        const leftoverLists = Array.isArray(parts[4]) ? parts[4] : [];
        togetherIds.forEach(function (id, index) {
          const list = Array.isArray(leftoverLists[index]) ? leftoverLists[index] : [];
          const rest = [];
          list.forEach(function (item) {
            if (!item || !item.id || andIds[item.id]) {
              return;
            }
            rest.push(item);
            extraById[item.id] = item;
          });
          togetherByPerson[id] = rest;
        });
      }
      catalogReady = true;
      pruneSelection();
      groups = nextGroups.length ? nextGroups : (arrangeBy === "dates" ? groupsFromItems(items, settings.zoomLevel) : groupsFromArrange(items, arrangeBy));
      renderPeople();
      const open = syncViewerIndex();
      if (open) {
        renderViewerLabels(open);
        syncViewerChrome(open);
        if (open.kind === "video" || open.kind === "live") {
          maybePromoteFullSource(open);
        }
      } else if (!viewer.hidden) {
        syncNavChrome();
      }
      const nextIds = items.map(function (it) { return it.id; }).join("\n");
      if (prevIds && prevIds === nextIds && renderKey && renderKey.indexOf(prevQs) !== -1) {
        paintGridStills();
      } else {
        render();
      }
      if (filter.person || filter.place || filter.thing) {
        refreshInspectorFromItems();
      }
    }).catch(function () {
      showDisconnected(true);
      if (!items.length) {
        render();
      }
    }).then(function () {
      catalogInFlight = null;
      if (catalogQueued) {
        catalogQueued = false;
        return loadCatalog();
      }
      return undefined;
    });
    return catalogInFlight;
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
    const pt = stagePoint(event.clientX, event.clientY);
    zoomAt(factor, pt.x, pt.y);
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
    const next = { q: "", scope: "", person: "", place: "", thing: "", kind: "", favorite: "" };
    if (kind === "person") {
      next.person = id;
    } else if (kind === "place") {
      next.place = id;
    } else if (kind === "thing") {
      next.thing = id;
    }
    applyFilterState(next, "");
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
    applyFilterState({
      q: searchInput ? searchInput.value : "",
      scope: filter.scope,
      person: "",
      place: "",
      thing: "",
      kind: filter.kind,
      favorite: filter.favorite,
    }, searchInput ? searchInput.value : "");
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
      if (namingPersonId) {
        payload.people = [{ id: namingPersonId, name: value }];
      } else {
        payload.people = [{ name: value }];
      }
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
      if (kind === "person") {
        namingPersonId = "";
        delete field.dataset.renameId;
        field.placeholder = "Person";
        const renamed = updated && updated.entities && updated.entities.people
          ? updated.entities.people
          : [];
        items.forEach(function (cached, idx) {
          if (!cached || !cached.entities || !cached.entities.people) {
            return;
          }
          cached.entities.people = cached.entities.people.map(function (rec) {
            const fresh = renamed.find(function (row) {
              return row && rec && row.id === rec.id;
            });
            return fresh || rec;
          });
          items[idx] = cached;
        });
      }
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
    const ids = Array.isArray(id) ? id.filter(Boolean) : (id ? [id] : []);
    pendingRemoveIds = ids;
    pendingRemoveId = ids.length === 1 ? ids[0] : null;
    syncRemoveConfirm();
    if (confirmRemove && confirmRemove.showModal) {
      confirmRemove.showModal();
      return;
    }
    const msg = ids.length > 1
      ? t("removeTitleMany", { n: ids.length }) + " " + t("removeHelpMany")
      : t("removeTitle") + " " + t("removeHelp");
    if (window.confirm(msg)) {
      performRemoveIds(ids);
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

  function afterItemsGone(ids) {
    const gone = {};
    (ids || []).forEach(function (id) {
      gone[id] = true;
    });
    if (viewerItemId && gone[viewerItemId]) {
      hideViewerChrome();
      stayOnLiveOrigin({ library: true, view: "grid" }, "", true);
    }
    selectedIds = selectedIds.filter(function (id) {
      return !gone[id];
    });
    if (selectedId && gone[selectedId]) {
      selectedId = selectedIds.length ? selectedIds[selectedIds.length - 1] : null;
    }
    pendingRemoveId = null;
    pendingRemoveIds = [];
    syncSelectionChrome();
    renderKey = "";
    return loadCatalog();
  }

  function afterItemGone(id) {
    return afterItemsGone(id ? [id] : []);
  }

  function performRemoveIds(ids) {
    const list = (ids || []).filter(Boolean);
    if (!list.length) {
      return Promise.resolve();
    }
    if (list.length === 1) {
      return fetch("/api/items/" + encodeURIComponent(list[0]) + "/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }).then(readJson).then(function () {
        return afterItemsGone(list);
      }).catch(function () {});
    }
    return fetch("/api/items/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itemIds: list }),
    }).then(readJson).then(function () {
      return afterItemsGone(list);
    }).catch(function () {});
  }

  function performRemove(id) {
    return performRemoveIds(id ? [id] : []);
  }

  function favoriteSelected() {
    const ids = selectedIds.length ? selectedIds.slice() : selectedItemIds();
    if (!ids.length) {
      return Promise.resolve();
    }
    const on = selectionFavoriteOn();
    return fetch("/api/items/favorite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itemIds: ids, favorite: on }),
    }).then(readJson).then(function (body) {
      const rows = (body && body.items) || [];
      rows.forEach(function (item) {
        if (item && item.id) {
          setItemFavorite(item.id, !!item.favorite);
        }
      });
      ids.forEach(function (id) {
        setItemFavorite(id, on);
      });
      syncSelectionChrome();
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
      if (viewerItemId) {
        askRemove(viewerItemId);
        return;
      }
      const ids = selectedIds.length ? selectedIds.slice() : selectedItemIds();
      if (ids.length) {
        askRemove(ids);
      }
    });
  }
  if (selectionFavoriteBtn) {
    selectionFavoriteBtn.addEventListener("click", function () {
      favoriteSelected();
    });
  }
  let pendingMoveIds = [];
  let pendingMoveSourceId = "";

  function closeMoveFolder() {
    pendingMoveIds = [];
    pendingMoveSourceId = "";
    if (moveFolder && moveFolder.open) {
      moveFolder.close();
    }
  }

  function sourceDestPath(source) {
    if (!source) {
      return "";
    }
    if (source.mode === "copy-here" && source.copyRoot) {
      return source.path || "";
    }
    return source.path || "";
  }

  function syncMoveConfirm() {
    const n = pendingMoveIds.length;
    const path = moveFolderPath ? (moveFolderPath.value || "").trim() : "";
    if (moveFolderConfirm) {
      moveFolderConfirm.textContent = n && path ? t("moveConfirm", { n: n, path: path }) : "";
    }
    if (moveFolderOk) {
      moveFolderOk.disabled = !(n && path);
    }
  }

  function paintMoveSources() {
    if (!moveFolderSources) {
      return;
    }
    moveFolderSources.innerHTML = "";
    (lastSources || []).forEach(function (source) {
      if (!source || !source.available) {
        return;
      }
      const path = sourceDestPath(source);
      if (!path) {
        return;
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("data-source-id", source.id);
      btn.setAttribute("aria-pressed", source.id === pendingMoveSourceId ? "true" : "false");
      btn.textContent = path;
      btn.addEventListener("click", function () {
        pendingMoveSourceId = source.id;
        if (moveFolderPath) {
          moveFolderPath.value = path;
        }
        paintMoveSources();
        syncMoveConfirm();
      });
      moveFolderSources.appendChild(btn);
    });
  }

  function openMoveFolder(ids) {
    pendingMoveIds = (ids || []).filter(Boolean);
    pendingMoveSourceId = "";
    if (moveFolderError) {
      moveFolderError.hidden = true;
      moveFolderError.textContent = "";
    }
    if (moveFolderReport) {
      moveFolderReport.hidden = true;
      moveFolderReport.textContent = "";
    }
    if (moveFolderPath) {
      moveFolderPath.value = "";
    }
    paintMoveSources();
    syncMoveConfirm();
    if (moveFolder && moveFolder.showModal) {
      moveFolder.showModal();
    }
  }

  function browseMoveFolder() {
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
          pendingMoveSourceId = "";
          if (moveFolderPath) {
            moveFolderPath.value = body.path;
          }
          paintMoveSources();
          syncMoveConfirm();
        }
      });
    }).catch(function () {});
  }

  function performMove() {
    const ids = pendingMoveIds.slice();
    const path = moveFolderPath ? (moveFolderPath.value || "").trim() : "";
    if (!ids.length || !path) {
      return Promise.resolve();
    }
    const body = { itemIds: ids };
    if (pendingMoveSourceId) {
      const chosen = (lastSources || []).find(function (source) {
        return source && source.id === pendingMoveSourceId;
      });
      if (chosen && sourceDestPath(chosen) === path) {
        body.sourceId = pendingMoveSourceId;
      } else {
        body.destination = path;
      }
    } else {
      body.destination = path;
    }
    if (moveFolderError) {
      moveFolderError.hidden = true;
      moveFolderError.textContent = "";
    }
    return fetch("/api/items/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(readJson).then(function (payload) {
      const moved = (payload && payload.moved) || [];
      const skipped = (payload && payload.skipped) || [];
      let renamed = 0;
      moved.forEach(function (row) {
        (row.files || []).forEach(function (file) {
          if (file && file.renamed) {
            renamed += 1;
          }
        });
      });
      if (moveFolderReport) {
        moveFolderReport.hidden = false;
        moveFolderReport.textContent = t("moveReport", {
          moved: moved.length,
          renamed: renamed,
          skipped: skipped.length,
        });
      }
      renderKey = "";
      return loadCatalog().then(function () {
        closeMoveFolder();
      });
    }).catch(function (err) {
      if (moveFolderError) {
        moveFolderError.hidden = false;
        moveFolderError.textContent = (err && err.body && err.body.error) || "invalid-argument";
      }
    });
  }

  if (selectionMoveBtn) {
    selectionMoveBtn.addEventListener("click", function () {
      const ids = selectedIds.slice();
      if (ids.length) {
        openMoveFolder(ids);
      }
    });
  }
  if (moveFolderCancel) {
    moveFolderCancel.addEventListener("click", function () {
      closeMoveFolder();
    });
  }
  if (moveFolderOk) {
    moveFolderOk.addEventListener("click", function () {
      performMove();
    });
  }
  if (moveFolderBrowse) {
    moveFolderBrowse.addEventListener("click", function () {
      browseMoveFolder();
    });
  }
  if (moveFolderPath) {
    moveFolderPath.addEventListener("input", function () {
      pendingMoveSourceId = "";
      paintMoveSources();
      syncMoveConfirm();
    });
  }
  if (selectionRemoveBtn) {
    selectionRemoveBtn.addEventListener("click", function () {
      const ids = selectedIds.slice();
      if (ids.length) {
        askRemove(ids);
      }
    });
  }
  if (selectionClearBtn) {
    selectionClearBtn.addEventListener("click", function () {
      clearSelection();
    });
  }
  if (selectionCompareBtn) {
    selectionCompareBtn.addEventListener("click", function () {
      openCompareForIds(selectedIds.slice());
    });
  }
  if (filterDuplicatesBtn) {
    filterDuplicatesBtn.addEventListener("click", function () {
      openDetectedCompare();
    });
  }
  if (duplicateCompareCancel) {
    duplicateCompareCancel.addEventListener("click", function () {
      closeCompare();
    });
  }
  if (duplicateCompareApply) {
    duplicateCompareApply.addEventListener("click", function () {
      applyCompareChoices();
    });
  }
  if (duplicateComparePrev) {
    duplicateComparePrev.addEventListener("click", function () {
      if (compareIndex > 0) {
        compareIndex -= 1;
        paintCompare();
      }
    });
  }
  if (duplicateCompareNext) {
    duplicateCompareNext.addEventListener("click", function () {
      if (compareIndex < compareGroups.length - 1) {
        compareIndex += 1;
        paintCompare();
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
        const ids = pendingRemoveIds.length ? pendingRemoveIds.slice() : (pendingRemoveId ? [pendingRemoveId] : []);
        confirmRemove.close();
        if (ids.length) {
          performRemoveIds(ids);
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
  if (confirmMerge) {
    const cancelMerge = document.getElementById("confirm-merge-cancel");
    const okMerge = document.getElementById("confirm-merge-ok");
    if (cancelMerge) {
      cancelMerge.addEventListener("click", function () {
        pendingMerge = null;
        confirmMerge.close();
      });
    }
    if (okMerge) {
      okMerge.addEventListener("click", function () {
        confirmMerge.close();
        runPendingMerge();
      });
    }
  }
  if (peopleMergeBtn) {
    peopleMergeBtn.addEventListener("click", function (event) {
      event.preventDefault();
      askMergePeople();
    });
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
    const next = copyFilter(filter);
    next.kind = kind || "";
    next.favorite = favorite || "";
    applyFilterState(next, next.q);
    renderKey = "";
    loadCatalog();
  }

  function paintSelection() {
    main.querySelectorAll(".cell").forEach(function (cell) {
      cell.classList.toggle("selected", selectedIds.indexOf(cell.dataset.id) >= 0);
    });
    if (main) {
      main.dataset.selected = selectedIds.join(",");
    }
  }

  function toggleSelectedId(id) {
    const idx = selectedIds.indexOf(id);
    if (idx >= 0) {
      selectedIds.splice(idx, 1);
    } else {
      selectedIds.push(id);
    }
    selectedId = id;
    lastClickedId = id;
    paintSelection();
    syncSelectionChrome();
  }

  function selectRange(fromId, toId) {
    const order = items.map(function (item) { return item.id; });
    const a = order.indexOf(fromId);
    const b = order.indexOf(toId);
    if (a < 0 || b < 0) {
      toggleSelectedId(toId);
      return;
    }
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    selectedIds = order.slice(lo, hi + 1);
    selectedId = toId;
    lastClickedId = toId;
    paintSelection();
    syncSelectionChrome();
  }

  function setArrange(value) {
    const next = value === "people" || value === "places" || value === "tags" ? value : "dates";
    if (next === arrangeBy) {
      return;
    }
    arrangeBy = next;
    renderKey = "";
    if (arrangeBy === "dates") {
      groups = groupsFromItems(items, settings.zoomLevel);
      render();
      return;
    }
    return loadCatalog();
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
  function onSizeSliderInput(event) {
    setGridSize(Number(event.target.value));
    if (sizeSlider && sizeSlider !== event.target) {
      sizeSlider.value = String(gridSize);
    }
  }
  if (sizeSlider) {
    sizeSlider.addEventListener("input", onSizeSliderInput);
    sizeSlider.addEventListener("change", onSizeSliderInput);
  }
  main.addEventListener("pointerover", function (event) {
    const cell = event.target && event.target.closest ? event.target.closest("#grid .cell") : null;
    if (!cell) {
      return;
    }
    hoveredId = cell.dataset.id;
    startHover(cell, itemById(cell.dataset.id));
  });
  main.addEventListener("pointerout", function (event) {
    const cell = event.target && event.target.closest ? event.target.closest("#grid .cell") : null;
    if (!cell) {
      return;
    }
    const related = event.relatedTarget;
    if (related && cell.contains(related)) {
      return;
    }
    if (hoverCell === cell) {
      if (hoveredId === cell.dataset.id) {
        hoveredId = null;
      }
      stopHover();
    }
  });
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
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", function () {
      clearAllFilters();
    });
  }
  if (arrangeSelect) {
    arrangeSelect.addEventListener("change", function () {
      setArrange(arrangeSelect.value);
    });
  }
  if (tagCreateBtn) {
    tagCreateBtn.addEventListener("click", function () {
      createTagFromBox();
    });
  }
  if (tagNewInput) {
    tagNewInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        createTagFromBox();
      }
    });
  }
  if (tagApplyBtn) {
    tagApplyBtn.addEventListener("click", function () {
      const token = pickTagId();
      if (token) {
        applyTagsToItems(selectedItemIds(), [token], []);
      }
    });
  }
  if (tagRemoveBtn) {
    tagRemoveBtn.addEventListener("click", function () {
      const token = pickTagId();
      if (token) {
        applyTagsToItems(selectedItemIds(), [], [token]);
      }
    });
  }
  if (dateGroupSelect) {
    dateGroupSelect.addEventListener("change", function () {
      setDateMode(dateGroupSelect.value, true);
    });
  }
  if (sideCollapse) {
    sideCollapse.addEventListener("click", function () {
      toggleSide(false);
    });
  }
  if (peopleToggle) {
    peopleToggle.addEventListener("click", function () {
      peopleOpen = !peopleOpen;
      applySectionLayout();
    });
  }
  if (tagsToggle) {
    tagsToggle.addEventListener("click", function () {
      tagsOpen = !tagsOpen;
      applySectionLayout();
    });
  }
  if (sideVsplit) {
    sideVsplit.addEventListener("pointerdown", function (event) {
      if (!peopleOpen || !tagsOpen) {
        return;
      }
      vSplitDragging = true;
      sideVsplit.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    sideVsplit.addEventListener("pointermove", function (event) {
      if (!vSplitDragging || !librarySide) {
        return;
      }
      const peopleEl = document.getElementById("people-panel");
      const jobsEl = document.getElementById("jobs-panel");
      if (!peopleEl) {
        return;
      }
      const top = peopleEl.getBoundingClientRect().top;
      const bottom = jobsEl ? jobsEl.getBoundingClientRect().top : librarySide.getBoundingClientRect().bottom;
      const span = Math.max(80, bottom - top);
      peopleShare = Math.max(0.22, Math.min(0.78, (event.clientY - top) / span));
      applySectionLayout();
    });
    sideVsplit.addEventListener("pointerup", function () {
      window.setTimeout(function () {
        vSplitDragging = false;
      }, 0);
    });
  }
  if (librarySplitter) {
    librarySplitter.addEventListener("click", function () {
      if (!splitDragging && !sideOpen) {
        toggleSide(true);
      }
    });
    librarySplitter.addEventListener("dblclick", function () {
      toggleSide();
    });
    librarySplitter.addEventListener("pointerdown", function (event) {
      if (!sideOpen) {
        return;
      }
      splitDragging = true;
      librarySplitter.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    librarySplitter.addEventListener("pointermove", function (event) {
      if (!splitDragging || !workspace) {
        return;
      }
      const rect = workspace.getBoundingClientRect();
      const next = Math.round(rect.right - event.clientX);
      sideWidth = Math.max(180, Math.min(420, next));
      applySideLayout();
    });
    librarySplitter.addEventListener("pointerup", function () {
      window.setTimeout(function () {
        splitDragging = false;
      }, 0);
    });
  }
  if (personNameInput) {
    personNameInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        commitPersonName();
      }
    });
    personNameInput.addEventListener("blur", commitPersonName);
  }
  if (jobsPause) {
    jobsPause.addEventListener("click", function () {
      postJobs("pause");
    });
  }
  if (jobsResume) {
    jobsResume.addEventListener("click", function () {
      postJobs("resume");
    });
  }
  if (jobsRerunFaces) {
    jobsRerunFaces.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      postJobs("rerun-faces");
    });
  }
  applySideLayout();

  function wheelTargetIsChrome(event) {
    const node = event.target;
    if (!node || !node.closest) {
      return false;
    }
    return !!node.closest("input, select, textarea, button, label, a, #viewer-info-panel");
  }

  function onViewerWheel(event) {
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
  }
  viewer.addEventListener("wheel", onViewerWheel, { passive: false, capture: true });

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
    if ((event.ctrlKey || event.metaKey) && event.key === ",") {
      event.preventDefault();
      openSettings();
      return;
    }
    if (event.key === "F5") {
      event.preventDefault();
      startSlideshow();
      return;
    }
    if (event.key === "Escape") {
      if (moveFolder && moveFolder.open) {
        event.preventDefault();
        closeMoveFolder();
        return;
      }
      if (confirmRemove && confirmRemove.open) {
        event.preventDefault();
        confirmRemove.close();
        return;
      }
      if (compareOpen()) {
        event.preventDefault();
        closeCompare();
        return;
      }
      if (confirmDeleteFile && confirmDeleteFile.open) {
        event.preventDefault();
        confirmDeleteFile.close();
        return;
      }
      if (confirmMerge && confirmMerge.open) {
        event.preventDefault();
        pendingMerge = null;
        confirmMerge.close();
        return;
      }
      if (confirmRemoveSource && confirmRemoveSource.open) {
        event.preventDefault();
        confirmRemoveSource.close();
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
        return;
      }
      if (currentView === "settings") {
        event.preventDefault();
        showView(previousView === "settings" ? "library" : previousView);
        return;
      }
      if (selectedIds.length) {
        event.preventDefault();
        clearSelection();
        return;
      }
      return;
    }
    if (event.key === "Delete" && !textFocused()) {
      if ((confirmRemove && confirmRemove.open) || (confirmDeleteFile && confirmDeleteFile.open) || (confirmMerge && confirmMerge.open)) {
        return;
      }
      if (viewerItemId) {
        event.preventDefault();
        askRemove(viewerItemId);
        return;
      }
      const ids = selectedIds.length ? selectedIds.slice() : (selectedId ? [selectedId] : []);
      if (!ids.length) {
        return;
      }
      event.preventDefault();
      askRemove(ids);
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
  if (viewerMute) {
    viewerMute.addEventListener("click", function () {
      viewerMuted = !viewerMuted;
      if (!viewerMuted && viewerVolume <= 0) {
        viewerVolume = 1;
      }
      applyViewerVolume();
    });
  }
  if (viewerVolumeSlider) {
    viewerVolumeSlider.addEventListener("input", function () {
      viewerVolume = Math.max(0, Math.min(1, Number(viewerVolumeSlider.value) / 100));
      viewerMuted = viewerVolume <= 0;
      applyViewerVolume();
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
  if (viewSettings) {
    viewSettings.addEventListener("click", function () {
      openSettings();
    });
  }
  if (settingsAddFolder) {
    settingsAddFolder.addEventListener("click", openAddDialog);
  }
  if (confirmRemoveSource) {
    const cancelSource = document.getElementById("confirm-remove-source-cancel");
    const okSource = document.getElementById("confirm-remove-source-ok");
    if (cancelSource) {
      cancelSource.addEventListener("click", function () {
        confirmRemoveSource.close();
      });
    }
    if (okSource) {
      okSource.addEventListener("click", function () {
        const id = pendingSourceId;
        confirmRemoveSource.close();
        performRemoveSource(id);
      });
    }
  }
  wireSettingsForm();

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
  function onViewerZoomSlider() {
    const box = viewerBox();
    setZoomPercent(Number(viewerZoomSlider.value), box.w / 2, box.h / 2);
    syncZoomChrome();
  }
  viewerZoomSlider.addEventListener("input", onViewerZoomSlider);
  viewerZoomSlider.addEventListener("change", onViewerZoomSlider);
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

  function updateStatusText(body) {
    if (!body) {
      return t("updateUnavailable");
    }
    const sha = body.git_sha || body.revision || "";
    const branch = body.git_branch || body.branch || "main";
    const code = body.code || body.reason || "";
    if (body.restarting || code === "restarting") {
      return t("updateRestarting", { sha: sha, branch: branch });
    }
    if (body.ok && body.alreadyCurrent) {
      return t("updateAlready", { sha: sha, branch: branch });
    }
    if (body.ok && body.updated) {
      return t("updateDone", { sha: sha, branch: branch });
    }
    if (code === "git-missing") {
      return t("updateGitMissing");
    }
    if (code === "not-a-git-copy") {
      return t("updateNotGit");
    }
    if (code === "diverged") {
      return t("updateDiverged");
    }
    if (code === "need-public") {
      return t("updateNeedPublic");
    }
    if (code === "fetch-failed" || code === "pull-failed" || code === "timeout") {
      return t("updateFailed");
    }
    if (body.error === "update-unavailable" || code === "update-unavailable") {
      return t("updateUnavailable");
    }
    return body.message || t("updateUnavailable");
  }

  function waitForLibraryRestart() {
    let sawDown = false;
    let tries = 0;
    const timer = window.setInterval(function () {
      tries += 1;
      fetch("/api/health").then(function (res) {
        if (!res.ok) {
          sawDown = true;
          return;
        }
        if (sawDown || tries > 8) {
          window.clearInterval(timer);
          window.location.reload();
        }
      }).catch(function () {
        sawDown = true;
      });
      if (tries > 50) {
        window.clearInterval(timer);
      }
    }, 400);
  }

  if (updateLibraryBtn) {
    updateLibraryBtn.addEventListener("click", function () {
      updateLibraryBtn.disabled = true;
      if (updateStatus) {
        updateStatus.hidden = false;
        updateStatus.textContent = t("updating");
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
          updateStatus.textContent = updateStatusText(body);
          updateStatus.setAttribute("data-ok", body && body.ok ? "true" : "false");
        }
        if (body && body.ok) {
          applyVersion(body);
        } else {
          loadVersion();
        }
        if (body && body.restarting) {
          waitForLibraryRestart();
        }
      }).catch(function (err) {
        updateLibraryBtn.disabled = false;
        if (updateStatus) {
          updateStatus.hidden = false;
          updateStatus.textContent = updateStatusText(err && err.body) || t("updateUnavailable");
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
        applyFilterState({
          q: filter.q,
          scope: filter.scope === scope ? "" : scope,
          person: "",
          place: "",
          thing: "",
          kind: filter.kind,
          favorite: filter.favorite,
        }, filter.q);
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

  if (languageSelect) {
    languageSelect.addEventListener("change", function () {
      applyLanguage(languageSelect.value, true);
    });
  }

  function gridThumbStats() {
    const cells = main.querySelectorAll('.cell[data-slot="grid"]');
    let painted = 0;
    const files = [];
    cells.forEach(function (cell) {
      const img = cell.querySelector("img");
      const placeholder = cell.querySelector(".placeholder");
      const ok = stillLooksGood(img);
      if (ok) {
        painted += 1;
      }
      files.push({
        file: cell.dataset.filename || "",
        kind: cell.dataset.kind || "",
        painted: !!ok,
        which: (img && (img.getAttribute("data-still") || img.getAttribute("src"))) || "",
        placeholder: !!(placeholder && !placeholder.hidden),
      });
    });
    return { count: cells.length, painted: painted, missing: cells.length - painted, files: files };
  }

  window.libraryTest = {
    loadCatalog: loadCatalog,
    openSettings: openSettings,
    currentView: function () {
      return currentView;
    },
    itemCount: function () {
      return items.length;
    },
    language: function () {
      return language;
    },
    gridThumbs: gridThumbStats,
    paintGridStills: paintGridStills,
    recoverStills: recoverStills,
    stillStats: stillStats,
    peopleOpen: function () {
      return peopleOpen;
    },
    tagsOpen: function () {
      return tagsOpen;
    },
  };

  pollTimer = window.setInterval(function () {
    recoverStills();
    fetch("/api/health").then(function (res) {
      if (!res.ok) {
        showDisconnected(true);
        return;
      }
      showDisconnected(false);
      return loadJobs().then(function () {
        if (scanning || !items.length || catalogNeedsStills() || currentView === "settings") {
          return loadCatalog();
        }
      });
    }).catch(function () {
      showDisconnected(true);
    });
  }, 1000);
  window.addEventListener("beforeunload", function () {
    window.clearInterval(pollTimer);
  });
})();
