"""One-off local paired-still comparison; uses copied fixture JPEGs only."""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))
from library.renditions import write_webp, write_webp_pair  # noqa: E402

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"
BEFORE = HERE / "before"
PAIRED = HERE / "paired"
THUMB_CAP, PREVIEW_CAP = 320, 1600


def clear(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.iterdir():
        if path.is_file():
            path.unlink()


def dimensions(path: Path) -> list[int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, check=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return [stream["width"], stream["height"]]


def old_pair(inputs: list[Path]) -> None:
    clear(BEFORE)
    for source in inputs:
        if not write_webp(source, BEFORE / f"thumb-{source.stem}.webp", THUMB_CAP):
            raise RuntimeError(f"thumb failed: {source.name}")
        if not write_webp(source, BEFORE / f"preview-{source.stem}.webp", PREVIEW_CAP):
            raise RuntimeError(f"preview failed: {source.name}")


def new_pair(inputs: list[Path]) -> None:
    clear(PAIRED)
    for source in inputs:
        if not write_webp_pair(
            source,
            PAIRED / f"thumb-{source.stem}.webp.tmp", THUMB_CAP,
            PAIRED / f"preview-{source.stem}.webp.tmp", PREVIEW_CAP,
        ):
            raise RuntimeError(f"pair failed: {source.name}")


def main() -> None:
    inputs = sorted(SAMPLES.glob("*.jpg")) + sorted(SAMPLES.glob("*.jpeg"))
    if len(inputs) < 10:
        raise RuntimeError(f"expected about 12 copied JPEGs, found {len(inputs)}")
    times: dict[str, list[float]] = {"two_process": [], "one_process_pair": []}
    for _ in range(3):
        for name, run in (("two_process", old_pair), ("one_process_pair", new_pair)):
            started = time.perf_counter()
            run(inputs)
            times[name].append(time.perf_counter() - started)
    first_thumb_seconds: list[float] = []
    first_pair_seconds: list[float] = []
    first_source = inputs[0]
    for index in range(5):
        thumb_path = HERE / f"first-thumb-{index}.webp"
        thumb_path.unlink(missing_ok=True)
        started = time.perf_counter()
        if not write_webp(first_source, thumb_path, THUMB_CAP):
            raise RuntimeError("first-thumb encode failed")
        first_thumb_seconds.append(time.perf_counter() - started)
        thumb_path.unlink(missing_ok=True)
        thumb_stage = HERE / f"first-thumb-pair-{index}.webp.tmp"
        preview_stage = HERE / f"first-preview-pair-{index}.webp.tmp"
        started = time.perf_counter()
        if not write_webp_pair(first_source, thumb_stage, THUMB_CAP, preview_stage, PREVIEW_CAP):
            raise RuntimeError("first paired encode failed")
        first_pair_seconds.append(time.perf_counter() - started)
        thumb_stage.unlink(missing_ok=True)
        preview_stage.unlink(missing_ok=True)
    old_outputs = sorted(BEFORE.iterdir())
    pair_outputs = sorted(PAIRED.iterdir())
    old_sizes = {path.name: path.stat().st_size for path in old_outputs}
    pair_sizes = {
        path.name.removesuffix(".tmp"): path.stat().st_size for path in pair_outputs
    }
    dims = {
        "two_process": {path.name: dimensions(path) for path in old_outputs},
        "one_process_pair": {
            path.name.removesuffix(".tmp"): dimensions(path) for path in pair_outputs
        },
    }
    report = {
        "inputs": [{"name": p.name, "bytes": p.stat().st_size} for p in inputs],
        "inputCount": len(inputs),
        "caps": {"thumbPx": THUMB_CAP, "previewPx": PREVIEW_CAP},
        "timesSeconds": times,
        "medianSeconds": {key: statistics.median(value) for key, value in times.items()},
        "speedup": round(statistics.median(times["two_process"]) / statistics.median(times["one_process_pair"]), 3),
        "firstItemThumbMedianSeconds": {
            "thumb_only": statistics.median(first_thumb_seconds),
            "paired_thumb_and_preview": statistics.median(first_pair_seconds),
        },
        "outputBytes": {"two_process": old_sizes, "one_process_pair": pair_sizes},
        "dimensions": dims,
    }
    if old_sizes != pair_sizes:
        raise RuntimeError("output sizes differ by slot/item")
    if dims["two_process"] != dims["one_process_pair"]:
        raise RuntimeError("output dimensions differ by slot/item")
    (HERE / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("inputCount", "medianSeconds", "speedup")}, indent=2))


if __name__ == "__main__":
    main()
