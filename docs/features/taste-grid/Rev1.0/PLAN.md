# Taste-Grid — Video tiles, size, wall, hearts, view chrome

Locked 2026-10-13 after Steve’s Windows notes on `cursor/s03-still-renditions-8e1d`.
Does not close a new Check. Do not touch Add-folder / launcher (Track A),
viewer prev/next/rotate (Track B), reveal-in-explorer, or globe drag
inversion. Do not add a 17th settings.json key.

Read PRODUCT F3/F7/F9/F11/F22, CONTRACTS `kind` / favorites / Days vs All,
UI-SPEC grid density / video tiles / wall / hearts / view toggles, and this
file.

## In scope

1. **Whole-tile hover.** Hover proxy covers the entire cell (`object-fit:
   cover`, absolute overlay). Still stays underneath. No flex-split
   still+video.
2. **Tile badges.** VIDEO badge on video cells (play mark + VIDEO +
   duration when known). LIVE badge unchanged (`.live-badge` text `LIVE`).
3. **Videos filter.** Toolbar control sets transient `kind=video` on
   `GET /api/items` and groups. CLI `--kind`. Invalid kind is
   `invalid-argument`.
4. **Zoom keeps thumbs.** Level/Size/scroll reuse existing tile DOM and
   decoded images. The grid does not blank during the interaction.
5. **Distinct sizes + closer max.** Level defaults: Years 72, Months 104,
   Days 192, All 420. Size slider: 72–520 in eight stops.
6. **Wall.** Dates off = one continuous grid, no date-section gaps.
   Session option only.
7. **Hearts.** Tile heart at Size ≥ 144 px; hidden at 72 and 104.
   Same badge corner. `catalog/favorites.json`. Collapsible top Favorites
   section, default expanded. Heart click does not open the viewer.
8. **Library / Globe.** Visible hover, active, and pressed-toggle chrome.

## Out of scope

Windows launcher, Add-folder dialog, viewer chrome, reveal-in-explorer,
globe drag inversion, new settings keys, albums, F22 gallery.

## Gate

Browser proof on a fixture library at 1280×720. Artifacts under
`docs/features/taste-grid/Rev1.0/assets/<run-id>/`.

1. Hover a video at All: one `<video>` fills the cell box; still is not
   a visible sibling half. Leave restores poster.
2. Every video cell has `.video-badge` text containing `VIDEO`. Videos
   control leaves only `kind=video` items.
3. Drag Size and step the level slider: cells stay painted (no empty
   grid interval). `#grid` `data-size` matches the stop.
4. All default cell box is 420 px. Years and Months boxes differ.
5. Dates off: no `.group-key` in the date/wall body; thumbs in one wrap.
6. Heart visible at All; hidden at Years default. Toggle writes
   `favorite`. `#favorites` appears expanded; collapse hides only those
   tiles.
7. Library/Globe show hover fill and a distinct pressed view.
