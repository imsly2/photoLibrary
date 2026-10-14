"""Portable Setup.bat: static contract + missing-module dry-run. Not an F-id."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.qa.s00 import PRODUCT_ROOT, Checks, assert_no_pillow_in_server
from tests.qa.s08 import write_result

WANTED = (
    ("setup-geo", ["setup-geo"]),
    ("setup-ml objects", ["setup-ml", "objects"]),
    ("setup-ml faces", ["setup-ml", "faces"]),
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
            "pass": "Write-Step" in setup and "Total 7" in setup,
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
            + "Need: setup-geo  (PR places)  +  setup-ml objects  (PR objects)  +  setup-ml faces  (PR faces)\n"
        )
    else:
        message = (
            "Dry-run: this copy has the local AI setup commands.\n"
            + "".join(f"  - python -m library {name}\n" for name, _tokens in WANTED)
            + "\nA real Setup.bat would run those three, then: Ready -- run Library.bat\n"
        )
    record["missingMessage"] = message
    record["networkNote"] = (
        "First real Setup.bat needs the internet for Python/ffmpeg (if missing) "
        "and the cities / YOLO / InsightFace packs. Models stay under library-data/. "
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
        checks.check("all-three-clis-present", missing == [], str(missing))
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
    extra = {
        "Setup.bat.txt": str(artifacts / "Setup.bat.txt"),
        "help.txt": str(artifacts / "help.txt"),
        "dry-run.txt": str(artifacts / "dry-run.txt"),
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
