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


def extract_bat_help(bat: str) -> str:
    marker = ":help"
    index = bat.lower().rfind(marker)
    if index < 0:
        return ""
    return bat[index:]


def static_source_checks(bat: str, setup: str, launch: str, library_bat: str) -> list[dict[str, Any]]:
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
            "pass": "Ready — run Library.bat" in bat and "Update Library" in bat,
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
    ]


def prove_static(checks: Checks) -> dict[str, Any]:
    bat = _read("Setup.bat")
    setup = _read("setup.ps1")
    launch = _read("launch.ps1")
    library_bat = _read("Library.bat")
    record: dict[str, Any] = {
        "setupBat": bat,
        "help": extract_bat_help(bat),
    }
    for item in static_source_checks(bat, setup, launch, library_bat):
        checks.check(item["name"], bool(item["pass"]), "")
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
    message = (
        "This copy does not have the local AI setup commands yet:\n"
        + "".join(f"  - python -m library {name}\n" for name in missing)
        + "\nRun Update Library (or Update.bat) to git pull those modules,\n"
        + "then run Setup.bat again.\n"
        + "Need: setup-geo  (PR places)  +  setup-ml objects  (PR objects)  +  setup-ml faces  (PR faces)\n"
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
    payload = {
        "pass": checks.failed == 0,
        "assertions": checks.assertions,
        "static": {"help": static["help"]},
        "probe": probe,
    }
    write_result(artifacts, payload)
    print(json.dumps(payload, indent=2), flush=True)
    return 0 if payload["pass"] else 1


def main(argv: list[str] | None = None) -> int:
    del argv
    artifacts = PRODUCT_ROOT / "docs/features/taste-setup/Rev1.0/assets/verify-1"
    return run_slice(PRODUCT_ROOT / "library-data", artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
