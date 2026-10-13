"""python -m tests.qa fixtures|slice|check|all"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[2]


def _add_venv() -> None:
    windows_site = PRODUCT_ROOT / ".venv" / "Lib" / "site-packages"
    if windows_site.is_dir() and str(windows_site) not in sys.path:
        sys.path.insert(0, str(windows_site))
    linux_root = PRODUCT_ROOT / ".venv" / "lib"
    if linux_root.is_dir():
        for linux_site in sorted(linux_root.glob("python3.*/site-packages")):
            if linux_site.is_dir() and str(linux_site) not in sys.path:
                sys.path.insert(0, str(linux_site))
    if str(PRODUCT_ROOT) not in sys.path:
        sys.path.insert(0, str(PRODUCT_ROOT))


_add_venv()

from tests.qa.s00 import copy_committed_fixtures  # noqa: E402


class _Tee:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._console = sys.stdout
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")

    def write(self, data: str) -> int:
        try:
            self._console.write(data)
        except UnicodeEncodeError:
            encoding = getattr(self._console, "encoding", None) or "ascii"
            self._console.write(data.encode(encoding, "backslashreplace").decode(encoding, "replace"))
        self._file.write(data)
        self._file.flush()
        return len(data)

    def flush(self) -> None:
        self._console.flush()
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _fail_unimplemented(kind: str, ident: str, artifacts: Path | None) -> int:
    payload = {
        kind: ident,
        "pass": False,
        "assertions": [
            {
                "name": "implemented",
                "pass": False,
                "detail": f"{kind} {ident} is not implemented in S00",
            }
        ],
    }
    print(json.dumps(payload, indent=2), flush=True)
    if artifacts is not None:
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "result.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    return 1


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _run_logged(runner, root: Path, artifacts: Path) -> int:
    artifacts.mkdir(parents=True, exist_ok=True)
    tee = _Tee(artifacts / "stdout.log")
    prev = sys.stdout
    sys.stdout = tee  # type: ignore[assignment]
    try:
        return runner(root, artifacts)
    finally:
        sys.stdout = prev
        tee.close()


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = argparse.ArgumentParser(prog="python -m tests.qa")
    sub = parser.add_subparsers(dest="cmd")

    fixtures = sub.add_parser("fixtures")
    fixtures.add_argument("--output", required=True)

    slice_p = sub.add_parser("slice")
    slice_p.add_argument("slice_id")
    slice_p.add_argument("--root", required=True)
    slice_p.add_argument("--artifacts", required=True)

    check_p = sub.add_parser("check")
    check_p.add_argument("feature_id")
    check_p.add_argument("--root", required=True)
    check_p.add_argument("--artifacts", required=True)

    all_p = sub.add_parser("all")
    all_p.add_argument("--root", required=True)
    all_p.add_argument("--artifacts", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "fixtures":
        copy_committed_fixtures(Path(args.output))
        print(f"copied fixtures to {args.output}", flush=True)
        return 0
    if args.cmd == "slice":
        if args.slice_id == "S00":
            from tests.qa.s00 import run_slice as runner
        elif args.slice_id == "S01":
            from tests.qa.s01 import run_slice as runner
        elif args.slice_id == "S02":
            from tests.qa.s02 import run_slice as runner
        elif args.slice_id == "S03":
            from tests.qa.s03 import run_slice as runner
        else:
            return _fail_unimplemented("slice", args.slice_id, Path(args.artifacts))
        return _run_logged(runner, Path(args.root), Path(args.artifacts))
    if args.cmd == "check":
        if args.feature_id == "F6":
            from tests.qa.s02 import run_check as runner
        else:
            return _fail_unimplemented("check", args.feature_id, Path(args.artifacts))
        return _run_logged(runner, Path(args.root), Path(args.artifacts))
    if args.cmd == "all":
        return _fail_unimplemented("all", "all", Path(args.artifacts))
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
