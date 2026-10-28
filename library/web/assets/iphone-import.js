(function () {
  const dialog = document.getElementById("import-iphone");
  const pathInput = document.getElementById("import-iphone-path");
  const browse = document.getElementById("import-iphone-browse");
  const lookBtn = document.getElementById("import-iphone-look");
  const copyBtn = document.getElementById("import-iphone-copy");
  const closeBtn = document.getElementById("import-iphone-close");
  const phoneEl = document.getElementById("import-iphone-phone");
  const countsEl = document.getElementById("import-iphone-counts");
  const rowsEl = document.getElementById("import-iphone-rows");
  const statusEl = document.getElementById("import-iphone-status");
  const errorEl = document.getElementById("import-iphone-error");
  const liveEl = document.getElementById("import-iphone-live");
  const elapsedEl = document.getElementById("import-iphone-elapsed");
  const rateEl = document.getElementById("import-iphone-rate");
  const folderEl = document.getElementById("import-iphone-folder");
  const foundEl = document.getElementById("import-iphone-found");
  const hereEl = document.getElementById("import-iphone-here");
  const missingEl = document.getElementById("import-iphone-missing");
  const keptEl = document.getElementById("import-iphone-kept");
  const paceEl = document.getElementById("import-iphone-pace");
  if (!dialog || !pathInput || !lookBtn || !copyBtn) {
    return;
  }

  let installed = false;
  let monthReady = false;
  let working = false;
  let poll = 0;
  let clock = 0;
  let added = false;
  let liveJob = null;
  let samples = [];
  let lastCount = null;
  let lastCountAt = 0;
  let paceStamp = "";

  function t(key) {
    if (window.LibraryI18n && window.LibraryI18n.t) {
      return window.LibraryI18n.t(key);
    }
    return key;
  }

  function showError(text) {
    if (!text) {
      errorEl.hidden = true;
      errorEl.textContent = "";
      return;
    }
    errorEl.hidden = false;
    errorEl.textContent = text;
  }

  const layoutNote = document.getElementById("import-iphone-layout-note");
  const MONTH_NOTE = "Reads the phone directly and saves pictures into folders like 2026-10. A file already there is never replaced. If another picture has the same name, it is saved beside it as IMG_0001_2. This lists the camera roll's DCIM files. It does not reproduce Explorer's 202610_a folders.";
  const EXPLORER_NOTE = "Reads the phone the way Explorer shows it, including 202610_a. Use this when the folder was already copied from Explorer. Each folder has to be asked for, so this is much slower.";

  function layoutMode() {
    const picked = document.querySelector('input[name="iphone-layout"]:checked');
    return picked && picked.value === "explorer" ? "explorer" : "month";
  }

  function paintLayoutNote() {
    if (!layoutNote) {
      return;
    }
    layoutNote.textContent = layoutMode() === "explorer" ? EXPLORER_NOTE : MONTH_NOTE;
  }

  function setBusy(busy) {
    lookBtn.disabled = busy || !installed;
    copyBtn.disabled = busy || !installed;
    browse.disabled = busy;
    pathInput.disabled = busy;
    document.querySelectorAll("#import-iphone-layout input").forEach(function (input) {
      input.disabled = busy || (input.value === "month" && !monthReady);
    });
  }

  function fileLabel(row) {
    const phone = row.phone || "";
    const cut = phone.indexOf("  (");
    return cut === -1 ? phone : phone.slice(0, cut);
  }

  function addRow(label, status, kind) {
    const line = document.createElement("div");
    line.className = "iphone-row" + (kind ? " " + kind : "");
    const name = document.createElement("span");
    name.textContent = label;
    const state = document.createElement("span");
    state.textContent = status;
    line.appendChild(name);
    line.appendChild(state);
    rowsEl.appendChild(line);
  }

  function paintRows(rows) {
    rowsEl.replaceChildren();
    const all = rows || [];
    const matched = all.filter(function (row) {
      return row.action === "skip";
    });
    const waiting = all.filter(function (row) {
      return row.action === "copy";
    });
    const kept = all.filter(function (row) {
      return row.action !== "skip" && row.action !== "copy";
    });
    matched.slice(0, 200).forEach(function (row) {
      addRow(fileLabel(row), "Already in this folder", "match");
    });
    kept.slice(0, 50).forEach(function (row) {
      addRow(fileLabel(row), "Same place, different size, left alone", "keep");
    });
    waiting.slice(0, 100).forEach(function (row) {
      addRow(fileLabel(row), "Not in this folder yet", "copy");
    });
    const hiddenMatches = Math.max(0, matched.length - 200);
    const hiddenWaiting = Math.max(0, waiting.length - 100);
    if (hiddenMatches || hiddenWaiting) {
      addRow(
        "The list is shortened.",
        (hiddenMatches ? hiddenMatches + " more already here. " : "") +
          (hiddenWaiting ? hiddenWaiting + " more still on the phone." : ""),
        "more"
      );
    }
  }

  function num(value) {
    return Number(value || 0).toLocaleString();
  }

  function clockText(ms) {
    const total = Math.max(0, Math.round(ms / 1000));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    const sec = String(seconds).padStart(2, "0");
    if (hours > 0) {
      return hours + ":" + String(minutes).padStart(2, "0") + ":" + sec;
    }
    return minutes + ":" + sec;
  }

  function rememberCount(count) {
    const now = Date.now();
    if (lastCount !== count) {
      lastCount = count;
      lastCountAt = now;
      if (foundEl) {
        foundEl.classList.add("bump");
        window.setTimeout(function () {
          foundEl.classList.remove("bump");
        }, 350);
      }
    } else if (!lastCountAt) {
      lastCountAt = now;
    }
    samples.push({ at: now, count: count });
    const cutoff = now - 30000;
    samples = samples.filter(function (sample) {
      return sample.at >= cutoff;
    });
  }

  function recentRate() {
    if (samples.length < 2) {
      return null;
    }
    const first = samples[0];
    const last = samples[samples.length - 1];
    const seconds = (last.at - first.at) / 1000;
    if (seconds < 3) {
      return null;
    }
    return (last.count - first.count) / seconds;
  }

  function quietMs() {
    return lastCountAt ? Date.now() - lastCountAt : 0;
  }

  function secondsText(ms) {
    return (ms / 1000).toFixed(ms >= 10000 ? 0 : 1);
  }

  function paceText(job) {
    const folder = job.current || "the phone";
    const quiet = quietMs();
    if (job.phase === "copying") {
      const lead = job.fromLook ? "Using the list from Look. " : "";
      return lead + "Copying " + (job.current || "the next picture") + ". " + num(job.copied) + " copied.";
    }
    const asking = Number(job.waitingMs || 0) > 800 || (job.phase === "reading" && quiet > 2000);
    if (asking && job.phase === "reading") {
      const waited = Number(job.waitingMs || 0) > 800 ? Number(job.waitingMs) : quiet;
      let text = "Asking the phone for " + folder + ". " + clockText(waited) + " on this folder.";
      if (job.folderFound) {
        text += " " + num(job.folderFound) + " items seen in it so far.";
      }
      return text;
    }
    if (job.folderFound && job.phase === "reading") {
      return folder + " has " + num(job.folderFound) + " items so far.";
    }
    const pace = job.pace;
    if (pace && pace.listMs) {
      const listed = secondsText(pace.listMs) + "s to list";
      if (pace.sizeMs == null) {
        return "The phone listed " + (pace.folder || folder) + " in " + secondsText(pace.listMs) + "s. Reading sizes.";
      }
      return "Last folder " + (pace.folder || folder) + ": " + num(pace.files) + " pictures, " +
        listed + ", " + secondsText(pace.sizeMs) + "s to read sizes.";
    }
    if (job.phase === "looked" || job.phase === "done" || job.phase === "stopped") {
      return "";
    }
    return job.phase === "reading" ? "Reading pictures in " + folder + "." : "";
  }

  function paintBoard() {
    const job = liveJob;
    if (!liveEl || !job) {
      return;
    }
    const running = job.phase === "reading" || job.phase === "copying";
    liveEl.hidden = false;
    const started = Number(job.startedAt || 0);
    if (started > 0) {
      elapsedEl.textContent = clockText(Date.now() - started * 1000);
    } else if (running && quietMs() > 1000) {
      elapsedEl.textContent = "Quiet " + clockText(quietMs());
    } else if (running) {
      elapsedEl.textContent = "Reading";
    } else {
      elapsedEl.textContent = "Done";
    }
    const recent = recentRate();
    const average = Number(job.picturesPerSec || 0);
    if (running && recent != null) {
      rateEl.textContent = recent.toFixed(1) + " pictures/sec";
    } else if (running && average > 0) {
      rateEl.textContent = average.toFixed(1) + " pictures/sec average";
    } else if (running && quietMs() > 2000) {
      rateEl.textContent = "no new picture just now";
    } else {
      rateEl.textContent = average > 0 ? average.toFixed(1) + " pictures/sec average" : "";
    }
    folderEl.textContent = job.current || (job.phone || "");
    const nextFound = num(job.onPhone);
    if (foundEl.textContent !== nextFound) {
      foundEl.textContent = nextFound;
    }
    if (job.comparing && job.phase === "reading") {
      hereEl.textContent = "…";
      missingEl.textContent = "…";
    } else {
      hereEl.textContent = num(job.skip);
      missingEl.textContent = num(job.willCopy);
    }
    if (job.kept) {
      keptEl.hidden = false;
      keptEl.textContent = num(job.kept) + " left alone (same place, different size).";
    } else if (job.copied) {
      keptEl.hidden = false;
      keptEl.textContent = num(job.copied) + " copied.";
    } else {
      keptEl.hidden = true;
      keptEl.textContent = "";
    }
    const nextPace = paceText(job);
    if (nextPace !== paceStamp) {
      paceStamp = nextPace;
      paceEl.textContent = nextPace;
    }
    countsEl.textContent = "";
    if (job.phase === "reading") {
      statusEl.textContent = "";
    }
  }

  function showJob(job) {
    liveJob = job || null;
    if (!liveJob || typeof liveJob.onPhone !== "number") {
      return;
    }
    rememberCount(Number(liveJob.onPhone || 0));
    paintBoard();
    const running = liveJob.phase === "reading" || liveJob.phase === "copying";
    if (running && !clock) {
      clock = window.setInterval(paintBoard, 200);
    }
    if (!running) {
      stopClock();
    }
  }

  function stopClock() {
    if (clock) {
      window.clearInterval(clock);
      clock = 0;
    }
  }

  function paintCounts(data) {
    phoneEl.textContent = data && data.phone ? data.phone : "";
    if (!data || typeof data.onPhone !== "number") {
      countsEl.textContent = "";
      if (liveEl) {
        liveEl.hidden = true;
      }
      return;
    }
    showJob(data);
  }

  function readJson(res) {
    return res.json().then(function (body) {
      if (!res.ok && body && body.error) {
        throw new Error(body.error);
      }
      return body;
    });
  }

  function refreshStatus() {
    return fetch("/api/iphone").then(readJson).then(function (data) {
      installed = !!data.installed;
      monthReady = Array.isArray(data.layouts) && data.layouts.indexOf("month") !== -1;
      if (!monthReady) {
        const explorerPick = document.querySelector('input[name="iphone-layout"][value="explorer"]');
        if (explorerPick) {
          explorerPick.checked = true;
        }
      }
      if (!installed) {
        showError(data.message || "The iPhone tool is not installed.");
      } else {
        showError("");
      }
      setBusy(working);
      if (!monthReady && layoutNote) {
        layoutNote.textContent = "By month is saved, but this running Library is still the Explorer reader. Reload Library before using it. Faces are still going, so a reload stops them.";
      } else {
        paintLayoutNote();
      }
      return data;
    }).catch(function (err) {
      installed = false;
      showError(err.message || "Import iPhone is not available.");
      setBusy(true);
    });
  }

  function attachRunning(job) {
    working = true;
    setBusy(true);
    if (job && job.path) {
      pathInput.value = job.path;
    }
    showJob(job);
    if (poll) {
      window.clearInterval(poll);
    }
    poll = window.setInterval(pollJob, 400);
    pollJob();
  }

  function openDialog() {
    added = false;
    statusEl.textContent = "";
    if (!dialog.open) {
      dialog.showModal();
    }
    refreshStatus().then(function (data) {
      const job = data && data.job;
      if (job && job.running) {
        attachRunning(job);
      }
    });
  }

  function closeDialog() {
    if (working) {
      stopCopy();
      return;
    }
    if (dialog.open) {
      dialog.close();
    }
  }

  function addFolder(folder) {
    if (added || !folder) {
      return Promise.resolve();
    }
    added = true;
    statusEl.textContent = "Adding the folder to the library…";
    return fetch("/api/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: folder, mode: "serve-from-there" }),
    }).then(function (res) {
      if (!res.ok && res.status !== 202) {
        return res.json().then(function (body) {
          showError((body && body.error) || "The folder was not added.");
        });
      }
      statusEl.textContent = "Folder added. Pictures will show as they are read.";
      if (dialog.open) {
        dialog.close();
      }
      if (window.location) {
        window.location.reload();
      }
    });
  }

  function pollJob() {
    fetch("/api/iphone").then(readJson).then(function (data) {
      const job = data.job || {};
      if (job.phase === "reading" || job.phase === "copying") {
        working = true;
        setBusy(true);
        showJob(job);
        return;
      }
      if (job.phase === "looked") {
        working = false;
        setBusy(false);
        window.clearInterval(poll);
        poll = 0;
        showJob(job);
        statusEl.textContent = job.message || "";
        paintRows(job.rows || []);
        if (job.path) {
          pathInput.value = job.path;
        }
        return;
      }
      if (job.message) {
        statusEl.textContent = job.message;
      }
      paintCounts(job);
      if (job.phase === "done" || job.phase === "stopped") {
        working = false;
        setBusy(false);
        window.clearInterval(poll);
        poll = 0;
        showJob(job);
        if ((job.copied || 0) > 0 || job.phase === "done") {
          addFolder(job.path || pathInput.value);
        }
        return;
      }
      if (job.phase === "error") {
        working = false;
        setBusy(false);
        window.clearInterval(poll);
        poll = 0;
        stopClock();
        showError(job.error || job.message || "The copy stopped.");
        if ((job.copied || 0) > 0) {
          addFolder(job.path || pathInput.value);
        }
      }
    }).catch(function () {
      statusEl.textContent = "Waiting for the copy…";
    });
  }

  function startCopy() {
    showError("");
    working = true;
    setBusy(true);
    statusEl.textContent = "Reading the camera roll…";
    fetch("/api/iphone/copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathInput.value, mode: layoutMode() }),
    }).then(readJson).then(function (body) {
      if (body && body.ok === false) {
        working = false;
        setBusy(false);
        showError(body.message || "Could not start the copy.");
        return;
      }
      if (poll) {
        window.clearInterval(poll);
      }
      poll = window.setInterval(pollJob, 400);
      pollJob();
    }).catch(function (err) {
      working = false;
      setBusy(false);
      showError(err.message || "Could not start the copy.");
    });
  }

  function stopCopy() {
    fetch("/api/iphone/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).catch(function () {});
  }

  document.body.addEventListener("click", function (event) {
    const target = event.target;
    if (!target || !target.id) {
      return;
    }
    if (target.id === "import-iphone-btn" || target.id === "empty-import-iphone") {
      openDialog();
    }
  });

  browse.addEventListener("click", function () {
    fetch("/api/pick-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(readJson).then(function (body) {
      if (body && body.path) {
        pathInput.value = body.path;
      }
    }).catch(function (err) {
      showError(err.message || "Could not browse for a folder.");
    });
  });

  function startLook() {
    showError("");
    working = true;
    setBusy(true);
    rowsEl.textContent = "";
    statusEl.textContent = "Reading the camera roll. Internal Storage. 0 pictures in 0 folders.";
    fetch("/api/iphone/look", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathInput.value, mode: layoutMode() }),
    }).then(readJson).then(function (body) {
      if (body && body.ok === false) {
        return refreshStatus().then(function (data) {
          if (data && data.job && data.job.running) {
            attachRunning(data.job);
            return;
          }
          working = false;
          setBusy(false);
          showError((body && body.message) || "Look failed.");
          statusEl.textContent = "";
        });
      }
      if (body && body.message) {
        statusEl.textContent = body.message;
      }
      if (poll) {
        window.clearInterval(poll);
      }
      poll = window.setInterval(pollJob, 400);
      pollJob();
    }).catch(function (err) {
      working = false;
      setBusy(false);
      showError(err.message || "Look failed.");
    });
  }

  document.querySelectorAll('input[name="iphone-layout"]').forEach(function (input) {
    input.addEventListener("change", paintLayoutNote);
  });
  paintLayoutNote();

  lookBtn.addEventListener("click", startLook);

  copyBtn.addEventListener("click", startCopy);
  closeBtn.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", function (event) {
    if (working) {
      event.preventDefault();
      stopCopy();
    }
  });

  refreshStatus().then(function (data) {
    const job = data && data.job;
    if ((job && job.running) || window.location.hash === "#import-iphone") {
      openDialog();
    }
  });
  window.addEventListener("hashchange", function () {
    if (window.location.hash === "#import-iphone") {
      openDialog();
    }
  });
})();
