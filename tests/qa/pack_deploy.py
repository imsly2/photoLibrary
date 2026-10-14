"""Lean PackDeploy zip: static contract + sandbox + real-repo pack. Not an F-id."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from tests.qa.s00 import PRODUCT_ROOT, Checks
from tests.qa.s08 import write_result
from tests.qa.setup_portable import ps51_encoding_safe

FORBIDDEN_IN_ZIP = (
    ".venv/",
    "venv/",
    "library-data/",
    ".git/",
    "docs/",
    "tests/",
    ".qa/",
    "__pycache__/",
    "captureregion/",
)

REQUIRED_IN_ZIP = (
    "photoLibrary/Setup.bat",
    "photoLibrary/setup.ps1",
    "photoLibrary/Library.bat",
    "photoLibrary/Update.bat",
    "photoLibrary/pyproject.toml",
    "photoLibrary/README.md",
    "photoLibrary/pack-deploy.py",
)


def _read(name: str) -> str:
    return (PRODUCT_ROOT / name).read_text(encoding="utf-8")


def _run_pack(app: Path, dest: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(PRODUCT_ROOT / "pack-deploy.py"),
        "--app-folder",
        str(app),
        "--output",
        str(dest),
    ]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, cwd=str(PRODUCT_ROOT), capture_output=True, text=True)


def _zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def _has_prefix(names: list[str], prefix: str) -> bool:
    lowered = prefix.lower()
    return any(item.lower().startswith(lowered) or ("/" + lowered) in item.lower() for item in names)


def prove_scripts(checks: Checks) -> None:
    bat = _read("PackDeploy.bat")
    ps1 = _read("pack-deploy.ps1")
    py = _read("pack-deploy.py")
    raw_ps1 = (PRODUCT_ROOT / "pack-deploy.ps1").read_bytes()
    ps51 = ps51_encoding_safe(raw_ps1)
    checks.check("pack-bat-ascii", all(ord(ch) < 128 for ch in bat), "")
    checks.check("pack-ps1-ascii", all(ord(ch) < 128 for ch in ps1) and all(b < 128 for b in raw_ps1), "")
    checks.check("pack-py-ascii", all(ord(ch) < 128 for ch in py), "")
    checks.check("pack-ps1-ps51-safe", bool(ps51.get("ok")), json.dumps(ps51, sort_keys=True))
    checks.check("pack-bat-calls-ps1", "pack-deploy.ps1" in bat, "")
    checks.check("pack-ps1-calls-py", "pack-deploy.py" in ps1, "")
    checks.check("pack-overwrite", "overwrites" in bat.lower() or "overwrite" in py.lower(), "")
    checks.check("pack-help", ":help" in bat.lower() and "-DryRun" in bat, "")
    checks.check("pack-excludes-named", ".venv" in py and "library-data" in py and "docs" in py and "tests" in py, "")
    checks.check("pack-includes-setup", "Setup.bat" in py and "library" in py, "")


def prove_sandbox(checks: Checks, artifacts: Path) -> dict[str, Any]:
    sandbox = artifacts / "sandbox-app"
    if sandbox.exists():
        for child in sorted(sandbox.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            else:
                child.rmdir()
        sandbox.rmdir()
    sandbox.mkdir(parents=True)

    (sandbox / "Setup.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "setup.ps1").write_text("# setup\n", encoding="ascii")
    (sandbox / "Library.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "Update.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "CreateShortcut.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "create-shortcut.ps1").write_text("# shortcut\n", encoding="ascii")
    (sandbox / "Launch.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "launch.ps1").write_text("# launch\n", encoding="ascii")
    (sandbox / "launch.sh").write_text("#!/bin/sh\n", encoding="ascii")
    (sandbox / "PackDeploy.bat").write_text("@echo off\n", encoding="ascii")
    (sandbox / "pack-deploy.ps1").write_text("# pack\n", encoding="ascii")
    (sandbox / "pack-deploy.py").write_text("# pack\n", encoding="ascii")
    (sandbox / "pyproject.toml").write_text("[project]\nname='library'\n", encoding="ascii")
    (sandbox / "README.md").write_text("Library\n", encoding="ascii")
    (sandbox / "library.ico").write_bytes(b"ico")
    (sandbox / "AGENTS.md").write_text("agent junk\n", encoding="ascii")
    lib = sandbox / "library"
    lib.mkdir()
    (lib / "__init__.py").write_text("", encoding="ascii")
    (lib / "web").mkdir()
    (lib / "web" / "index.html").write_text("<html></html>\n", encoding="ascii")
    cache = lib / "__pycache__"
    cache.mkdir()
    (cache / "skip.pyc").write_bytes(b"pyc")
    (lib / "gone.pyc").write_bytes(b"pyc")

    (sandbox / ".venv" / "Lib").mkdir(parents=True)
    (sandbox / ".venv" / "Lib" / "huge.bin").write_bytes(b"x" * 1024)
    (sandbox / "library-data" / "catalog").mkdir(parents=True)
    (sandbox / "library-data" / "catalog" / "item.json").write_text("{}\n", encoding="ascii")
    (sandbox / ".git").mkdir()
    (sandbox / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
    (sandbox / "docs").mkdir()
    (sandbox / "docs" / "PRODUCT.md").write_text("# product\n", encoding="ascii")
    (sandbox / "tests").mkdir()
    (sandbox / "tests" / "qa.py").write_text("# test\n", encoding="ascii")
    (sandbox / ".qa").mkdir()
    (sandbox / ".qa" / "tmp").write_text("x\n", encoding="ascii")
    (sandbox / "CaptureRegion").mkdir()
    (sandbox / "CaptureRegion" / "shot.png").write_bytes(b"png")
    (sandbox / "library.egg-info").mkdir()
    (sandbox / "library.egg-info" / "PKG-INFO").write_text("x\n", encoding="ascii")

    dest = artifacts / "sandbox-deploy.zip"
    if dest.exists():
        dest.unlink()
    proc = _run_pack(sandbox, dest)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    (artifacts / "sandbox-stdout.txt").write_text(combined, encoding="utf-8")
    checks.check("sandbox-pack-exit-0", proc.returncode == 0, combined[-800:])
    checks.check("sandbox-zip-exists", dest.is_file(), str(dest))
    names = _zip_names(dest) if dest.is_file() else []
    (artifacts / "sandbox-names.json").write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
    checks.check("sandbox-has-setup", "photoLibrary/Setup.bat" in names, str(names[:20]))
    checks.check("sandbox-has-library", any(item.startswith("photoLibrary/library/") for item in names), "")
    checks.check("sandbox-has-init", "photoLibrary/library/__init__.py" in names, "")
    for token in FORBIDDEN_IN_ZIP:
        checks.check(
            "sandbox-no-" + token.strip("/").replace(".", ""),
            not _has_prefix(names, "photoLibrary/" + token),
            token,
        )
    checks.check("sandbox-no-pyc", not any(item.endswith(".pyc") for item in names), "")
    checks.check("sandbox-no-egg-info", not any(".egg-info" in item for item in names), "")
    checks.check("sandbox-no-agents", not any(item.lower().endswith("/agents.md") for item in names), "")
    checks.check("sandbox-skipped-printed", ".venv/" in combined or ".venv" in combined, combined[-400:])
    return {"names": names, "returncode": proc.returncode, "zip": str(dest)}


def prove_repo(checks: Checks, artifacts: Path) -> dict[str, Any]:
    dest = artifacts / "photoLibrary-deploy.zip"
    if dest.exists():
        dest.unlink()
    dry = _run_pack(PRODUCT_ROOT, dest, extra=["--dry-run"])
    dry_text = (dry.stdout or "") + "\n" + (dry.stderr or "")
    (artifacts / "dry-run.txt").write_text(dry_text, encoding="utf-8")
    checks.check("dry-run-exit-0", dry.returncode == 0, dry_text[-600:])
    checks.check("dry-run-no-zip", not dest.exists(), str(dest))
    checks.check("dry-run-mentions-setup", "Setup.bat" in dry_text, "")
    checks.check("dry-run-mentions-library", "library/" in dry_text, "")
    checks.check("dry-run-mentions-skip", "Skipped" in dry_text, "")

    proc = _run_pack(PRODUCT_ROOT, dest)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    (artifacts / "pack-stdout.txt").write_text(text, encoding="utf-8")
    checks.check("repo-pack-exit-0", proc.returncode == 0, text[-800:])
    checks.check("repo-zip-exists", dest.is_file() and dest.stat().st_size > 0, str(dest))
    names = _zip_names(dest) if dest.is_file() else []
    (artifacts / "repo-names.json").write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
    size = dest.stat().st_size if dest.is_file() else 0
    checks.check("repo-zip-small", size < 20 * 1024 * 1024, str(size))
    for required in REQUIRED_IN_ZIP:
        checks.check("repo-has-" + Path(required).name.lower().replace(".", "-"), required in names, required)
    checks.check(
        "repo-has-library-tree",
        any(item.startswith("photoLibrary/library/") and item.endswith(".py") for item in names),
        "",
    )
    checks.check(
        "repo-has-web",
        any(item.startswith("photoLibrary/library/web/") for item in names),
        "",
    )
    for token in FORBIDDEN_IN_ZIP:
        checks.check(
            "repo-no-" + token.strip("/").replace(".", ""),
            not _has_prefix(names, "photoLibrary/" + token),
            token,
        )
    checks.check("repo-no-pyc", not any(item.endswith(".pyc") for item in names), "")
    checks.check("repo-next-step", "Setup.bat" in text and "extract" in text.lower(), "")
    checks.check("repo-overwrite-said", "overwrite" in text.lower(), "")
    return {
        "names": names,
        "returncode": proc.returncode,
        "zip": str(dest),
        "size": size,
        "dryRun": dry_text,
    }


def run(artifacts: Path) -> int:
    artifacts.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    prove_scripts(checks)
    sandbox = prove_sandbox(checks, artifacts)
    repo = prove_repo(checks, artifacts)
    extra = {
        "sandbox-deploy.zip": sandbox.get("zip", ""),
        "photoLibrary-deploy.zip": repo.get("zip", ""),
        "dry-run.txt": str(artifacts / "dry-run.txt"),
        "pack-stdout.txt": str(artifacts / "pack-stdout.txt"),
    }
    return write_result(
        "TASTE-PACK",
        "slice",
        checks,
        artifacts,
        ["python -m tests.qa.pack_deploy"],
        extra_paths=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove PackDeploy zip includes Setup/library and excludes fat trees.")
    parser.add_argument(
        "--artifacts",
        default=str(PRODUCT_ROOT / "docs" / "features" / "taste-pack" / "Rev1.0" / "assets" / "verify-1"),
    )
    args = parser.parse_args(argv)
    return run(Path(args.artifacts))


if __name__ == "__main__":
    sys.exit(main())
