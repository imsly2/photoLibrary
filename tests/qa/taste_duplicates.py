"""Duplicate compare UI. Not an F-id grade. Never auto-deletes on hash match."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from library.httpjson import request_json
from tests.qa.s00 import Checks, assert_no_pillow_in_server, stop_owned
from tests.qa.s01 import hash_tree, load_items
from tests.qa.s06 import prepare_media, start_owned
from tests.qa.s08 import fresh_root, run_library, write_result
from tests.qa.taste_filters import collect_console, wait_catalog

I18N = Path(__file__).resolve().parents[2] / "library" / "web" / "assets" / "i18n.js"


def seed_duplicates(media_src: Path, dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    src = media_src / "a" / "IMG_1042.jpg"
    unique = media_src / "b" / "no-exif.jpg"
    keep = dest / "keep" / "IMG_1042.jpg"
    drop = dest / "drop" / "IMG_1042.jpg"
    exact_a = dest / "exact-a" / "twin.jpg"
    exact_b = dest / "exact-b" / "twin.jpg"
    leftover = dest / "unique" / "no-exif.jpg"
    for path in (keep, drop, exact_a, exact_b, leftover):
        path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, keep)
    keep.write_bytes(keep.read_bytes() + b"\r\n")
    shutil.copy2(src, drop)
    drop.write_bytes(drop.read_bytes() + b"\n")
    shutil.copy2(src, exact_a)
    shutil.copy2(src, exact_b)
    shutil.copy2(unique, leftover)
    return {
        "keep": keep,
        "drop": drop,
        "exact_a": exact_a,
        "exact_b": exact_b,
        "unique": leftover,
    }


def item_by_path_part(items: list[dict[str, Any]], part: str) -> dict[str, Any] | None:
    for item in items:
        for loc in item.get("locations") or []:
            path = str(loc.get("lastKnownPath") or loc.get("pathFromVolumeRoot") or "")
            if part in path.replace("\\", "/"):
                return item
    return None


def group_by_reason(groups: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [row for row in groups if row.get("reason") == reason]


def prove_api(checks: Checks, artifacts: Path, media_src: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    i18n_text = I18N.read_text(encoding="utf-8")
    checks.check("i18n-duplicates-en", "duplicates: \"Duplicates\"" in i18n_text)
    checks.check("i18n-duplicates-zh", "duplicates: \"重复项\"" in i18n_text)
    checks.check("i18n-compare-zh", "compareTitle: \"比较重复项\"" in i18n_text)
    checks.check("i18n-keep-zh", "keep: \"保留\"" in i18n_text)
    checks.check("i18n-also-at-zh", "alsoAt: \"也在\"" in i18n_text)
    checks.check("i18n-apply-zh", "applyChoices: \"应用选择\"" in i18n_text)

    root = fresh_root(artifacts / "api-root")
    folder = artifacts / "api-media"
    planted = seed_duplicates(media_src, folder)
    before_media = hash_tree(folder)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    checks.check("scan-ok", scanned.returncode == 0, scanned.stderr[-200:])
    items = load_items(root)
    keep = item_by_path_part(items, "/keep/")
    drop = item_by_path_part(items, "/drop/")
    twin = item_by_path_part(items, "/exact-a/")
    unique = item_by_path_part(items, "/unique/")
    checks.check("has-keep", bool(keep and keep.get("filename") == "IMG_1042.jpg"), json.dumps(keep or {}))
    checks.check("has-drop", bool(drop and drop.get("filename") == "IMG_1042.jpg"), json.dumps(drop or {}))
    checks.check("keep-drop-distinct", bool(keep and drop and keep["id"] != drop["id"]))
    checks.check(
        "hash-merged-twin",
        bool(twin and len(twin.get("locations") or []) == 2),
        json.dumps((twin or {}).get("locations")),
    )
    checks.check("unique-present", bool(unique and unique.get("filename") == "no-exif.jpg"))
    checks.check("scan-no-auto-delete", hash_tree(folder) == before_media)
    record["ids"] = {
        "keep": (keep or {}).get("id"),
        "drop": (drop or {}).get("id"),
        "twin": (twin or {}).get("id"),
        "unique": (unique or {}).get("id"),
    }

    listed = run_library(root, ["duplicates"])
    checks.check("cli-duplicates-ok", listed.returncode == 0, listed.stderr[-200:])
    cli_body = json.loads(listed.stdout)
    cli_groups = cli_body.get("groups") or []
    checks.check("cli-has-groups", len(cli_groups) >= 2, json.dumps(cli_body))

    server, url, pids = start_owned(root)
    try:
        base = url.rstrip("/")
        status, payload = request_json(base + "/api/duplicates", timeout=8)
        checks.check("http-duplicates-200", status == 200, json.dumps(payload))
        groups = (payload or {}).get("groups") if isinstance(payload, dict) else []
        hash_groups = group_by_reason(groups, "hash")
        name_groups = group_by_reason(groups, "filename")
        checks.check("http-hash-group", len(hash_groups) >= 1, json.dumps(hash_groups))
        checks.check("http-name-group", len(name_groups) >= 1, json.dumps(name_groups))
        if hash_groups:
            sides = hash_groups[0].get("sides") or []
            checks.check("hash-two-sides", len(sides) == 2, json.dumps(hash_groups[0]))
            checks.check(
                "hash-one-item",
                hash_groups[0].get("itemIds") == [twin["id"]] if twin else False,
                json.dumps(hash_groups[0].get("itemIds")),
            )
            checks.check(
                "hash-sides-have-stats",
                all(side.get("path") and side.get("sha256") and side.get("sizeBytes") for side in sides),
                json.dumps(sides),
            )
        if name_groups:
            ids = set(name_groups[0].get("itemIds") or [])
            checks.check(
                "name-keep-drop",
                keep and drop and ids == {keep["id"], drop["id"]},
                json.dumps(name_groups[0]),
            )
            sides = name_groups[0].get("sides") or []
            checks.check(
                "name-sides-stats",
                len(sides) == 2
                and all(
                    side.get("width")
                    and side.get("path")
                    and side.get("folder")
                    and side.get("sha256")
                    for side in sides
                ),
                json.dumps(sides),
            )
        unique_ids = {item.get("id") for item in items}
        grouped_ids = {item_id for row in groups for item_id in (row.get("itemIds") or [])}
        checks.check(
            "unique-not-grouped",
            unique and unique["id"] in unique_ids and unique["id"] not in grouped_ids,
            json.dumps(sorted(grouped_ids)),
        )
        status, listed_items = request_json(base + "/api/items", timeout=5)
        names = [item.get("filename") for item in (listed_items or [])]
        checks.check(
            "hash-match-not-two-items",
            status == 200 and names.count("twin.jpg") == 1,
            json.dumps(names),
        )

        status, removed = request_json(
            base + "/api/items/remove",
            method="POST",
            body={"itemIds": [drop["id"]]} if drop else {"itemIds": []},
            timeout=8,
        )
        checks.check("http-remove-drop", status == 200 and removed.get("ok") is True, json.dumps(removed))
        status, after = request_json(base + "/api/items", timeout=5)
        after_ids = {item.get("id") for item in (after or [])}
        checks.check("remove-drops-b", drop and drop["id"] not in after_ids, json.dumps(sorted(after_ids)))
        checks.check("remove-keeps-a", keep and keep["id"] in after_ids, json.dumps(sorted(after_ids)))
        checks.check("remove-keeps-twin", twin and twin["id"] in after_ids, json.dumps(sorted(after_ids)))
        status, after_groups = request_json(base + "/api/duplicates", timeout=5)
        remain_name = group_by_reason((after_groups or {}).get("groups") or [], "filename")
        checks.check(
            "name-group-gone",
            status == 200 and remain_name == [],
            json.dumps(remain_name),
        )
    finally:
        stop_owned(server, extra_pids=pids)

    checks.check("api-originals-stay", hash_tree(folder) == before_media)
    record["originalsUnchanged"] = True
    return record


def compare_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const dialog = document.getElementById('duplicate-compare');
          const sides = Array.from(document.querySelectorAll('#duplicate-compare-sides .compare-side')).map(function (el) {
            const facts = {};
            el.querySelectorAll('.info-fact').forEach(function (row) {
              const dt = (row.querySelector('dt') || {}).textContent || '';
              const dd = (row.querySelector('dd') || {}).textContent || '';
              facts[dt] = dd;
            });
            const checked = el.querySelector('input[type=\"radio\"]:checked');
            const radios = Array.from(el.querySelectorAll('input[type=\"radio\"]')).map(function (node) {
              return node.name || '';
            });
            return {
              itemId: el.getAttribute('data-item-id') || '',
              path: facts.Path || facts['路径'] || '',
              folder: facts.Folder || facts['文件夹'] || '',
              dimensions: facts.Dimensions || facts['尺寸'] || '',
              size: facts.Size || facts['大小'] || '',
              date: facts['Date taken'] || facts['拍摄日期'] || '',
              hash: facts.Hash || facts['哈希'] || '',
              choice: checked ? checked.value : '',
              radioName: checked ? checked.name : (radios[0] || ''),
              facts: facts
            };
          });
          const infoFacts = {};
          document.querySelectorAll('#viewer-fact-list .info-fact').forEach(function (row) {
            const dt = (row.querySelector('dt') || {}).textContent || '';
            const dd = (row.querySelector('dd') || {}).textContent || '';
            infoFacts[dt] = dd;
          });
          const files = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
            return {
              id: el.getAttribute('data-id') || '',
              file: el.getAttribute('data-filename') || ''
            };
          });
          return {
            open: !!(dialog && dialog.open),
            title: (document.getElementById('duplicate-compare-title') || {}).textContent || '',
            help: (document.getElementById('duplicate-compare-help') || {}).textContent || '',
            meta: (document.getElementById('duplicate-compare-meta') || {}).textContent || '',
            empty: !!(document.getElementById('duplicate-compare-empty') && !document.getElementById('duplicate-compare-empty').hidden),
            apply: (document.getElementById('duplicate-compare-apply') || {}).textContent || '',
            cancel: (document.getElementById('duplicate-compare-cancel') || {}).textContent || '',
            index: (document.getElementById('duplicate-compare-index') || {}).textContent || '',
            infoCompare: (document.getElementById('info-compare-copies') || {}).textContent || '',
            infoFacts: infoFacts,
            infoOpen: !!(document.getElementById('viewer-info-panel') && !document.getElementById('viewer-info-panel').hidden),
            confirmOpen: !!(document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open),
            sides: sides,
            files: files,
            lang: document.documentElement.lang
          };
        }"""
    )


