"""People panel, bottom Size/Dates, and processing chrome. Not an F-id grade."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree
from tests.qa.s03 import find_item
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


def people_by_name(body: dict[str, Any], name: str | None) -> list[dict[str, Any]]:
    rows = body.get("people") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if row.get("name") == name]


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    root = fresh_root(artifacts / "api-root")
    folder = artifacts / "api-media"
    copy_rels(media_src, folder, MEDIA_RELS)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
    items = {item.get("filename"): item for item in _load_items(root)}
    jpeg = items.get("IMG_1042.jpg") or {}
    near = items.get("near.jpg") or {}
    far = items.get("far.jpg") or {}
    other = items.get("no-exif.jpg") or {}
    checks.check("has-four-stills", all(rec.get("id") for rec in (jpeg, near, far, other)))

    ada = run_library(root, ["annotate", jpeg["id"], "--person", "Ada"])
    checks.check("annotate-ada", ada.returncode == 0, ada.stderr[-200:])
    ada_id = (json.loads(ada.stdout).get("entities") or {}).get("people") or []
    ada_id = ada_id[0]["id"] if ada_id else ""
    checks.check("ada-id", ada_id.startswith("person_"), ada_id)

    both = annotate_json(
        root,
        near["id"],
        {"people": [{"id": ada_id}, {"name": "Bob"}]},
        artifacts,
        "both.json",
    )
    checks.check("annotate-ada-bob", both.returncode == 0, both.stderr[-200:])
    bob_faces = (json.loads(both.stdout).get("entities") or {}).get("people") or []
    bob_id = ""
    for rec in bob_faces:
        if rec.get("name") == "Bob":
            bob_id = rec.get("id") or ""
    checks.check("bob-id", bob_id.startswith("person_"), bob_id)

    unnamed_one = annotate_json(root, far["id"], {"people": [{"name": None}]}, artifacts, "unnamed-one.json")
    checks.check("unnamed-one", unnamed_one.returncode == 0, unnamed_one.stderr[-200:])
    singleton = people_by_name({"people": _load_people(root)}, None)
    singleton_id = ""
    for rec in singleton:
        if rec["id"] not in {ada_id, bob_id}:
            singleton_id = rec["id"]
            break

    cluster = annotate_json(root, other["id"], {"people": [{"name": None}]}, artifacts, "cluster-1.json")
    checks.check("cluster-create", cluster.returncode == 0, cluster.stderr[-200:])
    cluster_people = people_by_name({"people": _load_people(root)}, None)
    cluster_id = ""
    for rec in cluster_people:
        if rec["id"] not in {ada_id, bob_id, singleton_id}:
            cluster_id = rec["id"]
            break
    checks.check("cluster-id", bool(cluster_id), cluster_id)
    annotate_json(root, jpeg["id"], {"people": [{"id": cluster_id}]}, artifacts, "cluster-2.json")
    annotate_json(root, near["id"], {"people": [{"id": cluster_id}]}, artifacts, "cluster-3.json")

    listed = run_library(root, ["people", "list"])
    checks.check("people-list-cli", listed.returncode == 0, listed.stderr[-200:])
    body = json.loads(listed.stdout)
    record["people"] = body
    checks.check("poi-min-3", body.get("personOfInterestMin") == 3, json.dumps(body))
    by_id = {row["id"]: row for row in body.get("people") or []}
    checks.check("ada-visible", by_id.get(ada_id, {}).get("visible") is True, json.dumps(by_id.get(ada_id)))
    checks.check("ada-named", by_id.get(ada_id, {}).get("named") is True, json.dumps(by_id.get(ada_id)))
    checks.check(
        "singleton-hidden",
        by_id.get(singleton_id, {}).get("visible") is False,
        json.dumps(by_id.get(singleton_id)),
    )
    checks.check(
        "cluster-visible",
        by_id.get(cluster_id, {}).get("visible") is True and by_id.get(cluster_id, {}).get("itemCount") >= 3,
        json.dumps(by_id.get(cluster_id)),
    )

    and_items = run_library(root, ["items", "--person", ada_id + "," + bob_id])
    checks.check("and-cli", and_items.returncode == 0, and_items.stderr[-200:])
    and_names = [item.get("filename") for item in json.loads(and_items.stdout)]
    record["andNames"] = and_names
    checks.check("and-only-near", and_names == ["near.jpg"], json.dumps(and_names))

    named = run_library(root, ["people", "update", cluster_id, "--name", "Pat"])
    checks.check("rename-cli", named.returncode == 0, named.stderr[-200:])
    renamed = json.loads(named.stdout)
    checks.check("rename-pat", renamed.get("name") == "Pat", json.dumps(renamed))

    thumb = run_library(root, ["people", "update", ada_id, "--thumbnail", jpeg["id"]])
    checks.check("thumb-cli", thumb.returncode == 0, thumb.stderr[-200:])
    thumb_body = json.loads(thumb.stdout)
    checks.check(
        "thumb-item",
        (thumb_body.get("thumbnail") or {}).get("itemId") == jpeg["id"],
        json.dumps(thumb_body),
    )

    jobs = run_library(root, ["jobs"])
    checks.check("jobs-cli", jobs.returncode == 0, jobs.stderr[-200:])
    jobs_body = json.loads(jobs.stdout)
    record["jobs"] = jobs_body
    ids = [q.get("id") for q in jobs_body.get("queues") or []]
    checks.check("jobs-queues", ids == ["renditions", "analyze", "infer-faces", "objects"], json.dumps(ids))
    checks.check("jobs-ok", jobs_body.get("ok") is True, json.dumps(jobs_body))
    paused = run_library(root, ["jobs", "pause"])
    checks.check("jobs-pause", paused.returncode == 0 and json.loads(paused.stdout).get("paused") is True)
    resumed = run_library(root, ["jobs", "resume"])
    checks.check("jobs-resume", resumed.returncode == 0 and json.loads(resumed.stdout).get("paused") is False)

    server, url, pids = start_owned(root)
    try:
        status, http_people = request_json(url.rstrip("/") + "/api/people", timeout=5)
        checks.check("people-http", status == 200 and isinstance(http_people, dict), str(status))
        status, and_http = request_json(
            url.rstrip("/") + "/api/items?person=" + ada_id + "," + bob_id,
            timeout=5,
        )
        http_names = [item.get("filename") for item in and_http] if isinstance(and_http, list) else []
        checks.check("and-http", status == 200 and http_names == ["near.jpg"], json.dumps(http_names))
        status, job_http = request_json(url.rstrip("/") + "/api/jobs", timeout=5)
        checks.check("jobs-http", status == 200 and isinstance(job_http, dict) and job_http.get("ok") is True)
        status, paused_http = request_json(
            url.rstrip("/") + "/api/jobs",
            method="POST",
            body={"action": "pause"},
            timeout=5,
        )
        checks.check("jobs-pause-http", status == 200 and isinstance(paused_http, dict) and paused_http.get("paused") is True)
        request_json(url.rstrip("/") + "/api/jobs", method="POST", body={"action": "resume"}, timeout=5)
        record["httpPeople"] = http_people
    finally:
        stop_owned(server, extra_pids=pids)
    merged = run_library(root, ["people", "merge", ada_id, bob_id])
    checks.check("merge-cli", merged.returncode == 0, merged.stderr[-200:])
    after_merge = json.loads(run_library(root, ["people", "list"]).stdout)
    after_ids = {row.get("id"): row.get("name") for row in after_merge.get("people") or []}
    checks.check("merge-ada-kept", after_ids.get(ada_id) == "Ada", json.dumps(after_ids))
    checks.check("merge-bob-dropped", bob_id not in after_ids, json.dumps(after_ids))
    record["mergeCli"] = json.loads(merged.stdout) if merged.returncode == 0 else {}
    return record


def _load_items(root: Path) -> list[dict[str, Any]]:
    from tests.qa.s01 import load_items

    return load_items(root)


def _load_people(root: Path) -> list[dict[str, Any]]:
    from tests.qa.s08 import load_people

    return load_people(root)


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks) -> dict[str, Any]:
    record: dict[str, Any] = {}
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="IMG_1042.jpg"]', timeout=30000)
    page.wait_for_selector(".person-row", timeout=10000)
    page.locator("#date-group").select_option("off")
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.dateGroup === 'off'",
        timeout=5000,
    )
    page.locator("#size-slider").evaluate(
        """(el) => {
          el.value = '3';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    page.wait_for_function(
        "() => document.getElementById('grid') && document.getElementById('grid').dataset.size === '192'",
        timeout=5000,
    )
    page.screenshot(path=str(artifacts / "library-chrome.png"))
    layout = page.evaluate(
        """() => {
          const chrome = document.getElementById('library-chrome');
          const grid = document.getElementById('grid');
          const side = document.getElementById('library-side');
          const splitter = document.getElementById('library-splitter');
          const toolbar = document.querySelector('header .toolbar');
          const date = document.getElementById('date-group');
          const size = document.getElementById('size-slider');
          function box(el) {
            if (!el) {
              return null;
            }
            const r = el.getBoundingClientRect();
            return { top: r.top, left: r.left, bottom: r.bottom, right: r.right, width: r.width, height: r.height };
          }
          return {
            chrome: box(chrome),
            grid: box(grid),
            side: box(side),
            splitter: box(splitter),
            dateInToolbar: !!(toolbar && date && toolbar.contains(date)),
            sizeInChrome: !!(chrome && size && chrome.contains(size)),
            dateInChrome: !!(chrome && date && chrome.contains(date)),
            dateOptions: date ? Array.from(date.options).map(function (opt) { return opt.value; }) : [],
            people: Array.from(document.querySelectorAll('.person-row .person-name')).map(function (el) {
              return (el.textContent || '').trim();
            }),
            jobs: (document.getElementById('jobs-status') || {}).textContent || '',
            pause: !!document.getElementById('jobs-pause'),
            resume: (document.getElementById('jobs-resume') || {}).textContent || '',
            sideCollapsed: document.querySelector('.workspace').classList.contains('side-collapsed'),
          };
        }"""
    )
    record["layout"] = layout
    chrome = layout.get("chrome") or {}
    grid = layout.get("grid") or {}
    side = layout.get("side") or {}
    checks.check("chrome-present", bool(chrome.get("width")), json.dumps(layout))
    checks.check("size-in-chrome", layout.get("sizeInChrome") is True, json.dumps(layout))
    checks.check("date-in-chrome", layout.get("dateInChrome") is True, json.dumps(layout))
    checks.check("date-not-in-toolbar", layout.get("dateInToolbar") is False, json.dumps(layout))
    checks.check(
        "chrome-below-grid",
        (chrome.get("top") or 0) >= (grid.get("bottom") or 9999) - 2,
        json.dumps({"chrome": chrome, "grid": grid}),
    )
    checks.check(
        "side-right-of-grid",
        (side.get("left") or 0) >= (grid.get("right") or 9999) - 8,
        json.dumps({"side": side, "grid": grid}),
    )
    checks.check(
        "date-modes",
        layout.get("dateOptions") == ["years", "months", "days", "off"],
        json.dumps(layout.get("dateOptions")),
    )
    names = layout.get("people") or []
    checks.check("people-has-ada", "Ada" in names, json.dumps(names))
    checks.check("people-has-bob", "Bob" in names, json.dumps(names))
    checks.check("people-has-pat", "Pat" in names, json.dumps(names))
    checks.check("people-no-singleton-unnamed", names.count("Unnamed") == 0, json.dumps(names))
    checks.check("jobs-chrome", bool(layout.get("pause")) and layout.get("resume") in {"Start", "Resume"}, json.dumps(layout))

    page.locator(".person-row", has_text="Ada").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('#grid .cell')).map(function (el) {
            return el.getAttribute('data-filename');
          });
          const person = (document.getElementById('grid').dataset.person || '');
          return person.indexOf('person_') === 0 && person.indexOf(',') < 0
            && names.indexOf('IMG_1042.jpg') >= 0 && names.indexOf('far.jpg') < 0;
        }""",
        timeout=8000,
    )
    ada_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell')).map(el => el.getAttribute('data-filename'))"
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
          const names = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
            return el.getAttribute('data-filename');
          });
          const person = (document.getElementById('grid').dataset.person || '');
          const merge = document.getElementById('people-merge');
          return person.indexOf(',') >= 0 && names.length === 1 && names[0] === 'near.jpg'
            && merge && !merge.hidden;
        }""",
        timeout=8000,
    )
    and_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(el => el.getAttribute('data-filename'))"
    )
    record["andGrid"] = and_names
    checks.check("multiselect-and", and_names == ["near.jpg"], json.dumps(and_names))
    merge_hidden = page.evaluate("() => !!(document.getElementById('people-merge') || {}).hidden")
    checks.check("merge-visible-when-two", merge_hidden is False)
    page.locator("#people-merge").click()
    page.wait_for_function(
        "() => { const d = document.getElementById('confirm-merge'); return d && d.open; }",
        timeout=5000,
    )
    page.locator("#confirm-merge-ok").click()
    page.wait_for_function(
        """() => {
          const names = Array.from(document.querySelectorAll('.person-row .person-name')).map(function (el) {
            return el.textContent.trim();
          });
          return names.indexOf('Ada') >= 0 && names.indexOf('Bob') < 0;
        }""",
        timeout=8000,
    )
    after_merge_ui = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent.trim())"
    )
    record["afterMergeUi"] = after_merge_ui
    checks.check("merge-ui-keeps-ada", "Ada" in after_merge_ui, json.dumps(after_merge_ui))
    checks.check("merge-ui-drops-bob", "Bob" not in after_merge_ui, json.dumps(after_merge_ui))

    page.locator(".person-row", has_text="Pat").click()
    page.wait_for_selector("#person-profile:not([hidden])", timeout=5000)
    page.fill("#person-name", "Patricia")
    page.locator("#person-name").press("Enter")
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).some(el => el.textContent.trim() === 'Patricia')",
        timeout=8000,
    )
    record["renamed"] = page.evaluate(
        "() => Array.from(document.querySelectorAll('.person-row .person-name')).map(el => el.textContent.trim())"
    )
    checks.check("rename-in-panel", "Patricia" in record["renamed"], json.dumps(record["renamed"]))

    thumb_css = page.evaluate(
        """() => {
          const face = document.querySelector('.person-face');
          const img = document.querySelector('.person-face img');
          function box(el) {
            if (!el) {
              return null;
            }
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return {
              width: r.width,
              height: r.height,
              overflow: s.overflow,
              cssWidth: s.width,
              cssHeight: s.height,
            };
          }
          const choices = Array.from(document.querySelectorAll('.person-face-choice')).map(function (el) {
            const r = el.getBoundingClientRect();
            return { top: r.top, left: r.left, right: r.right, bottom: r.bottom };
          });
          let overlap = false;
          for (let i = 0; i < choices.length; i += 1) {
            for (let j = i + 1; j < choices.length; j += 1) {
              const a = choices[i];
              const b = choices[j];
              const hit = a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
              if (hit) {
                overlap = true;
              }
            }
          }
          return { face: box(face), img: box(img), choiceCount: choices.length, choiceOverlap: overlap };
        }"""
    )
    record["thumbCss"] = thumb_css
    face_h = ((thumb_css.get("face") or {}).get("height")) or 0
    img_h = ((thumb_css.get("img") or {}).get("height")) or 0
    checks.check("people-face-has-height", face_h >= 16, json.dumps(thumb_css.get("face")))
    checks.check(
        "people-face-img-has-height",
        img_h >= 16 or (thumb_css.get("img") is None and face_h >= 16),
        json.dumps(thumb_css.get("img")),
    )
    checks.check("people-face-overflow-hidden", (thumb_css.get("face") or {}).get("overflow") == "hidden", json.dumps(thumb_css.get("face")))
    checks.check("people-choice-no-overlap", thumb_css.get("choiceOverlap") is False, json.dumps(thumb_css))

    person_before = page.evaluate("() => document.getElementById('grid').dataset.person || ''")
    if page.locator(".person-face-choice").count() > 0:
        page.locator(".person-face-choice").first.click()
        person_after = page.evaluate("() => document.getElementById('grid').dataset.person || ''")
        checks.check(
            "choice-does-not-toggle-row",
            person_after == person_before,
            json.dumps({"before": person_before, "after": person_after}),
        )
    else:
        checks.check("choice-does-not-toggle-row", True, "no face choices")

    page.locator("#jobs-pause").click(force=True)
    page.locator("#jobs-resume").click()
    page.wait_for_function(
        "() => (document.getElementById('jobs-resume') || {}).textContent === 'Start' || (document.getElementById('jobs-status') || {}).textContent",
        timeout=5000,
    )
    page.screenshot(path=str(artifacts / "people-panel.png"))
    page.locator("#side-collapse").click()
    page.wait_for_function(
        "() => document.querySelector('.workspace').classList.contains('side-collapsed')",
        timeout=3000,
    )
    page.locator("#library-splitter").click()
    page.wait_for_function(
        "() => !document.querySelector('.workspace').classList.contains('side-collapsed')",
        timeout=3000,
    )
    checks.check("side-toggle", True)
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library people list",
        "python -m library jobs pause",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "people-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["people-api.json"] = str(artifacts / "people-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        folder = artifacts / "browser-media"
        copy_rels(media_src, folder, MEDIA_RELS)
        scanned = run_library(isolated, ["scan", str(folder), "--serve-from-there"], timeout=180)
        checks.check("browser-scan", scanned.returncode == 0, scanned.stderr[-200:])
        items = {item.get("filename"): item for item in _load_items(isolated)}
        jpeg = items["IMG_1042.jpg"]
        near = items["near.jpg"]
        far = items["far.jpg"]
        other = items["no-exif.jpg"]
        ada = json.loads(run_library(isolated, ["annotate", jpeg["id"], "--person", "Ada"]).stdout)
        ada_id = ((ada.get("entities") or {}).get("people") or [{}])[0].get("id")
        both = json.loads(
            annotate_json(
                isolated,
                near["id"],
                {"people": [{"id": ada_id}, {"name": "Bob"}]},
                artifacts,
                "browser-both.json",
            ).stdout
        )
        annotate_json(isolated, far["id"], {"people": [{"name": None}]}, artifacts, "browser-singleton.json")
        cluster = json.loads(
            annotate_json(isolated, other["id"], {"people": [{"name": None}]}, artifacts, "browser-cluster.json").stdout
        )
        cluster_id = ""
        for rec in (cluster.get("entities") or {}).get("people") or []:
            if rec.get("name") is None:
                cluster_id = rec.get("id") or ""
        annotate_json(isolated, jpeg["id"], {"people": [{"id": cluster_id}]}, artifacts, "browser-cluster-2.json")
        annotate_json(isolated, near["id"], {"people": [{"id": cluster_id}]}, artifacts, "browser-cluster-3.json")
        run_library(isolated, ["people", "update", cluster_id, "--name", "Pat"])

        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "near.jpg", "far.jpg"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks)
                unexpected = [message for message in errors if "status of 400" not in message and "status of 404" not in message]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "people-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["people-browser.json"] = str(artifacts / "people-browser.json")
            extra["people-panel.png"] = str(artifacts / "people-panel.png")
            extra["library-chrome.png"] = str(artifacts / "library-chrome.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-people-runner", False, str(exc))
    return write_result("TASTE-PEOPLE", "slice", checks, artifacts, commands, extra)
