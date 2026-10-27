# Side preview, nearby strip, hover loupe — 2026-10-20

Steve's next Library request, recorded before implementation. This does not
ship yet. It does not close a feature Check. Speed work stays on
[BROWSE-SPEED-BASELINE.md](BROWSE-SPEED-BASELINE.md); do not drop those
numbers while building this.

Scope is PRODUCT F10 and the presentable viewer chrome in UI-SPEC. The old
"Soon: filmstrip" row was a general strip and was held until the presentable
checklist is green. Steve is now asking for three specific preview behaviors.
Build only these three.

## 1. Side preview between the grid and People — locked 2026-10-20

Steve: leave the People sidebar as it is. Put the preview between the grid
and that sidebar. Give the preview its own vertical resize handle.

Row, left to right, while a picture is open on a wide window:

`#library-stage` (grid + bottom Size/Dates) · `#preview-splitter` ·
`#viewer` · `#library-splitter` · `#library-side`

`#viewer` is the existing viewer, docked in that slot. It is not a second
copy of the buttons. Previous, next, rotate, zoom, rating, favorite, info,
reveal, open, and video scrub stay the controls already in `#viewer`.
People, Tags, and Processing do not move and do not collapse because a
preview opened.

`#preview-splitter` matches `#library-splitter`: a 6px vertical handle,
pointer drag, session-only width, no settings key. Default preview width
480px. Dragging the handle left widens the preview until the grid is 120px
wide. The preview does not shrink below 320px unless the window itself is
tighter. There is no 720px cap. Back or Esc closes the dock, hides the
handle, and leaves grid filters, scroll, and selection as they were.

F or F11 still fills the window with this same viewer. Esc leaves fullscreen
first. If the picture was docked, that returns to the dock; a second Esc
closes the dock. Arrow keys move in the current sort and stop at the ends.

When the workspace is narrower than grid minimum + preview minimum + the
current People width + both 6px handles, the same click keeps today's
full-window viewer and does not show `#preview-splitter`.

While the preview is docked, the grid stays on screen. The pointer decides
the wheel: over the grid, a plain wheel scrolls the grid and Ctrl+wheel
changes thumbnail size; over the picture, the wheel zooms that picture.
People's own scroll is left alone. Visible grid thumbnails keep loading
while the dock is open. Loading pauses only when a full-window viewer
covers the grid.

Nearby thumbs and the hover loupe are the following slice. Do not build
them in the dock slice.

## 2. Nearby thumbs in the fullscreen viewer

The fullscreen viewer gains a bottom row of nearby pictures in the current
sort: ten before the open item and ten after it. The open item stays marked.
Clicking a thumb in that row opens that item without leaving fullscreen.
Fewer than ten exist at either end when the sort runs out. The row follows
the same order as Previous / Next.

## 3. Hover shows the full thumbnail

When a grid tile is smaller than the thumbnail's longest side (`thumbPx`,
default 320), hovering that tile shows the thumb already loaded for the cell
at its full size. Tiles at or above `thumbPx` stay as they are. The flyout
does not take the click, and video hover-play is unchanged. The nearby-row
hover waits with the filmstrip.

## Verify when built

Synthetic fixture, real browser, screenshots plus JSON under
`assets/side-preview/`. Click opens the side panel and does not navigate
away. The panel's controls match the fullscreen set. People placement matches
Steve's answer below. Fullscreen shows the nearby row, clipped at the ends,
in sort order. Hover shows preview bytes, and a click still opens the
picture. Re-run the scratch floor in
[BROWSE-SPEED-BASELINE.md](BROWSE-SPEED-BASELINE.md) and keep hash parity.
No live restart, no original writes, no new feature Check closure in the
first slice.
