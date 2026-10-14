# S10 — Spin the offline globe and open a place

Locked 2026-10-13 after S09 at `b8e2663`. **Closes F12.** Tour is S11 (F13).

Read PRODUCT F12, CONTRACTS places API, UI-SPEC globe, FIXTURES GPS set, and this file. Do not invent fields, errors, settings, or screens.

## In scope

- `GET /api/places`: `{id,latitude,longitude,name,itemCount,newestItemId}` for coordinate places with visible items. No-GPS omitted. Same unavailable policy as items.
- Globe view: local texture only. No map tiles. No network. Drag spins. Wheel zooms with cursor anchor.
- Overlapping pins at the current zoom are one cluster with a count.
- Click a cluster: filter to those place ids, open the newest item. Esc closes the viewer and leaves the filtered grid. Opening Globe again shows the globe.
- WebGL failure is inline text, not another map provider.
- `python -m tests.qa slice S10`, `check F12` on fixture-owned roots.
- Original bytes unchanged. `library/` must not import Pillow.

## Out of scope

Tour Play, Live pairing, settings page, F21/F22. Do not add a setting. Do not add test-only UI.

## Gate

Fresh fixture-owned roots. Ports 18765–18864. Artifacts: `result.json`, `stdout.log`, `globe.png`, `cluster.png`, `cluster-members.json`, `offline-network.json`.

```powershell
python -m tests.qa slice S10 --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa check F12 --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. After the three-JPEG GPS set, `GET /api/places` returns two places and omits no-exif. `GET /api/items?place=<id>` returns only that place.
2. Real globe at 1280×720. Texture is local. `offline-network.json` shows no map-tile or geocode requests.
3. Cluster geometry and counts. Drag/zoom keep the cursor anchor (measured).
4. Click cluster opens newest; Esc leaves the filtered grid. Record `globe.png`, `cluster.png`, `cluster-members.json`.
5. Exit 0 only when every proof ran.

The implementer may run these and must not call that log the grade.
