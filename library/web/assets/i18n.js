(function (global) {
  const STRINGS = {
    en: {
      library: "Library",
      globe: "Globe",
      search: "Search",
      sort: "Sort",
      newest: "Newest",
      oldest: "Oldest",
      name: "Name",
      location: "Location",
      sortField: "Sort field",
      direction: "Direction",
      newestFirst: "Newest first",
      oldestFirst: "Oldest first",
      date: "Date",
      remove: "Remove",
      deleteFile: "Delete file",
      addFolder: "Add folder",
      addPhotos: "Add photos",
      updateLibrary: "Update Library",
      version: "Library version",
      filters: "Filters",
      filter: "Filter",
      all: "All",
      photos: "Photos",
      videos: "Videos",
      favorites: "Favorites",
      activeFilters: "Active filters",
      clearAll: "Clear all",
      group: "Group",
      groupBy: "Group by Date People Places or Tags",
      dates: "Date",
      people: "People",
      places: "Places",
      tags: "Tags",
      things: "Things",
      newTag: "New tag",
      create: "Create",
      chooseTag: "Choose tag",
      apply: "Apply",
      tag: "Tag",
      disconnected: "Library is not responding",
      retry: "Retry",
      size: "Size",
      sizeSlider: "Grid density thumbnail size",
      datesGroup: "Dates",
      dateGrouping: "Date grouping Years Months Days or Off",
      years: "Years",
      months: "Months",
      days: "Days",
      off: "Off",
      resizePeople: "Resize People panel",
      libraryPanel: "Library panel",
      hide: "Hide",
      showPanel: "Show panel",
      hidePanel: "Hide panel",
      collapsePeople: "Collapse People",
      expandPeople: "Expand People",
      collapseTags: "Collapse Tags",
      expandTags: "Expand Tags",
      resizePeopleTags: "Resize People and Tags",
      noPeople: "No people yet",
      personName: "Person name",
      unnamed: "Unnamed",
      thumbnail: "Thumbnail",
      noTags: "No tags yet",
      processing: "Processing",
      idle: "Idle",
      pause: "Pause",
      start: "Start",
      resume: "Resume",
      rerunFaces: "Re-run Faces",
      rerunFacesTitle: "Re-run face detect with current quality gates",
      play: "Play",
      noLocations: "No locations to show",
      addAFolder: "Add a folder",
      path: "Path",
      browse: "Browse",
      copyHere: "Copy onto this drive",
      copyHereHelp: "Originals travel with this drive.",
      serveThere: "Serve from that folder",
      serveThereHelp: "Originals stay where they are.",
      cancel: "Cancel",
      add: "Add",
      back: "Back",
      favorite: "Favorite",
      unfavorite: "Unfavorite",
      slideshow: "Slideshow",
      slideshowTitle: "Slideshow F5",
      fullscreen: "Fullscreen",
      fullscreenTitle: "Fullscreen F11",
      info: "Info",
      person: "Person",
      place: "Place",
      thing: "Thing",
      originalMissing: "Original is not on this computer",
      previewUnavailable: "Preview is not available",
      zoom: "Zoom Ctrl++ / Ctrl+- · wheel · Ctrl+0 fit · Ctrl+1 100%",
      viewerZoom: "Viewer zoom",
      previous: "Previous",
      previousTitle: "Previous ←",
      rotate: "Rotate",
      rotateTitle: "Rotate Ctrl+R",
      next: "Next",
      nextTitle: "Next →",
      videoPosition: "Video position",
      mute: "Mute",
      unmute: "Unmute",
      volume: "Volume",
      reveal: "Reveal in Explorer",
      open: "Open",
      playPreview: "Play preview",
      addPhotosFirst: "Add photos first",
      removeTitle: "Remove from Library?",
      removeHelp: "The file stays on disk.",
      deleteTitle: "Delete this file from disk?",
      deleteHelp: "This sends the original to the Recycle Bin. The catalog record is then removed.",
      emptyLibrary: "No pictures yet",
      noMatches: "No matches",
      noMatchesFor: "No matches for {q}",
      loadingPictures: "Loading pictures…",
      noneYet: "None yet",
      unknown: "Unknown",
      noPlace: "No place",
      untagged: "Untagged",
      file: "File",
      dateTaken: "Date taken",
      camera: "Camera",
      noCamera: "No camera info for this file.",
      dimensions: "Dimensions",
      fileSize: "Size",
      filePath: "Path",
      gps: "GPS",
      preview: "Preview",
      loadingFull: "Loading full…",
      original: "Original",
      full: "Full",
      previewFullUnavailable: "Preview — full unavailable",
      paused: "Paused",
      pausedWaiting: "Paused — {n} waiting",
      processingLine: "Processing — {bits}",
      queued: "queued",
      left: "left",
      scope: "Scope",
      personChip: "Person: {name}",
      placeChip: "Place: {name}",
      tagChip: "Tag: {name}",
      searchChip: "Search: {q}",
      scopeChip: "Scope: {name}",
      removeLabel: "Remove {name}",
      language: "Language",
      english: "English",
      chinese: "中文",
      views: "Views",
      updating: "Updating…",
      updateAlready: "Already up to date ({sha} on {branch}).",
      updateDone: "Updated to {sha} on {branch}.",
      updateRestarting: "Updated to {sha} on main. Restarting Library...",
      updateGitMissing: "Git is not installed on this computer. Install Git, then try Update again.",
      updateNotGit: "This Library folder is not a git copy, so it cannot pull an update.",
      updateFailed: "Could not pull main. Check the internet, then try Update again.",
      updateDiverged: "This copy is not on main and could not switch. Ask Steve.",
      updateUnavailable: "Update is not available.",
      updateNeedPublic: "Update needs a public download of main. No GitHub login. Ask Steve to make the repo public.",
      familyHint: "First time: Setup.bat, then the Library shortcut. Later: Update Library (restarts by itself).",
    },
    "zh-Hans": {
      library: "图库",
      globe: "地球",
      search: "搜索",
      sort: "排序",
      newest: "最新",
      oldest: "最早",
      name: "名称",
      location: "地点",
      sortField: "排序字段",
      direction: "方向",
      newestFirst: "最新在前",
      oldestFirst: "最早在前",
      date: "日期",
      remove: "移出图库",
      deleteFile: "删除文件",
      addFolder: "添加文件夹",
      addPhotos: "添加照片",
      updateLibrary: "更新图库",
      version: "图库版本",
      filters: "筛选",
      filter: "筛选",
      all: "全部",
      photos: "照片",
      videos: "视频",
      favorites: "收藏",
      activeFilters: "当前筛选",
      clearAll: "清除全部",
      group: "分组",
      groupBy: "按日期、人物、地点或标签分组",
      dates: "日期",
      people: "人物",
      places: "地点",
      tags: "标签",
      things: "事物",
      newTag: "新标签",
      create: "创建",
      chooseTag: "选择标签",
      apply: "应用",
      tag: "标签",
      disconnected: "图库没有响应",
      retry: "重试",
      size: "大小",
      sizeSlider: "缩略图大小",
      datesGroup: "日期",
      dateGrouping: "按年、月、日分组或关闭",
      years: "年",
      months: "月",
      days: "日",
      off: "关闭",
      resizePeople: "调整人物面板宽度",
      libraryPanel: "图库面板",
      hide: "隐藏",
      showPanel: "显示面板",
      hidePanel: "隐藏面板",
      collapsePeople: "收起人物",
      expandPeople: "展开人物",
      collapseTags: "收起标签",
      expandTags: "展开标签",
      resizePeopleTags: "调整人物和标签高度",
      noPeople: "还没有人物",
      personName: "姓名",
      unnamed: "未命名",
      thumbnail: "头像",
      noTags: "还没有标签",
      processing: "处理中",
      idle: "空闲",
      pause: "暂停",
      start: "开始",
      resume: "继续",
      rerunFaces: "重新识别人脸",
      rerunFacesTitle: "用当前质量设置重新检测人脸",
      play: "播放",
      noLocations: "没有可显示的地点",
      addAFolder: "添加文件夹",
      path: "路径",
      browse: "浏览",
      copyHere: "复制到此磁盘",
      copyHereHelp: "原图会跟着这个磁盘走。",
      serveThere: "在原文件夹打开",
      serveThereHelp: "原图留在原来的位置。",
      cancel: "取消",
      add: "添加",
      back: "返回",
      favorite: "收藏",
      unfavorite: "取消收藏",
      slideshow: "幻灯片",
      slideshowTitle: "幻灯片 F5",
      fullscreen: "全屏",
      fullscreenTitle: "全屏 F11",
      info: "信息",
      person: "人物",
      place: "地点",
      thing: "事物",
      originalMissing: "这台电脑上没有原图",
      previewUnavailable: "没有预览",
      zoom: "缩放 Ctrl++ / Ctrl+- · 滚轮 · Ctrl+0 适合窗口 · Ctrl+1 100%",
      viewerZoom: "查看缩放",
      previous: "上一张",
      previousTitle: "上一张 ←",
      rotate: "旋转",
      rotateTitle: "旋转 Ctrl+R",
      next: "下一张",
      nextTitle: "下一张 →",
      videoPosition: "视频进度",
      mute: "静音",
      unmute: "取消静音",
      volume: "音量",
      reveal: "在资源管理器中显示",
      open: "打开",
      playPreview: "播放预览",
      addPhotosFirst: "请先添加照片",
      removeTitle: "从图库中移除？",
      removeHelp: "磁盘上的文件会保留。",
      deleteTitle: "从磁盘删除这个文件？",
      deleteHelp: "原图会进入回收站，然后从图库记录中删除。",
      emptyLibrary: "还没有照片",
      noMatches: "没有匹配结果",
      noMatchesFor: "没有与 {q} 匹配的结果",
      loadingPictures: "正在载入照片…",
      noneYet: "还没有",
      unknown: "未知",
      noPlace: "无地点",
      untagged: "无标签",
      file: "文件",
      dateTaken: "拍摄日期",
      camera: "相机",
      noCamera: "这个文件没有相机信息。",
      dimensions: "尺寸",
      fileSize: "大小",
      filePath: "路径",
      gps: "GPS",
      preview: "预览",
      loadingFull: "正在载入完整画面…",
      original: "原图",
      full: "完整",
      previewFullUnavailable: "预览 — 完整画面不可用",
      paused: "已暂停",
      pausedWaiting: "已暂停 — 还有 {n} 个在等待",
      processingLine: "正在处理 — {bits}",
      queued: "排队中",
      left: "剩余",
      scope: "范围",
      personChip: "人物：{name}",
      placeChip: "地点：{name}",
      tagChip: "标签：{name}",
      searchChip: "搜索：{q}",
      scopeChip: "范围：{name}",
      removeLabel: "移除 {name}",
      language: "语言",
      english: "English",
      chinese: "中文",
      views: "视图",
      updating: "正在更新…",
      updateAlready: "已经是最新（{sha}，{branch}）。",
      updateDone: "已更新到 {sha}（{branch}）。",
      updateRestarting: "已更新到 {sha}（main）。正在重新打开图库…",
      updateGitMissing: "这台电脑还没有安装 Git。请先安装 Git，然后再点更新。",
      updateNotGit: "这个图库文件夹不是 git 副本，所以不能更新。",
      updateFailed: "无法拉取 main。请检查网络后再试。",
      updateDiverged: "这个副本不在 main 上，也无法切换。请让 Steve 来看一下。",
      updateUnavailable: "现在不能更新。",
      updateNeedPublic: "更新需要公开下载 main。不用登录 GitHub。请让 Steve 把仓库设为公开。",
      familyHint: "第一次：先运行 Setup.bat，再用桌面上的图库图标。以后点“更新图库”，会自动重新打开。",
    },
  };

  const QUEUE_KEYS = {
    renditions: { en: "Previews", "zh-Hans": "预览" },
    analyze: { en: "Analyze", "zh-Hans": "分析" },
    "infer-faces": { en: "Faces", "zh-Hans": "人脸" },
    objects: { en: "Objects", "zh-Hans": "物体" },
  };

  let lang = "en";

  function normalize(code) {
    return code === "zh-Hans" || code === "zh" || code === "zh-CN" ? "zh-Hans" : "en";
  }

  function interpolate(text, vars) {
    if (!vars) {
      return text;
    }
    return String(text).replace(/\{(\w+)\}/g, function (_, key) {
      return vars[key] == null ? "" : String(vars[key]);
    });
  }

  function t(key, vars) {
    const pack = STRINGS[lang] || STRINGS.en;
    const text = pack[key] || STRINGS.en[key] || key;
    return interpolate(text, vars);
  }

  function queueLabel(id, fallback) {
    const row = QUEUE_KEYS[id];
    if (row) {
      return row[lang] || row.en;
    }
    return fallback || id;
  }

  function formatDateGroup(key) {
    const raw = String(key || "");
    if (lang !== "zh-Hans") {
      return raw;
    }
    if (/^\d{4}$/.test(raw)) {
      return raw + "年";
    }
    if (/^\d{4}-\d{2}$/.test(raw)) {
      return raw.slice(0, 4) + "年" + String(Number(raw.slice(5))) + "月";
    }
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      return raw.slice(0, 4) + "年" + String(Number(raw.slice(5, 7))) + "月" + String(Number(raw.slice(8))) + "日";
    }
    return raw;
  }

  function applyStatic() {
    const root = document.documentElement;
    if (root) {
      root.lang = lang === "zh-Hans" ? "zh-Hans" : "en";
    }
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      const key = node.getAttribute("data-i18n");
      if (key) {
        node.textContent = t(key);
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (node) {
      const key = node.getAttribute("data-i18n-placeholder");
      if (key) {
        node.setAttribute("placeholder", t(key));
      }
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (node) {
      const key = node.getAttribute("data-i18n-aria");
      if (key) {
        node.setAttribute("aria-label", t(key));
      }
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (node) {
      const key = node.getAttribute("data-i18n-title");
      if (key) {
        node.setAttribute("title", t(key));
      }
    });
  }

  function setLanguage(next) {
    lang = normalize(next);
    applyStatic();
    return lang;
  }

  global.LibraryI18n = {
    t: t,
    setLanguage: setLanguage,
    getLanguage: function () {
      return lang;
    },
    applyStatic: applyStatic,
    queueLabel: queueLabel,
    formatDateGroup: formatDateGroup,
    normalize: normalize,
  };
})(window);
