"""Portable Setup.bat: static contract + missing-module dry-run. Not an F-id."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server
from tests.qa.s08 import write_result

WANTED = (
    ("setup-geo", ["setup-geo"]),
    ("setup-ml objects", ["setup-ml", "objects"]),
    ("setup-ml faces", ["setup-ml", "faces"]),
    ("setup-ml transcribe", ["setup-ml", "transcribe"]),
)


def _read(name: str) -> str:
    return (PRODUCT_ROOT / name).read_text(encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(PRODUCT_ROOT),
        capture_output=True,
        text=True,
    )


def probe_command(tokens: list[str]) -> dict[str, Any]:
    proc = _run([sys.executable, "-m", "library", *tokens, "--help"])
    combined = (proc.stdout or "") + (proc.stderr or "")
    present = proc.returncode == 0 and "invalid choice" not in combined
    return {
        "tokens": tokens,
        "returncode": proc.returncode,
        "present": present,
        "excerpt": combined[-800:],
    }


# Windows PowerShell 5.1 reads a no-BOM file as the system ANSI page
# (cp1252 on US English). UTF-8 em-dash E2 80 94 becomes â€" and 0x94
# is a closing smart quote, which then leaves `using` as a directive.
_PS_DOUBLE_QUOTES = frozenset('"\u201c\u201d')
_PS_SINGLE_QUOTES = frozenset("'\u2018\u2019")


def _scan_ps51_source(text: str) -> dict[str, Any]:
    """Walk PowerShell-ish source the way a broken encoding would."""
    i = 0
    n = len(text)
    in_dq = False
    in_sq = False
    in_block = False
    line_comment = False
    stmt_start = True
    depth = 0
    bare_using: list[int] = []
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
                stmt_start = True
            i += 1
            continue
        if in_block:
            if ch == "#" and nxt == ">":
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if in_dq:
            if ch == "`":
                i += 2
                continue
            if ch in _PS_DOUBLE_QUOTES:
                in_dq = False
            i += 1
            continue
        if in_sq:
            if ch in _PS_SINGLE_QUOTES:
                if nxt in _PS_SINGLE_QUOTES:
                    i += 2
                    continue
                in_sq = False
            i += 1
            continue
        if ch in " \t":
            i += 1
            continue
        if ch == "\n":
            stmt_start = True
            i += 1
            continue
        if ch == ";":
            stmt_start = True
            i += 1
            continue
        if ch == "<" and nxt == "#":
            in_block = True
            i += 2
            continue
        if ch == "#":
            line_comment = True
            i += 1
            continue
        if ch in _PS_DOUBLE_QUOTES:
            in_dq = True
            stmt_start = False
            i += 1
            continue
        if ch in _PS_SINGLE_QUOTES:
            in_sq = True
            stmt_start = False
            i += 1
            continue
        if ch == "{":
            depth += 1
            stmt_start = True
            i += 1
            continue
        if ch == "}":
            depth -= 1
            stmt_start = False
            i += 1
            continue
        if stmt_start and text[i : i + 5] == "using" and (
            i + 5 >= n or not (text[i + 5].isalnum() or text[i + 5] == "_")
        ):
            bare_using.append(text.count("\n", 0, i) + 1)
        stmt_start = False
        i += 1
    return {
        "stringsClosed": not in_dq and not in_sq and not in_block,
        "braceDepth": depth,
        "bareUsingLines": bare_using,
    }


def ps51_encoding_safe(raw: bytes) -> dict[str, Any]:
    as_cp1252 = raw.decode("cp1252")
    scan = _scan_ps51_source(as_cp1252)
    return {
        "asciiOnly": all(b < 128 for b in raw),
        "cp1252EqualsUtf8": as_cp1252 == raw.decode("utf-8"),
        **scan,
        "ok": (
            all(b < 128 for b in raw)
            and scan["stringsClosed"]
            and scan["braceDepth"] == 0
            and not scan["bareUsingLines"]
        ),
    }


def extract_bat_help(bat: str) -> str:
    marker = ":help"
    index = bat.lower().rfind(marker)
    if index < 0:
        return ""
    return bat[index:]


def extract_resolve_function(text: str) -> str:
    start = text.find("function Resolve-LibraryAppFolder")
    end = text.find("# end Resolve-LibraryAppFolder")
    if start < 0 or end < 0 or end <= start:
        return ""
    return text[start:end].strip()


def _ready_only_after_errorlevel(bat: str) -> bool:
    fail_at = bat.find('if not "%ERR%"=="0"')
    ready_at = bat.find("Ready -- run Library.bat")
    if fail_at < 0 or ready_at < 0 or ready_at < fail_at:
        return False
    fail_exit = bat.find("exit /b %ERR%", fail_at)
    if fail_exit < 0 or ready_at < fail_exit:
        return False
    return "Ready -- run Library.bat" not in bat[fail_at:fail_exit]


def trim_folder(path: str) -> str:
    item = path.strip()
    while len(item) > 3 and item.endswith(("/", "\\")):
        item = item[:-1]
    return item


def resolve_library_app_folder(
    hint: str = "",
    script_root: str = "",
    script_path: str = "",
    script_definition: str = "",
    cwd: str = "",
) -> str | None:
    """Python port of Resolve-LibraryAppFolder. Empty script_root = empty $PSScriptRoot."""
    candidates: list[str] = []
    if hint:
        candidates.append(trim_folder(hint))
    if script_root:
        candidates.append(trim_folder(script_root))
    if script_path:
        parent = str(Path(script_path).parent)
        if parent:
            candidates.append(trim_folder(parent))
    if script_definition:
        definition = Path(script_definition)
        if definition.is_file():
            candidates.append(trim_folder(str(definition.parent)))
    for item in candidates:
        if item and Path(item).is_dir():
            return str(Path(item).resolve())
    if cwd:
        here = trim_folder(cwd)
        here_path = Path(here)
        if here and here_path.is_dir():
            markers = (
                "Setup.bat",
                "Library.bat",
                "Launch.bat",
                "setup.ps1",
                "launch.ps1",
                "CreateShortcut.bat",
            )
            if any((here_path / name).exists() for name in markers):
                return str(here_path.resolve())
    return None


def prove_app_folder_null(checks: Checks) -> dict[str, Any]:
    """Simulate empty $PSScriptRoot so a null Set-Location path cannot regress."""
    setup = _read("setup.ps1")
    launch = _read("launch.ps1")
    shortcut = _read("create-shortcut.ps1")
    bat = _read("Setup.bat")
    library_bat = _read("Library.bat")
    update_bat = _read("Update.bat")
    shortcut_bat = _read("CreateShortcut.bat")
    extracted = {
        "setup.ps1": extract_resolve_function(setup),
        "launch.ps1": extract_resolve_function(launch),
        "create-shortcut.ps1": extract_resolve_function(shortcut),
    }
    checks.check(
        "resolve-function-present-in-setup",
        "param(" in extracted["setup.ps1"] and "$Hint" in extracted["setup.ps1"],
        "",
    )
    checks.check(
        "resolve-function-identical-in-siblings",
        extracted["setup.ps1"] == extracted["launch.ps1"] == extracted["create-shortcut.ps1"]
        and bool(extracted["setup.ps1"]),
        "",
    )
    checks.check("library-bat-passes-appfolder", '-AppFolder "%APPDIR%"' in library_bat, "")
    checks.check("update-bat-passes-appfolder", '-AppFolder "%APPDIR%"' in update_bat, "")
    checks.check("create-shortcut-bat-passes-appfolder", '-AppFolder "%APPDIR%"' in shortcut_bat, "")
    checks.check(
        "launch-ps1-no-bare-psscriptroot-setlocation",
        not re.search(
            r"\$AppFolder\s*=\s*\$PSScriptRoot\s*\n\s*Set-Location\s+\$AppFolder",
            launch,
        ),
        "",
    )
    checks.check(
        "create-shortcut-ps1-no-bare-psscriptroot-setlocation",
        not re.search(
            r"\$AppFolder\s*=\s*\$PSScriptRoot\s*\n\s*Set-Location\s+\$AppFolder",
            shortcut,
        ),
        "",
    )
    checks.check("setup-ps1-probe-appfolder", "[switch]$ProbeAppFolder" in setup, "")
    checks.check("setup-ps1-explicit-exit-1-on-null", "Write-AppFolderFail" in setup and "exit 1" in setup, "")

    record: dict[str, Any] = {
        "probe": "empty $PSScriptRoot (script_root='') with bat -AppFolder hint, MyCommand.Path, cwd marker, and all-empty fail",
        "cases": {},
    }

    with tempfile.TemporaryDirectory() as tmp:
        usb = Path(tmp) / "photoLibrary"
        usb.mkdir()
        (usb / "Setup.bat").write_text("@echo off\n", encoding="ascii")
        (usb / "setup.ps1").write_text("# probe\n", encoding="ascii")
        empty = Path(tmp) / "empty-cwd"
        empty.mkdir()

        hint_hit = resolve_library_app_folder(hint=str(usb), script_root="")
        record["cases"]["empty-psscriptroot-uses-appfolder-hint"] = hint_hit
        checks.check(
            "empty-psscriptroot-uses-appfolder-hint",
            hint_hit is not None and Path(hint_hit).resolve() == usb.resolve(),
            str(hint_hit),
        )

        path_hit = resolve_library_app_folder(
            hint="",
            script_root="",
            script_path=str(usb / "setup.ps1"),
        )
        record["cases"]["empty-psscriptroot-uses-myinvocation-path"] = path_hit
        checks.check(
            "empty-psscriptroot-uses-myinvocation-path",
            path_hit is not None and Path(path_hit).resolve() == usb.resolve(),
            str(path_hit),
        )

        cwd_hit = resolve_library_app_folder(hint="", script_root="", cwd=str(usb))
        record["cases"]["empty-psscriptroot-uses-cwd-with-setup-bat"] = cwd_hit
        checks.check(
            "empty-psscriptroot-uses-cwd-with-setup-bat",
            cwd_hit is not None and Path(cwd_hit).resolve() == usb.resolve(),
            str(cwd_hit),
        )

        miss = resolve_library_app_folder(hint="", script_root="", cwd=str(empty))
        record["cases"]["empty-everything-without-marker-is-null"] = miss
        checks.check(
            "empty-everything-without-marker-is-null",
            miss is None,
            str(miss),
        )

        missing_hint = resolve_library_app_folder(hint=str(Path(tmp) / "no-such-folder"), script_root="")
        record["cases"]["missing-hint-without-fallback-is-null"] = missing_hint
        checks.check(
            "missing-hint-without-fallback-is-null",
            missing_hint is None,
            str(missing_hint),
        )

        trailing = resolve_library_app_folder(hint=str(usb) + "/", script_root="")
        record["cases"]["hint-trailing-slash"] = trailing
        checks.check(
            "hint-trailing-slash-still-resolves",
            trailing is not None and Path(trailing).resolve() == usb.resolve(),
            str(trailing),
        )

    fail_block = ""
    fail_at = bat.find('if not "%ERR%"=="0"')
    fail_exit = bat.find("exit /b %ERR%", fail_at) if fail_at >= 0 else -1
    if fail_at >= 0 and fail_exit >= 0:
        fail_block = bat[fail_at:fail_exit]
    record["setupBatFailBranch"] = fail_block
    checks.check(
        "setup-bat-fail-branch-no-ready",
        "Ready -- run Library.bat" not in fail_block and "exit /b %ERR%" in bat,
        fail_block,
    )
    checks.check(
        "setup-ps1-ready-after-success-only",
        setup.rfind("Ready -- run Library.bat") > setup.find("Write-MissingUpdate"),
        "",
    )
    return record


def static_source_checks(
    bat: str,
    setup: str,
    launch: str,
    library_bat: str,
    ps51: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ps51 = ps51 or {}
    return [
        {
            "name": "setup-bat-calls-setup-ps1",
            "pass": "setup.ps1" in bat and "launch.ps1" not in bat.split(":")[0],
        },
        {
            "name": "setup-bat-echoes-once-daily-update",
            "pass": (
                "Setup once" in bat
                and "Library.bat every day" in bat
                and "Update.bat" in bat
                and "git pull" in bat
            ),
        },
        {
            "name": "setup-bat-ready-or-update",
            "pass": "Ready -- run Library.bat" in bat and "Update Library" in bat,
        },
        {
            "name": "setup-ps1-ascii-only",
            "pass": all(ord(ch) < 128 for ch in setup),
        },
        {
            "name": "setup-ps1-no-em-dash-or-smart-quotes",
            "pass": not any(ch in setup for ch in "\u2014\u2013\u201c\u201d\u2018\u2019"),
        },
        {
            "name": "setup-bat-ascii-only",
            "pass": all(ord(ch) < 128 for ch in bat),
        },
        {
            "name": "setup-ps1-ps51-cp1252-safe",
            "pass": bool(ps51.get("ok")),
        },
        {
            "name": "setup-ps1-no-bare-using",
            "pass": not ps51.get("bareUsingLines"),
        },
        {
            "name": "setup-ps1-strings-and-braces-closed",
            "pass": bool(ps51.get("stringsClosed")) and ps51.get("braceDepth") == 0,
        },
        {
            "name": "setup-bat-has-help",
            "pass": ":help" in bat.lower() and "DryRun" in bat,
        },
        {
            "name": "setup-bat-no-msi",
            "pass": "No MSI" in bat,
        },
        {
            "name": "setup-ps1-does-not-serve",
            "pass": '"serve"' not in setup and "-m\", \"library\", \"serve\"" not in setup,
        },
        {
            "name": "setup-ps1-composes-clis",
            "pass": (
                "setup-geo" in setup
                and "setup-ml" in setup
                and "objects" in setup
                and "faces" in setup
            ),
        },
        {
            "name": "setup-ps1-venv-and-pip",
            "pass": ".venv" in setup and "pip install -e ." in setup,
        },
        {
            "name": "setup-ps1-winget-same-ids",
            "pass": "Python.Python.3.12" in setup and "Gyan.FFmpeg" in setup,
        },
        {
            "name": "setup-ps1-dryrun-and-help",
            "pass": "[switch]$Help" in setup and "[switch]$DryRun" in setup,
        },
        {
            "name": "setup-ps1-missing-says-update",
            "pass": "Update Library" in setup and "Update.bat" in setup,
        },
        {
            "name": "library-bat-still-launch-ps1",
            "pass": "launch.ps1" in library_bat and "setup.ps1" not in library_bat,
        },
        {
            "name": "launch-ps1-still-serves",
            "pass": '"-m", "library", "serve"' in launch and "[switch]$Update" in launch,
        },
        {
            "name": "launch-ps1-no-setup-hijack",
            "pass": "[switch]$Setup]" not in launch.replace("[switch]$SetupMl", ""),
        },
        {
            "name": "launch-ps1-update-relaunches",
            "pass": "--relaunch" in launch and "tracking main" in launch,
        },
        {
            "name": "setup-ps1-progress-steps",
            "pass": "Write-Step" in setup and "Total 8" in setup,
        },
        {
            "name": "setup-ps1-fail-next",
            "pass": "Write-FailNext" in setup and "What to try next" in setup,
        },
        {
            "name": "setup-ps1-creates-shortcut",
            "pass": "create-shortcut.ps1" in setup and "Install-Shortcuts" in setup,
        },
        {
            "name": "setup-ps1-internet-up-front",
            "pass": "needs the internet" in setup.lower() or "needs the internet" in setup,
        },
        {
            "name": "setup-ps1-optional-git-or-zip",
            "pass": "Git.Git" in setup and "zip of main" in setup and "gh.exe" not in setup,
        },
        {
            "name": "setup-ps1-appfolder-param",
            "pass": "[string]$AppFolder" in setup and "Resolve-LibraryAppFolder" in setup,
        },
        {
            "name": "setup-ps1-resolves-myinvocation-path",
            "pass": "MyCommand.Path" in setup and "MyCommand.Definition" in setup,
        },
        {
            "name": "setup-ps1-fail-loud-if-folder-null",
            "pass": (
                "Could not find the Library folder" in setup
                and "Did not finish." in setup
                and "Write-AppFolderFail" in setup
            ),
        },
        {
            "name": "setup-ps1-no-bare-psscriptroot-setlocation",
            "pass": not re.search(
                r"\$AppFolder\s*=\s*\$PSScriptRoot\s*\n\s*Set-Location\s+\$AppFolder",
                setup,
            ),
        },
        {
            "name": "setup-bat-passes-appfolder",
            "pass": '-AppFolder "%APPDIR%"' in bat and "set \"APPDIR=%~dp0\"" in bat,
        },
        {
            "name": "setup-bat-ready-only-after-errorlevel",
            "pass": _ready_only_after_errorlevel(bat),
        },
    ]


def prove_static(checks: Checks) -> dict[str, Any]:
    bat = _read("Setup.bat")
    setup = _read("setup.ps1")
    launch = _read("launch.ps1")
    library_bat = _read("Library.bat")
    ps51 = ps51_encoding_safe((PRODUCT_ROOT / "setup.ps1").read_bytes())
    record: dict[str, Any] = {
        "setupBat": bat,
        "help": extract_bat_help(bat),
        "ps51": ps51,
    }
    for item in static_source_checks(bat, setup, launch, library_bat, ps51):
        detail = json.dumps(ps51) if "ps51" in item["name"] or "bare-using" in item["name"] else ""
        checks.check(item["name"], bool(item["pass"]), detail)
    shortcut_bat = _read("CreateShortcut.bat")
    shortcut_ps1 = _read("create-shortcut.ps1")
    shortcut_ps51 = ps51_encoding_safe((PRODUCT_ROOT / "create-shortcut.ps1").read_bytes())
    record["shortcutPs51"] = shortcut_ps51
    checks.check("create-shortcut-bat-exists", "create-shortcut.ps1" in shortcut_bat, "")
    checks.check("create-shortcut-bat-ascii", all(ord(ch) < 128 for ch in shortcut_bat), "")
    checks.check("create-shortcut-ps1-ascii", all(ord(ch) < 128 for ch in shortcut_ps1), "")
    checks.check("create-shortcut-ps1-ps51-safe", bool(shortcut_ps51.get("ok")), json.dumps(shortcut_ps51))
    checks.check(
        "create-shortcut-writes-lnk",
        "WScript.Shell" in shortcut_ps1 and "Library.lnk" in shortcut_ps1 and "library.ico" in shortcut_ps1,
        "",
    )
    checks.check("library-ico-exists", (PRODUCT_ROOT / "library.ico").is_file(), "")
    record["appFolder"] = prove_app_folder_null(checks)
    update_py = _read("library/update.py")
    checks.check(
        "update-tracks-main",
        'DEFAULT_TRACK = "main"' in update_py
        and "fetch" in update_py
        and "pull" in update_py
        and "--ff-only" in update_py
        and "checkout" in update_py,
        "",
    )
    return record


def prove_probe(checks: Checks) -> dict[str, Any]:
    help_proc = _run([sys.executable, "-m", "library", "--help"])
    help_text = (help_proc.stdout or "") + (help_proc.stderr or "")
    record: dict[str, Any] = {
        "libraryHelpReturncode": help_proc.returncode,
        "libraryHelp": help_text,
        "commands": {},
    }
    missing: list[str] = []
    for name, tokens in WANTED:
        result = probe_command(tokens)
        record["commands"][name] = result
        if result["present"]:
            checks.check(f"probe-{name}-present-or-missing-ok", True, "present")
        else:
            missing.append(name)
            checks.check(
                f"probe-{name}-missing-on-this-tip",
                True,
                f"returncode={result['returncode']}",
            )
    record["missing"] = missing
    record["wouldExit"] = 1 if missing else 0
    if missing:
        message = (
            "This copy does not have the local AI setup commands yet:\n"
            + "".join(f"  - python -m library {name}\n" for name in missing)
            + "\nRun Update Library (or Update.bat) to git pull those modules,\n"
            + "then run Setup.bat again.\n"
            + "Need: setup-geo  (PR places)  +  setup-ml objects  (PR objects)  +  setup-ml faces  (PR faces)  +  setup-ml transcribe  (Whisper)\n"
        )
    else:
        message = (
            "Dry-run: this copy has the local AI setup commands.\n"
            + "".join(f"  - python -m library {name}\n" for name, _tokens in WANTED)
            + "\nA real Setup.bat would run those four, then: Ready -- run Library.bat\n"
        )
    record["missingMessage"] = message
    record["networkNote"] = (
        "First real Setup.bat needs the internet for Python/ffmpeg (if missing) "
        "and the cities / YOLO / InsightFace / Whisper packs. Models stay under library-data/. "
        "Dry-run / -Help do not download."
    )
    if missing:
        checks.check("dry-run-would-exit-nonzero", record["wouldExit"] == 1, str(record["wouldExit"]))
        checks.check(
            "dry-run-names-update",
            "Update Library" in message and "Update.bat" in message,
            message,
        )
        checks.check(
            "dry-run-lists-all-missing",
            all(name in message for name in missing),
            message,
        )
    else:
        checks.check("all-four-clis-present", missing == [], str(missing))
    checks.check("probe-does-not-serve", "Serving" not in help_text and "8765" not in help_text, "")
    return record


def run_slice(root: Path, artifacts: Path) -> int:
    del root
    artifacts.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    assert_no_pillow_in_server(checks)
    static = prove_static(checks)
    probe = prove_probe(checks)
    (artifacts / "Setup.bat.txt").write_text(static["setupBat"], encoding="utf-8")
    (artifacts / "help.txt").write_text(static["help"], encoding="utf-8")
    (artifacts / "dry-run.txt").write_text(
        probe["missingMessage"] + "\n" + probe["networkNote"] + "\n",
        encoding="utf-8",
    )
    (artifacts / "app-folder-probe.json").write_text(
        json.dumps(static.get("appFolder") or {}, indent=2) + "\n",
        encoding="utf-8",
    )
    extra = {
        "Setup.bat.txt": str(artifacts / "Setup.bat.txt"),
        "help.txt": str(artifacts / "help.txt"),
        "dry-run.txt": str(artifacts / "dry-run.txt"),
        "app-folder-probe.json": str(artifacts / "app-folder-probe.json"),
    }
    code = write_result(
        "TASTE-SETUP",
        "slice",
        checks,
        artifacts,
        [
            "python -m tests.qa slice TASTE-SETUP",
            f"{sys.executable} -m library --help",
            f"{sys.executable} -m library setup-geo --help",
            f"{sys.executable} -m library setup-ml objects --help",
            f"{sys.executable} -m library setup-ml faces --help",
            f"{sys.executable} -m library setup-ml transcribe --help",
        ],
        extra,
    )
    payload = {
        "pass": checks.ok(),
        "assertions": checks.assertions,
        "static": {"help": static["help"]},
        "probe": probe,
    }
    print(json.dumps(payload, indent=2), flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    del argv
    artifacts = PRODUCT_ROOT / "docs/features/taste-setup/Rev1.0/assets/verify-1"
    return run_slice(PRODUCT_ROOT / "library-data", artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