def prove_browser(page: Any, url: str, artifacts: Path, checks: Checks, ids: dict[str, str]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    keep_id = ids["keep"]
    drop_id = ids["drop"]
    twin_id = ids["twin"]
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-filename="twin.jpg"]', timeout=30000)
    page.locator("#date-group").select_option("off")
    page.wait_for_function(
        """() => document.querySelectorAll('#grid .cell[data-slot=\"grid\"][data-filename]').length >= 4""",
        timeout=8000,
    )

    page.locator("#filter-duplicates").click()
    page.wait_for_function(
        "() => document.getElementById('duplicate-compare') && document.getElementById('duplicate-compare').open",
        timeout=8000,
    )
    first = compare_state(page)
    record["first"] = first
    checks.check("compare-open", first.get("open") is True)
    checks.check("compare-title-en", first.get("title") == "Compare duplicates", json.dumps(first.get("title")))
    checks.check("two-sides", len(first.get("sides") or []) >= 2, json.dumps(first.get("sides")))
    sides = first.get("sides") or []
    checks.check(
        "sides-stats",
        all(side.get("dimensions") and side.get("size") and side.get("path") and side.get("hash") for side in sides),
        json.dumps(sides),
    )
    checks.check(
        "default-keep",
        all(side.get("choice") == "keep" for side in sides),
        json.dumps([side.get("choice") for side in sides]),
    )
    radio_names = [side.get("radioName") for side in sides]
    checks.check(
        "unique-radio-groups",
        len(radio_names) == len(set(radio_names)) and all(radio_names),
        json.dumps(radio_names),
    )
    page.screenshot(path=str(artifacts / "compare-sides.png"))

    if page.locator("#duplicate-compare-next").is_enabled():
        page.locator("#duplicate-compare-next").click()
        page.wait_for_function(
            """() => {
              const sides = document.querySelectorAll('#duplicate-compare-sides .compare-side');
              return sides.length >= 2 && Array.from(sides).some(function (el) {
                return (el.textContent || '').indexOf('keep') >= 0 || (el.textContent || '').indexOf('IMG_1042') >= 0
                  || (el.getAttribute('data-item-id') || '').length > 8;
              });
            }""",
            timeout=5000,
        )

    page.locator("#language").select_option("zh-Hans")
    page.wait_for_function(
        """() => document.documentElement.lang === 'zh-Hans'
          && ((document.getElementById('duplicate-compare-title') || {}).textContent || '') === '比较重复项'""",
        timeout=8000,
    )
    zh = compare_state(page)
    record["chinese"] = zh
    checks.check("title-zh", zh.get("title") == "比较重复项", json.dumps(zh.get("title")))
    checks.check("apply-zh", zh.get("apply") == "应用选择", json.dumps(zh.get("apply")))
    checks.check("cancel-zh", zh.get("cancel") == "取消", json.dumps(zh.get("cancel")))
    keep_labels = page.evaluate(
        """() => Array.from(document.querySelectorAll('#duplicate-compare-sides label')).map(function (el) {
          return el.textContent || '';
        })"""
    )
    checks.check("choice-zh", "保留" in "".join(keep_labels) and "移出图库" in "".join(keep_labels), json.dumps(keep_labels))
    page.screenshot(path=str(artifacts / "compare-zh.png"))

    page.locator("#language").select_option("en")
    page.wait_for_function(
        """() => document.documentElement.lang === 'en'
          && ((document.getElementById('duplicate-compare-title') || {}).textContent || '') === 'Compare duplicates'""",
        timeout=8000,
    )
    page.locator("#duplicate-compare-cancel").click()
    page.wait_for_function(
        "() => !document.getElementById('duplicate-compare').open",
        timeout=5000,
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    after_cancel = {item.get("id") for item in (listed or [])}
    checks.check(
        "cancel-leaves-both",
        status == 200 and keep_id in after_cancel and drop_id in after_cancel,
        json.dumps(sorted(after_cancel)),
    )

    page.locator("#filter-duplicates").click()
    page.wait_for_function(
        "() => document.getElementById('duplicate-compare') && document.getElementById('duplicate-compare').open",
        timeout=8000,
    )

    def show_filename_group() -> None:
        for _ in range(4):
            state = compare_state(page)
            side_ids = {side.get("itemId") for side in (state.get("sides") or [])}
            if keep_id in side_ids and drop_id in side_ids:
                return
            nxt = page.locator("#duplicate-compare-next")
            if nxt.is_enabled():
                nxt.click()
                page.wait_for_timeout(200)
            else:
                break
        raise RuntimeError("filename group not shown " + json.dumps(compare_state(page)))

    def mark_remove(item_id: str) -> None:
        page.evaluate(
            """(dropId) => {
              const radio = document.querySelector(
                '#duplicate-compare-sides .compare-side[data-item-id=\"' + dropId + '\"] input[value=\"remove\"]'
              );
              if (radio) {
                radio.click();
              }
            }""",
            item_id,
        )
        page.wait_for_function(
            """(dropId) => {
              const radio = document.querySelector(
                '#duplicate-compare-sides .compare-side[data-item-id=\"' + dropId + '\"] input[value=\"remove\"]'
              );
              return radio && radio.checked;
            }""",
            arg=item_id,
            timeout=5000,
        )

    show_filename_group()
    mark_remove(drop_id)
    chosen = compare_state(page)
    record["chosen"] = chosen
    drop_side = next((side for side in (chosen.get("sides") or []) if side.get("itemId") == drop_id), None)
    keep_side = next((side for side in (chosen.get("sides") or []) if side.get("itemId") == keep_id), None)
    checks.check("marked-remove-b", bool(drop_side and drop_side.get("choice") == "remove"), json.dumps(drop_side))
    checks.check("kept-a-choice", bool(keep_side and keep_side.get("choice") == "keep"), json.dumps(keep_side))
    page.locator("#duplicate-compare-apply").click()
    page.wait_for_function(
        "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
        timeout=8000,
    )
    page.screenshot(path=str(artifacts / "compare-confirm.png"))
    page.locator("#confirm-remove-cancel").click()
    page.wait_for_function(
        "() => !document.getElementById('confirm-remove').open",
        timeout=5000,
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    after_dismiss = {item.get("id") for item in (listed or [])}
    checks.check(
        "confirm-cancel-keeps-both",
        status == 200 and keep_id in after_dismiss and drop_id in after_dismiss,
        json.dumps(sorted(after_dismiss)),
    )

    page.locator("#filter-duplicates").click()
    page.wait_for_function(
        "() => document.getElementById('duplicate-compare') && document.getElementById('duplicate-compare').open",
        timeout=8000,
    )
    show_filename_group()
    mark_remove(drop_id)
    page.locator("#duplicate-compare-apply").click()
    page.wait_for_function(
        "() => document.getElementById('confirm-remove') && document.getElementById('confirm-remove').open",
        timeout=8000,
    )
    page.locator("#confirm-remove-ok").click()
    page.wait_for_function(
        """(dropId) => {
          const ids = Array.from(document.querySelectorAll('#grid .cell[data-slot=\"grid\"]')).map(function (el) {
            return el.getAttribute('data-id');
          });
          return ids.indexOf(dropId) < 0;
        }""",
        arg=drop_id,
        timeout=10000,
    )
    status, listed = request_json(url.rstrip("/") + "/api/items", timeout=5)
    remain = {item.get("id") for item in (listed or [])}
    checks.check("keep-a-present", status == 200 and keep_id in remain, json.dumps(sorted(remain)))
    checks.check("remove-b-gone", drop_id not in remain, json.dumps(sorted(remain)))
    checks.check("twin-still-present", twin_id in remain, json.dumps(sorted(remain)))
    page.screenshot(path=str(artifacts / "after-keep-remove.png"))

    page.locator('#grid .cell[data-slot="grid"][data-id="' + twin_id + '"]').first.click()
    page.wait_for_function(
        "() => document.getElementById('viewer') && !document.getElementById('viewer').hidden",
        timeout=8000,
    )
    page.locator("#viewer-info").click()
    page.wait_for_function(
        "() => document.getElementById('viewer-info-panel') && !document.getElementById('viewer-info-panel').hidden",
        timeout=5000,
    )
    info = compare_state(page)
    record["info"] = info
    also = (info.get("infoFacts") or {}).get("Also at") or ""
    checks.check("info-also-at", "twin.jpg" in also or "exact-" in also, json.dumps(info.get("infoFacts")))
    checks.check("info-hash", bool((info.get("infoFacts") or {}).get("Hash")), json.dumps(info.get("infoFacts")))
    checks.check("info-compare-copies", info.get("infoCompare") == "Compare copies", json.dumps(info.get("infoCompare")))
    page.screenshot(path=str(artifacts / "info-also-at.png"))
    page.locator("#info-compare-copies").click()
    page.wait_for_function(
        "() => document.getElementById('duplicate-compare') && document.getElementById('duplicate-compare').open",
        timeout=8000,
    )
    from_info = compare_state(page)
    record["fromInfo"] = from_info
    checks.check("info-opens-compare", from_info.get("open") is True)
    checks.check("info-compare-two-sides", len(from_info.get("sides") or []) >= 2, json.dumps(from_info.get("sides")))
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.getElementById('duplicate-compare').open",
        timeout=5000,
    )
    checks.check("esc-closes-compare", True)
    return record


def seed_browser_root(root: Path, media_src: Path, artifacts: Path) -> tuple[Path, dict[str, str]]:
    folder = artifacts / "browser-media"
    seed_duplicates(media_src, folder)
    scanned = run_library(root, ["scan", str(folder), "--serve-from-there"], timeout=180)
    if scanned.returncode != 0:
        raise RuntimeError(scanned.stderr[-200:])
    items = load_items(root)
    keep = item_by_path_part(items, "/keep/")
    drop = item_by_path_part(items, "/drop/")
    twin = item_by_path_part(items, "/exact-a/")
    unique = item_by_path_part(items, "/unique/")
    if not (keep and drop and twin and unique):
        raise RuntimeError("browser seed missing items")
    return folder, {
        "keep": keep["id"],
        "drop": drop["id"],
        "twin": twin["id"],
        "unique": unique["id"],
    }


def run_slice(root: Path, artifacts: Path) -> int:
    checks = Checks()
    artifacts.mkdir(parents=True, exist_ok=True)
    commands = [
        "python -m library duplicates",
        "GET /api/duplicates",
        "POST /api/items/remove",
    ]
    extra: dict[str, str] = {}
    try:
        media_src = prepare_media(artifacts)
        before = hash_tree(media_src)
        api = prove_api(checks, artifacts, media_src)
        (artifacts / "dup-api.json").write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        extra["dup-api.json"] = str(artifacts / "dup-api.json")

        isolated = artifacts / "browser-root"
        fresh_root(isolated)
        media_folder, ids = seed_browser_root(isolated, media_src, artifacts)
        before_browser_media = hash_tree(media_folder)
        server, url, pids = start_owned(isolated)
        try:
            wait_catalog(url.rstrip("/"), ("IMG_1042.jpg", "twin.jpg", "no-exif.jpg"))
            from playwright.sync_api import sync_playwright

            checks.check("playwright-import", True)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                errors = collect_console(page)
                record = prove_browser(page, url, artifacts, checks, ids)
                unexpected = [
                    message
                    for message in errors
                    if "status of 400" not in message and "status of 404" not in message
                ]
                checks.check("no-console-errors", unexpected == [], json.dumps(errors))
                browser.close()
            (artifacts / "dup-browser.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            extra["dup-browser.json"] = str(artifacts / "dup-browser.json")
            extra["compare-sides.png"] = str(artifacts / "compare-sides.png")
            extra["compare-zh.png"] = str(artifacts / "compare-zh.png")
            extra["compare-confirm.png"] = str(artifacts / "compare-confirm.png")
            extra["after-keep-remove.png"] = str(artifacts / "after-keep-remove.png")
            extra["info-also-at.png"] = str(artifacts / "info-also-at.png")
        finally:
            stop_owned(server, extra_pids=pids)
        checks.check("browser-originals-stay", hash_tree(media_folder) == before_browser_media)
        checks.check("original-fixture-bytes", hash_tree(media_src) == before)
        assert_no_pillow_in_server(checks)
    except Exception as exc:
        checks.check("taste-duplicates-runner", False, str(exc))
    return write_result("TASTE-DUPLICATES", "slice", checks, artifacts, commands, extra)
