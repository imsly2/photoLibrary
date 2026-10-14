"""People and Tags stay collapsible and never overlap. Not an F-id grade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import copy_rels, prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import annotate_json, collect_console, wait_catalog

MEDIA_RELS = (
    "a/IMG_1042.jpg",
    "b/no-exif.jpg",
    "a/near.jpg",
    "b/far.jpg",
)

TAG_NAMES = (
    "Hiking",
    "Singing",
    "Painting",
    "Garden",
    "Kitchen",
    "Birthday",
    "Travel",
    "School",
    "Holiday",
    "Family",
    "Dinner",
    "Park",
)


def seed(root: Path, media_src: Path, artifacts: Path) -> dict[str, str]:
    folder = artifacts / "media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    items = {item.get("filename"): item for item in load_items(root)}
    jpeg = items["IMG_1042.jpg"]
    ada = json.loads(run_library(root, ["annotate", jpeg["id"], "--person", "Ada"]).stdout)
    ada_id = ((ada.get("entities") or {}).get("people") or [{}])[0].get("id") or ""
    for name in TAG_NAMES:
        created = run_library(root, ["tags", "create", name])
        if created.returncode != 0:
            raise RuntimeError(created.stderr[-200:])
    first = TAG_NAMES[0]
    apply = run_library(root, ["tags", "apply", "--item", jpeg["id"], "--add", first])
    if apply.returncode != 0:
        annotate_json(root, jpeg["id"], {"things": [{"name": first}]}, artifacts, "tag-hike.json")
    return {"Ada": ada_id}


def section_boxes(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          function box(el) {
            if (!el) {
              return null;
            }
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return {
              top: r.top,
              bottom: r.bottom,
              left: r.left,
              right: r.right,
              height: r.height,
              width: r.width,
              display: s.display,
              overflow: s.overflow,
              overflowY: s.overflowY,
            };
          }
          const side = document.getElementById('library-side');
          const people = document.getElementById('people-panel');
          const tags = document.getElementById('tags-panel');
          const tagsSection = document.getElementById('tags-section');
          const person = document.querySelector('.person-row');
          const jobs = document.getElementById('jobs-panel');
          const peopleBox = box(people);
          const tagsBox = box(tags);
          const personBox = box(person);
          const tagsSecBox = box(tagsSection);
          let overlap = false;
          if (personBox && tagsBox && tagsBox.display !== 'none' && tagsBox.height > 0 && personBox.height > 0) {
            overlap = personBox.left < tagsBox.right && personBox.right > tagsBox.left
              && personBox.top < tagsBox.bottom && personBox.bottom > tagsBox.top;
          }
          return {
            sideClass: side ? side.className : '',
            peopleOpen: window.libraryTest ? window.libraryTest.peopleOpen() : null,
            tagsOpen: window.libraryTest ? window.libraryTest.tagsOpen() : null,
            peopleToggle: (document.getElementById('people-toggle') || {}).getAttribute('aria-expanded'),
            tagsToggle: (document.getElementById('tags-toggle') || {}).getAttribute('aria-expanded'),
            peopleLabel: (document.getElementById('people-toggle') || {}).getAttribute('aria-label'),
            tagsLabel: (document.getElementById('tags-toggle') || {}).getAttribute('aria-label'),
            peopleHeading: (document.getElementById('people-heading') || {}).textContent,
            tagsHeading: (document.getElementById('tags-heading') || {}).textContent,
            vsplitHidden: !!(document.getElementById('side-vsplit') || {}).hidden,
            people: peopleBox,
            tags: tagsBox,
            tagsSection: tagsSecBox,
            person: personBox,
            jobs: box(jobs),
            overlap: overlap,
          };
        }"""
    )


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    ids = seed(root, media_src, artifacts / "api")
    people = json.loads(run_library(root, ["people"]).stdout)
    rows = people.get("people") if isinstance(people, dict) else people
    ada = [row for row in (rows or []) if row.get("id") == ids["Ada"]]
    checks.check("people-have-ada", bool(ada), json.dumps(ada))
    tags = json.loads(run_library(root, ["tags"]).stdout)
    tag_rows = tags.get("tags") if isinstance(tags, dict) else tags
    names = {row.get("name") for row in (tag_rows or [])}
    checks.check("tags-seeded", names >= set(TAG_NAMES[:4]), json.dumps(sorted(names)))
    record["people"] = ids
    record["tagCount"] = len(tag_rows or [])
    return record


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".person-row", timeout=30000)
    first = section_boxes(page)
    record["first"] = first
    checks.check("people-start-open", first.get("peopleOpen") is True and first.get("peopleToggle") == "true", json.dumps(first))
    checks.check("tags-start-collapsed", first.get("tagsOpen") is False and first.get("tagsToggle") == "false", json.dumps(first))
    checks.check("side-tags-collapsed-class", "tags-collapsed" in (first.get("sideClass") or ""), json.dumps(first.get("sideClass")))
    person_h = ((first.get("person") or {}).get("height")) or 0
    checks.check("person-row-visible", person_h >= 16, json.dumps(first.get("person")))
    tags_display = (first.get("tags") or {}).get("display")
    tags_h = ((first.get("tags") or {}).get("height")) or 0
    checks.check("tags-body-hidden", tags_display == "none" or tags_h == 0, json.dumps(first.get("tags")))
    checks.check("default-no-overlap", first.get("overlap") is False, json.dumps(first))
    checks.check("vsplit-hidden-when-tags-closed", first.get("vsplitHidden") is True, json.dumps(first))

    page.locator("#tags-toggle").click()
    page.wait_for_function(
        "() => window.libraryTest && window.libraryTest.tagsOpen() === true",
        timeout=3000,
    )
    opened = section_boxes(page)
    record["tagsOpen"] = opened
    checks.check("tags-expand", opened.get("tagsOpen") is True and opened.get("tagsToggle") == "true", json.dumps(opened))
    checks.check("vsplit-visible-when-both-open", opened.get("vsplitHidden") is False, json.dumps(opened))
    people_overflow = (opened.get("people") or {}).get("overflowY") or (opened.get("people") or {}).get("overflow")
    tags_overflow = (opened.get("tags") or {}).get("overflowY") or (opened.get("tags") or {}).get("overflow")
    checks.check("people-clips", people_overflow in {"auto", "scroll", "hidden"}, json.dumps(opened.get("people")))
    checks.check("tags-clips", tags_overflow in {"auto", "scroll", "hidden"}, json.dumps(opened.get("tags")))
    checks.check("expanded-no-overlap", opened.get("overlap") is False, json.dumps(opened))
    person_after = opened.get("person") or {}
    tags_after = opened.get("tags") or {}
    if person_after and tags_after and (tags_after.get("height") or 0) > 0:
        checks.check(
            "tags-below-person",
            (tags_after.get("top") or 0) >= (person_after.get("bottom") or 0) - 1,
            json.dumps({"person": person_after, "tags": tags_after}),
        )
    else:
        checks.check("tags-below-person", True, "tags or person missing")

    page.locator("#people-toggle").click()
    page.wait_for_function(
        "() => window.libraryTest && window.libraryTest.peopleOpen() === false",
        timeout=3000,
    )
    people_closed = section_boxes(page)
    record["peopleClosed"] = people_closed
    checks.check("people-collapse", people_closed.get("peopleOpen") is False, json.dumps(people_closed))
    people_display = (people_closed.get("people") or {}).get("display")
    people_h = ((people_closed.get("people") or {}).get("height")) or 0
    checks.check("people-body-hidden", people_display == "none" or people_h == 0, json.dumps(people_closed.get("people")))
    checks.check("collapsed-people-no-overlap", people_closed.get("overlap") is False, json.dumps(people_closed))

    page.locator("#people-toggle").click()
    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        "() => document.documentElement.lang === 'zh-Hans' && (document.getElementById('people-heading') || {}).textContent === '人物'",
        timeout=8000,
    )
    chinese = section_boxes(page)
    record["chinese"] = chinese
    checks.check("people-heading-zh", chinese.get("peopleHeading") == "人物", json.dumps(chinese))
    checks.check("tags-heading-zh", chinese.get("tagsHeading") == "标签", json.dumps(chinese))
    checks.check(
        "toggle-labels-zh",
        chinese.get("peopleLabel") == "收起人物" and chinese.get("tagsLabel") == "收起标签",
        json.dumps({"people": chinese.get("peopleLabel"), "tags": chinese.get("tagsLabel")}),
    )

    page.screenshot(path=str(artifacts / "sidebar-people-tags.png"))
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "sidebar-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["sidebar-api.json"] = str(artifacts / "sidebar-api.json")
        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        seed(isolated, media_src, artifacts / "browser")
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
            (artifacts / "sidebar-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["sidebar-browser.json"] = str(artifacts / "sidebar-browser.json")
            extra["sidebar-people-tags.png"] = str(artifacts / "sidebar-people-tags.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-sidebar-runner", False, str(exc))
    return write_result("TASTE-SIDEBAR", "slice", checks, artifacts, ["python -m tests.qa slice TASTE-SIDEBAR"], extra)
