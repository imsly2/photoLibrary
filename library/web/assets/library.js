(function () {
  const empty = document.getElementById("empty");
  const grid = document.getElementById("grid");
  const viewer = document.getElementById("viewer");
  const viewerImage = document.getElementById("viewer-image");

  function thumbUrl(id) {
    return "/api/media/" + encodeURIComponent(id) + "?which=thumb";
  }

  function previewUrl(id) {
    return "/api/media/" + encodeURIComponent(id) + "?which=preview";
  }

  function makeCell(item) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "cell";
    el.dataset.id = item.id;
    el.dataset.filename = item.filename || "";
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
    return el;
  }

  function updateThumb(cell, item) {
    const img = cell.querySelector("img");
    if (!img || (img.complete && img.naturalWidth > 0)) {
      return;
    }
    const url = thumbUrl(item.id);
    img.removeAttribute("src");
    img.src = url;
  }

  function openViewer(id) {
    viewerImage.removeAttribute("src");
    viewerImage.src = previewUrl(id);
    viewer.hidden = false;
  }

  function closeViewer() {
    viewer.hidden = true;
    viewerImage.removeAttribute("src");
  }

  function syncGrid(items) {
    const hasItems = items.length > 0;
    empty.hidden = hasItems;
    grid.hidden = !hasItems;
    const seen = new Set();
    items.forEach(function (item) {
      seen.add(item.id);
      let cell = grid.querySelector('[data-id="' + item.id + '"]');
      if (!cell) {
        cell = makeCell(item);
        grid.appendChild(cell);
      }
      updateThumb(cell, item);
    });
    Array.from(grid.children).forEach(function (el) {
      if (!seen.has(el.dataset.id)) {
        el.remove();
      }
    });
  }

  async function loadItems() {
    try {
      const resp = await fetch("/api/items");
      if (!resp.ok) {
        return;
      }
      const items = await resp.json();
      if (!Array.isArray(items)) {
        return;
      }
      syncGrid(items);
    } catch (err) {
      return;
    }
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeViewer();
    }
  });

  loadItems();
  setInterval(loadItems, 1000);
})();
