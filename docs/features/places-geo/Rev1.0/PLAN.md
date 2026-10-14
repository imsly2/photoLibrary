# Places-geo — Phase A offline city names

Steve: local city/region names like iPhone, flash-drive friendly, no
cloud default. Sits on the existing EXIF/ISO6709 → haversine place
pipeline. Does **not** close a new Check. No faces, YOLO, or MSI.

Read PRODUCT F6 / F3 / F14 / F15, CONTRACTS local place names,
UI-SPEC Info + search, FIXTURES `tests/fixtures/geo/`, and this file.

## In scope

1. Optional offline cities pack in `library-data/geo/` (gitignored).
2. `python -m library setup-geo` and `Setup-geo.bat`. `--from` for a
   local/fixture pack; default fetches GeoNames cities5000.
3. scan / `resolve_place` / `analyze-places` fill `place.name` only when
   it is null and coords exist.
4. Never overwrite a human/agent name. Annotate stays the write path.
5. Info + search show the name. Fixture GPS JPEG → `Chicago, Illinois`.

## Out of scope

Cloud geocoders as default. Face/object models. Shipping the cities
dump in git. Full `Setup.bat` + ML. A 23rd Check. Changing F6’s
no-pack null-name assertions.

## Gate

```
python -m tests.qa check GEO --root "$qaRoot/library-data" --artifacts $evidence
python -m tests.qa slice PLACES-GEO --root "$qaRoot/library-data" --artifacts $evidence
```

F6 without a pack still expects null names. 16/22 unchanged unless a
fresh F-id rerun is recorded in STATUS.

## Steve once

```
python -m library setup-geo
```

or double-click `Setup-geo.bat`. Then Add folder / scan. Open a GPS
photo → Info → Places shows the city. Already-scanned library:

```
python -m library analyze-places
```

Later `Setup.bat` should call that same `python -m library setup-geo`
one-liner.
