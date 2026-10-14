"""Filter bar chips, people AND, arrange, tags. Not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/near.jpg",
    "b/far.jpg",
)


def wait_catalog(base: str, names: tuple[str, ...] | list[str], timeout: float = 90) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        status, payload = request_json(base + "/api/items", timeout=3)
        if status == 200 and isinstance(payload, list):
            last = payload
            have = {item.get("filename") for item in payload}
            if all(name in have for name in names):
                return last
        time.sleep(0.25)
    raise RuntimeError("catalog timeout " + json.dumps([item.get("filename") for item in last]))


def collect_console(page: Any) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


def annotate_json(root: Path, item_id: str, payload: dict[str, Any], artifacts: Path, name: str) -> Any:
    folder = artifacts / "annotate-json"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return run_library(root, ["annotate", item_id, "--json", str(path)])


def filenames(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("filename") or "" for item in items]


def people_ids(root: Path, items: dict[str, dict[str, Any]], artifacts: Path) -> dict[str, str]:
    jpeg = items["IMG_1042.jpg"]
    near = items["near.jpg"]
    far = items["far.jpg"]
    other = items["no-exif.jpg"]
    ada = json.loads(run_library(root, ["annotate", jpeg["id"], "--person", "Ada"]).stdout)
    ada_id = ((ada.get("entities") or {}).get("people") or [{}])[0].get("id") or ""
    both = json.loads(
        annotate_json(
            root,
            near["id"],
            {"people": [{"id": ada_id}, {"name": "Bob"}]},
            artifacts,
            "near-ada-bob.json",
        ).stdout
    )
    bob_id = ""
    for rec in (both.get("entities") or {}).get("people") or []:
        if rec.get("name") == "Bob":
            bob_id = rec.get("id") or ""
    far_ann = json.loads(
        annotate_json(
            root,
            far["id"],
            {"people": [{"id": bob_id}, {"name": "Cam"}]},
            artifacts,
            "far-bob-cam.json",
        ).stdout
    )
    cam_id = ""
    for rec in (far_ann.get("entities") or {}).get("people") or []:
        if rec.get("name") == "Cam":
            cam_id = rec.get("id") or ""
    annotate_json(
        root,
        other["id"],
        {"people": [{"id": ada_id}, {"id": bob_id}, {"id": cam_id}]},
        artifacts,
        "all-three.json",
    )
    return {"Ada": ada_id, "Bob": bob_id, "Cam": cam_id}


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    folder = artifacts / "api-media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
    items = {item.get("filename"): item for item in load_items(root)}
    checks.check("has-four-stills", all(items.get(name) for name in ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg")))
    ids = people_ids(root, items, artifacts)
    record["people"] = ids
    checks.check("three-people", all(ids.values()) and len(set(ids.values())) == 3, json.dumps(ids))

    listed = run_library(root, ["items", "--person", ids["Ada"] + "," + ids["Bob"]])
    checks.check("items-and-cli", listed.returncode == 0, listed.stderr[-200:])
    and_body = json.loads(listed.stdout)
    and_names = set(filenames(and_body))
    checks.check(
        "and-ada-bob",
        and_names == {"near.jpg", "no-exif.jpg"},
        json.dumps(sorted(and_names)),
    )
    triple = json.loads(run_library(root, ["items", "--person", ids["Ada"] + "," + ids["Bob"] + "," + ids["Cam"]]).stdout)
    checks.check("and-three", filenames(triple) == ["no-exif.jpg"], json.dumps(filenames(triple)))
    ada_only = json.loads(run_library(root, ["items", "--person", ids["Ada"]]).stdout)
    checks.check(
        "ada-only",
        set(filenames(ada_only)) == {"IMG_1042.jpg", "near.jpg", "no-exif.jpg"},
        json.dumps(filenames(ada_only)),
    )

    created = run_library(root, ["tags", "create", "Hiking"])
    checks.check("tag-create", created.returncode == 0, created.stderr[-200:])
    hiking = json.loads(created.stdout)
    checks.check("hiking-id", str(hiking.get("id") or "").startswith("thing_"), json.dumps(hiking))
    singing = json.loads(run_library(root, ["tags", "create", "Singing"]).stdout)
    painting = json.loads(run_library(root, ["tags", "create", "Painting"]).stdout)
    jpeg_id = items["IMG_1042.jpg"]["id"]
    near_id = items["near.jpg"]["id"]
    far_id = items["far.jpg"]["id"]
    applied = run_library(
        root,
        ["tags", "apply", "--item", jpeg_id, "--item", near_id, "--add", "Hiking"],
    )
    checks.check("tag-apply-two", applied.returncode == 0, applied.stderr[-200:])
    run_library(root, ["tags", "apply", "--item", jpeg_id, "--add", "Singing"])
    run_library(root, ["tags", "apply", "--item", far_id, "--add", "Painting"])
    hike_items = json.loads(run_library(root, ["items", "--thing", "Hiking"]).stdout)
    checks.check(
        "filter-hiking",
        set(filenames(hike_items)) == {"IMG_1042.jpg", "near.jpg"},
        json.dumps(filenames(hike_items)),
    )
    and_tags = json.loads(run_library(root, ["items", "--thing", hiking["id"] + "," + singing["id"]]).stdout)
    checks.check("and-tags", filenames(and_tags) == ["IMG_1042.jpg"], json.dumps(filenames(and_tags)))
    removed = run_library(root, ["tags", "apply", "--item", jpeg_id, "--remove", "Singing"])
    checks.check("tag-remove", removed.returncode == 0, removed.stderr[-200:])
    after_remove = json.loads(run_library(root, ["items", "--thing", "Singing"]).stdout)
    checks.check("singing-gone", after_remove == [], json.dumps(after_remove))

    mug = run_library(root, ["annotate", jpeg_id, "--thing", "mug"])
    checks.check("re-infer-mug", mug.returncode == 0, mug.stderr[-200:])
    still_hike = json.loads(run_library(root, ["items", "--thing", "Hiking"]).stdout)
    checks.check(
        "tag-survives-reannotate",
        "IMG_1042.jpg" in filenames(still_hike),
        json.dumps(filenames(still_hike)),
    )
    rebuilt = run_library(root, ["rebuild-index"])
    checks.check("rebuild-ok", rebuilt.returncode == 0, rebuilt.stderr[-200:])
    after_rebuild = json.loads(run_library(root, ["items", "--thing", "Hiking"]).stdout)
    checks.check(
        "tag-survives-rebuild",
        set(filenames(after_rebuild)) == {"IMG_1042.jpg", "near.jpg"},
        json.dumps(filenames(after_rebuild)),
    )

    people_groups = json.loads(run_library(root, ["items"]).stdout)
    from library.service import Library

    lib = Library(root)
    by_people = lib.groups_list({"by": "people"})
    keys = [row.get("key") for row in by_people]
    checks.check("group-people-ada", "Ada" in keys, json.dumps(keys))
    checks.check("group-people-bob", "Bob" in keys, json.dumps(keys))
    all_ids = {item["id"] for item in people_groups}
    grouped_ids = [item_id for row in by_people for item_id in row.get("itemIds") or []]
    checks.check("group-people-once", sorted(grouped_ids) == sorted(all_ids), json.dumps(grouped_ids))
    checks.check("group-people-no-dupes", len(grouped_ids) == len(set(grouped_ids)), json.dumps(grouped_ids))
    by_places = lib.groups_list({"by": "places"})
    place_keys = [row.get("key") for row in by_places]
    checks.check("group-places-has-no-place-or-named", bool(place_keys), json.dumps(place_keys))
    by_tags = lib.groups_list({"by": "tags"})
    tag_keys = [row.get("key") for row in by_tags]
    checks.check("group-tags-hiking", "Hiking" in tag_keys, json.dumps(tag_keys))
    checks.check("group-tags-untagged", "Untagged" in tag_keys, json.dumps(tag_keys))
    record["groups"] = {"people": keys, "places": place_keys, "tags": tag_keys}
    record["groupedIds"] = grouped_ids
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    layout = page.evaluate(
        """() => {
          const header = document.querySelector('header');
          const bar = document.getElementById('filter-bar');
          const search = document.getElementById('search');
          const chips = document.getElementById('filter-chips');
          return {
            searchInHeader: !!(header && search && header.contains(search)),
            searchInBar: !!(bar && search && bar.contains(search)),
            filtersInBar: !!(bar && chips && bar.contains(chips)),
            filtersInHeader: !!(header && chips && header.contains(chips)),
            searchChips: !!document.getElementById('search-chips'),
            arrange: (document.getElementById('arrange') || {}).value,
            arrangeOptions: Array.from(document.querySelectorAll('#arrange option')).map(function (n) { return n.value; }),
            arrangeLabels: Array.from(document.querySelectorAll('#arrange option')).map(function (n) { return n.textContent.trim(); }),
            clearHidden: !!(document.getElementById('clear-filters') || {}).hidden
          };
        }"""
    )
    record["layout"] = layout
    checks.check("search-in-filter-bar", layout.get("searchInBar") is True, json.dumps(layout))
    checks.check("search-not-in-header", layout.get("searchInHeader") is False, json.dumps(layout))
    checks.check("no-search-scope-chips", layout.get("searchChips") is False, json.dumps(layout))
    checks.check("filters-in-bar", layout.get("filtersInBar") is True, json.dumps(layout))
    checks.check("filters-not-in-header", layout.get("filtersInHeader") is False, json.dumps(layout))
    checks.check(
        "arrange-default-date",
        layout.get("arrange") == "dates",
        json.dumps(layout.get("arrange")),
    )
    checks.check(
        "arrange-options",
        layout.get("arrangeOptions") == ["dates", "people", "places", "tags"],
        json.dumps(layout.get("arrangeOptions")),
    )

    page.locator(".person-row", has_text="Ada").click()
    page.wait_for_function(
        """() => {
          const person = (document.getElementById('grid').dataset.person || '');
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          const chips = Array.from(document.querySelectorAll('#active-filters .filter-chip')).map(function (n) { return n.textContent.trim(); });
          return person.indexOf('person_') === 0 && person.indexOf(',') < 0
            && chips.some(function (t) { return t.indexOf('Person: Ada') === 0; })
            && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') < 0;
        }""",
        timeout=8000,
    )
    ada_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["adaGrid"] = ada_names
    checks.check(
        "click-ada-filters",
        set(ada_names) >= {"IMG_1042.jpg", "near.jpg"} and "far.jpg" not in ada_names,
        json.dumps(ada_names),
    )

    page.locator(".person-row", has_text="Bob").click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        """() => {
          const person = (document.getElementById('grid').dataset.person || '');
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return person.indexOf(',') >= 0 && names.indexOf('near.jpg') >= 0 && names.indexOf('IMG_1042.jpg') < 0;
        }""",
        timeout=8000,
    )
    and_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["andGrid"] = and_names
    checks.check("multiselect-and", set(and_names) == {"near.jpg", "no-exif.jpg"}, json.dumps(and_names))

    page.locator(".person-row", has_text="Ada").click()
    page.wait_for_function(
        """() => {
          const person = (document.getElementById('grid').dataset.person || '');
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          const chips = Array.from(document.querySelectorAll('#active-filters .filter-chip')).map(function (n) { return n.textContent.trim(); });
          return person.indexOf(',') < 0 && person.indexOf('person_') === 0
            && !chips.some(function (t) { return t.indexOf('Person: Ada') === 0; })
            && chips.some(function (t) { return t.indexOf('Person: Bob') === 0; })
            && names.indexOf('far.jpg') >= 0 && names.indexOf('IMG_1042.jpg') < 0;
        }""",
        timeout=8000,
    )
    after_deselect = page.evaluate(
        """() => ({
          person: document.getElementById('grid').dataset.person,
          files: Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename')),
          chips: Array.from(document.querySelectorAll('#active-filters .filter-chip')).map(n => n.textContent.trim())
        })"""
    )
    record["afterDeselectAda"] = after_deselect
    checks.check(
        "click-selected-deselects",
        "Person: Ada" not in " ".join(after_deselect.get("chips") or [])
        and "far.jpg" in (after_deselect.get("files") or []),
        json.dumps(after_deselect),
    )

    page.locator(".filter-chip", has_text="Person: Bob").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return !document.getElementById('grid').dataset.person
            && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') >= 0;
        }""",
        timeout=8000,
    )
    checks.check("chip-remove-clears-person", True)

    page.locator(".person-row", has_text="Ada").click()
    page.wait_for_function(
        "() => (document.getElementById('grid').dataset.person || '').indexOf('person_') === 0",
        timeout=8000,
    )
    page.locator("#clear-filters").click()
    page.wait_for_function(
        """() => !document.getElementById('grid').dataset.person
          && document.querySelectorAll('#active-filters .filter-chip').length === 0""",
        timeout=8000,
    )
    checks.check("clear-all", True)

    page.locator("#tag-new").fill("Hiking")
    page.locator("#tag-create").click()
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('#tags-list button')).some(n => n.textContent.indexOf('Hiking') >= 0)",
        timeout=8000,
    )
    page.locator('[data-filename="IMG_1042.jpg"]').click(modifiers=["ControlOrMeta"])
    page.locator('[data-filename="near.jpg"]').click(modifiers=["ControlOrMeta"])
    page.wait_for_function(
        "() => (document.getElementById('grid').dataset.selected || '').split(',').filter(Boolean).length >= 2",
        timeout=5000,
    )
    page.locator("#tag-pick").select_option(label="Hiking")
    page.locator("#tag-apply").click()
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('#tags-list button')).some(function (n) {
          return n.textContent.indexOf('Hiking') >= 0 && /[1-9]/.test(n.textContent);
        })""",
        timeout=8000,
    )
    page.locator(".tag-row", has_text="Hiking").click()
    page.wait_for_function(
        """() => {
          const chips = Array.from(document.querySelectorAll('#active-filters .filter-chip')).map(n => n.textContent.trim());
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'));
          return chips.some(function (t) { return t.indexOf('Tag: Hiking') === 0; })
            && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') < 0;
        }""",
        timeout=8000,
    )
    hike_grid = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["hikeGrid"] = hike_grid
    checks.check("tag-chip-filters", "IMG_1042.jpg" in hike_grid, json.dumps(hike_grid))

    page.locator("#arrange").select_option("people")
    page.wait_for_function(
        """() => document.getElementById('grid').dataset.arrange === 'people'
          && Array.from(document.querySelectorAll('#grid .group-key')).some(n => n.textContent.trim() === 'Ada')""",
        timeout=8000,
    )
    page.locator("#arrange").select_option("tags")
    page.wait_for_function(
        """() => document.getElementById('grid').dataset.arrange === 'tags'
          && Array.from(document.querySelectorAll('#grid .group-key')).some(n => n.textContent.trim() === 'Hiking' || n.textContent.trim() === 'Untagged')""",
        timeout=8000,
    )
    before = page.evaluate("() => document.querySelectorAll('#grid .group:not(.collapsed)').length")
    page.locator("#grid .group-key").first.click()
    page.wait_for_function(
        "() => document.querySelectorAll('#grid .group.collapsed').length >= 1",
        timeout=5000,
    )
    after = page.evaluate("() => document.querySelectorAll('#grid .group.collapsed').length")
    record["collapse"] = {"before": before, "after": after}
    checks.check("group-collapse", after >= 1, json.dumps(record["collapse"]))

    page.screenshot(path=str(artifacts / "filter-bar.png"))
    page.locator("#arrange").select_option("people")
    page.wait_for_timeout(400)
    page.screenshot(path=str(artifacts / "group-people.png"))
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> None:
    folder = artifacts / "browser-media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    items = {item.get("filename"): item for item in load_items(root)}
    people_ids(root, items, artifacts)


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library items --person id1,id2",
        "python -m library tags create Hiking",
        "python -m library tags apply --item <id> --add Hiking",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "filters-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["filters-api.json"] = str(artifacts / "filters-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed_browser_root(isolated, media_src, artifacts)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "far.jpg", "no-exif.jpg"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks)
                unexpected = [message for message in errors if "status of 400" not in message]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "filters-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["filters-browser.json"] = str(artifacts / "filters-browser.json")
            extra["filter-bar.png"] = str(artifacts / "filter-bar.png")
            extra["group-people.png"] = str(artifacts / "group-people.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-filters-runner", False, str(exc))
    return write_result("TASTE-FILTERS", "slice", checks, artifacts, commands, extra)
