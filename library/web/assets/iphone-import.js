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
  if (!dialog || !pathInput || !lookBtn || !copyBtn) {
    return;
  }

  let installed = false;
  let copying = false;
  let poll = 0;
  let added = false;

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

  function setBusy(busy) {
    lookBtn.disabled = busy || !installed;
    copyBtn.disabled = busy || !installed;
    browse.disabled = busy;
    pathInput.disabled = busy;
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

  function paintCounts(data) {
    phoneEl.textContent = "";
    if (typeof data.onPhone !== "number") {
      countsEl.textContent = "";
      return;
    }
    const phone = data.phone ? data.phone : "The phone";
    let text =
      phone + " has " + Number(data.onPhone).toLocaleString() + " pictures. " +
      Number(data.skip || 0).toLocaleString() + " are already in this folder. " +
      Number(data.willCopy || 0).toLocaleString() + " are not here yet.";
    if (data.kept) {
      text += " " + Number(data.kept).toLocaleString() + " have a different size and were left alone.";
    }
    if (data.copied) {
      text += " " + Number(data.copied).toLocaleString() + " copied.";
    }
    countsEl.textContent = text;
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
      if (!installed) {
        showError(data.message || "The iPhone tool is not installed.");
      } else {
        showError("");
      }
      setBusy(copying);
      return data;
    }).catch(function (err) {
      installed = false;
      showError(err.message || "Import iPhone is not available.");
      setBusy(true);
    });
  }

  function openDialog() {
    added = false;
    statusEl.textContent = "";
    dialog.showModal();
    refreshStatus();
  }

  function closeDialog() {
    if (copying) {
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
      if (job.current) {
        statusEl.textContent = "Copying " + job.current + "…";
      } else if (job.message) {
        statusEl.textContent = job.message;
      }
      paintCounts(job);
      if (job.phase === "done" || job.phase === "stopped") {
        copying = false;
        setBusy(false);
        window.clearInterval(poll);
        poll = 0;
        addFolder(job.path || pathInput.value);
        return;
      }
      if (job.phase === "error") {
        copying = false;
        setBusy(false);
        window.clearInterval(poll);
        poll = 0;
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
    copying = true;
    setBusy(true);
    statusEl.textContent = "Reading the camera roll…";
    fetch("/api/iphone/copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathInput.value }),
    }).then(readJson).then(function (body) {
      if (body && body.ok === false) {
        copying = false;
        setBusy(false);
        showError(body.message || "Could not start the copy.");
        return;
      }
      if (poll) {
        window.clearInterval(poll);
      }
      poll = window.setInterval(pollJob, 1000);
      pollJob();
    }).catch(function (err) {
      copying = false;
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

  lookBtn.addEventListener("click", function () {
    showError("");
    setBusy(true);
    statusEl.textContent = "Reading the camera roll…";
    fetch("/api/iphone/look", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: pathInput.value }),
    }).then(readJson).then(function (body) {
      setBusy(false);
      if (!body || body.ok === false) {
        showError((body && body.message) || "Look failed.");
        statusEl.textContent = "";
        return;
      }
      statusEl.textContent = body.repeated
        ? "Nothing was copied. Explorer listed " + body.repeated + " pictures twice. Each was counted once."
        : "Nothing was copied.";
      paintCounts(body);
      paintRows(body.rows || []);
      if (body.path) {
        pathInput.value = body.path;
      }
    }).catch(function (err) {
      setBusy(false);
      showError(err.message || "Look failed.");
    });
  });

  copyBtn.addEventListener("click", startCopy);
  closeBtn.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", function (event) {
    if (copying) {
      event.preventDefault();
      stopCopy();
    }
  });

  if (window.location.hash === "#import-iphone") {
    openDialog();
  }
  window.addEventListener("hashchange", function () {
    if (window.location.hash === "#import-iphone") {
      openDialog();
    }
  });
})();
