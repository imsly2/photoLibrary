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

  function paintRows(rows) {
    rowsEl.replaceChildren();
    const shown = (rows || []).filter(function (row) {
      return row.action !== "skip";
    }).slice(0, 300);
    shown.forEach(function (row) {
      const line = document.createElement("div");
      line.className = "iphone-row";
      ["phone", "folder", "status"].forEach(function (key) {
        const cell = document.createElement("span");
        cell.textContent = row[key] || "";
        line.appendChild(cell);
      });
      rowsEl.appendChild(line);
    });
  }

  function paintCounts(data) {
    const phone = data.phone ? data.phone : "";
    phoneEl.textContent = phone;
    if (typeof data.onPhone !== "number") {
      countsEl.textContent = "";
      return;
    }
    countsEl.textContent =
      "On the phone " + data.onPhone +
      "    Exact match " + (data.skip || 0) +
      "    Will copy " + (data.willCopy || 0) +
      (data.copied ? "    Copied " + data.copied : "");
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
      statusEl.textContent = "Look finished. Nothing was copied.";
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
})();
