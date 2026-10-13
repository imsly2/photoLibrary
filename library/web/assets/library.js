(function () {
  const main = document.querySelector("main");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");
  if (!main || !viewer || !viewerImage) {
    return;
  }

  const PLACEHOLDER = "Preview is not available";
  let rendered = false;
  let pollTimer = 0;

  function showEmpty() {
    main.innerHTML = "<p>No pictures yet</p>";
    rendered = false;
  }

  function closeViewer() {
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
  }

  function openViewer(id) {
    viewerImage.src = "/api/media/" + encodeURIComponent(id) + "?which=preview";
    viewer.hidden = false;
  }

  function requestThumb(cell, id) {
    const img = cell.querySelector("img");
    const placeholder = cell.querySelector(".placeholder");
    const url = "/api/media/" + encodeURIComponent(id) + "?which=thumb";
    img.onload = function () {
      placeholder.hidden = true;
      img.hidden = false;
    };
    img.onerror = function () {
      img.hidden = true;
      placeholder.hidden = false;
      window.setTimeout(function () {
        if (!img.hidden) {
          return;
        }
        img.src = url;
      }, 1000);
    };
    img.src = url;
  }

  function renderItems(items) {
    const list = document.createElement("div");
    list.className = "item-list";
    items.forEach(function (item) {
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
      cell.addEventListener("click", function () {
        openViewer(item.id);
      });
      list.appendChild(cell);
      requestThumb(cell, item.id);
    });
    main.innerHTML = "";
    main.appendChild(list);
    rendered = true;
  }

  function load() {
    fetch("/api/items")
      .then(function (res) {
        if (!res.ok) {
          throw new Error("items");
        }
        return res.json();
      })
      .then(function (items) {
        if (!Array.isArray(items) || items.length === 0) {
          if (!rendered) {
            showEmpty();
          }
          return;
        }
        if (!rendered) {
          renderItems(items);
        }
      })
      .catch(function () {
        if (!rendered) {
          showEmpty();
        }
      });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeViewer();
    }
  });

  viewer.addEventListener("click", function (event) {
    if (event.target === viewer) {
      closeViewer();
    }
  });

  load();
  pollTimer = window.setInterval(load, 1000);
  window.addEventListener("beforeunload", function () {
    window.clearInterval(pollTimer);
  });
})();
