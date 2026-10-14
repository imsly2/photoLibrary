"""Dry assertion for launch.ps1 ArgumentList on a 1-element python command.

PowerShell `$arr[1..0]` walks indices 1 then 0. The old launcher therefore
put python.exe into argv[1]. This module documents that before/after and
asserts the Length-gt-1 helper never does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[2]


def powershell_range(start: int, end: int) -> list[int]:
    """PowerShell `start..end` — descending when start > end."""
    step = 1 if end >= start else -1
    return list(range(start, end + step, step))


def slice_extras(python: list[str]) -> list[str]:
    """The old `$python[1..($python.Length - 1)] | Where-Object { $_ }`."""
    extras: list[str] = []
    for index in powershell_range(1, len(python) - 1):
        if 0 <= index < len(python) and python[index]:
            extras.append(python[index])
    return extras


def buggy_argument_list(python: list[str]) -> list[str]:
    return slice_extras(python) + ["-m", "library", "serve"]


def serve_argument_list(python: list[str]) -> list[str]:
    extras: list[str] = []
    if len(python) > 1:
        extras = slice_extras(python)
    return extras + ["-m", "library", "serve"]


def looks_like_python_exe(value: str) -> bool:
    name = Path(value.replace("\\", "/")).name.lower()
    return name in {"python.exe", "python", "python3.exe", "python3"}


def unwrapped_filepath(python: str) -> str:
    """PowerShell indexes a STRING as characters, so `$python[0]` is `C`."""
    return python[0] if python else ""


def cases() -> list[dict[str, object]]:
    one = [r"C:\Users\Family\AppData\Local\Programs\Python\Python312\python.exe"]
    py = [r"C:\Windows\py.exe", "-3.12"]
    venv = [r"C:\Library\.venv\Scripts\python.exe"]
    return [
        {
            "name": "unwrapped-string-filepath",
            "python": one[0],
            "before": {
                "FilePath": unwrapped_filepath(one[0]),
                "ArgumentList": buggy_argument_list(list(one[0])),
            },
            "after": {
                "FilePath": one[0],
                "ArgumentList": serve_argument_list(one),
            },
        },
        {
            "name": "length-1-python-exe",
            "python": one,
            "before": {
                "FilePath": one[0],
                "ArgumentList": buggy_argument_list(one),
            },
            "after": {
                "FilePath": one[0],
                "ArgumentList": serve_argument_list(one),
            },
        },
        {
            "name": "length-2-py-3.12",
            "python": py,
            "before": {
                "FilePath": py[0],
                "ArgumentList": buggy_argument_list(py),
            },
            "after": {
                "FilePath": py[0],
                "ArgumentList": serve_argument_list(py),
            },
        },
        {
            "name": "length-1-venv-python-exe",
            "python": venv,
            "before": {
                "FilePath": venv[0],
                "ArgumentList": buggy_argument_list(venv),
            },
            "after": {
                "FilePath": venv[0],
                "ArgumentList": serve_argument_list(venv),
            },
        },
    ]


def static_source_checks() -> list[dict[str, object]]:
    launch = (PRODUCT_ROOT / "launch.ps1").read_text(encoding="utf-8")
    bat = (PRODUCT_ROOT / "Library.bat").read_text(encoding="utf-8")
    return [
        {
            "name": "guard-length-gt-1",
            "pass": "$python.Count -gt 1" in launch or "$Python.Count -gt 1" in launch or "$python.Length -gt 1" in launch or "$Python.Length -gt 1" in launch,
        },
        {
            "name": "prefers-venv-scripts-python",
            "pass": r".venv\Scripts\python.exe" in launch,
        },
        {
            "name": "library-bat-pauses-on-error",
            "pass": "if errorlevel 1 pause" in bat.lower() or "if errorlevel 1 pause" in bat,
        },
        {
            "name": "no-unguarded-start-process-slice",
            "pass": "Start-Process -FilePath $python[0] -ArgumentList (@($python[1.." not in launch,
        },
        {
            "name": "rewrapped-python-array",
            "pass": "$python = @(Get-Python312)" in launch,
        },
        {
            "name": "exe-is-string-index-zero",
            "pass": "$exe = [string]$python[0]" in launch and "Start-Process -FilePath $exe" in launch,
        },
        {
            "name": "unary-comma-single-source",
            "pass": "return ,@($cmd.Source)" in launch or "return ,@($venv)" in launch,
        },
        {
            "name": "keeps-update-switch",
            "pass": "[switch]$Update" in launch and '"-m", "library", "update"' in launch,
        },
    ]


def run_assertions() -> dict[str, object]:
    assertions: list[dict[str, object]] = []
    documented = cases()
    for case in documented:
        after = case["after"]["ArgumentList"]
        before = case["before"]["ArgumentList"]
        python = case["python"]
        name = str(case["name"])
        if name == "unwrapped-string-filepath":
            assertions.append(
                {
                    "name": f"{name}-before-filepath-is-C",
                    "pass": case["before"]["FilePath"] == "C",
                    "detail": {"FilePath": case["before"]["FilePath"]},
                }
            )
            assertions.append(
                {
                    "name": f"{name}-after-filepath-is-full-exe",
                    "pass": case["after"]["FilePath"] == python and looks_like_python_exe(str(case["after"]["FilePath"])),
                    "detail": {"FilePath": case["after"]["FilePath"]},
                }
            )
            assertions.append(
                {
                    "name": f"{name}-after-excludes-python-exe",
                    "pass": after == ["-m", "library", "serve"],
                    "detail": {"ArgumentList": after},
                }
            )
            continue
        if name.startswith("length-1"):
            ok_before_has_exe = any(looks_like_python_exe(part) for part in before)
            assertions.append(
                {
                    "name": f"{name}-before-includes-python-exe",
                    "pass": ok_before_has_exe,
                    "detail": {"ArgumentList": before},
                }
            )
            ok_after_clean = not any(looks_like_python_exe(part) for part in after)
            assertions.append(
                {
                    "name": f"{name}-after-excludes-python-exe",
                    "pass": ok_after_clean,
                    "detail": {"ArgumentList": after},
                }
            )
            assertions.append(
                {
                    "name": f"{name}-after-is-module-serve",
                    "pass": after == ["-m", "library", "serve"],
                    "detail": {"ArgumentList": after},
                }
            )
        else:
            assertions.append(
                {
                    "name": f"{name}-keeps-launcher-extra",
                    "pass": after == ["-3.12", "-m", "library", "serve"] and after == before,
                    "detail": {"ArgumentList": after},
                }
            )
        assertions.append(
            {
                "name": f"{name}-filepath-is-interpreter",
                "pass": case["after"]["FilePath"] == python[0],
                "detail": str(case["after"]["FilePath"]),
            }
        )
    for item in static_source_checks():
        assertions.append({"name": item["name"], "pass": item["pass"], "detail": ""})

    payload = {
        "pass": all(bool(item["pass"]) for item in assertions),
        "beforeAfter": documented,
        "assertions": assertions,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    del argv
    payload = run_assertions()
    print(json.dumps(payload, indent=2), flush=True)
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
