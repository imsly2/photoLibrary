"""One-off: where does a paired thumb+preview FFmpeg call spend time on real photos?"""
import json, os, shutil, statistics, subprocess, sys, time
from pathlib import Path

os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ["PATH"]
HERE = Path(__file__).parent
SRC = Path(r"J:\Pictures\1. Favorites Pictures")
samples = HERE / "samples"
samples.mkdir(exist_ok=True)
if not any(samples.iterdir()):
    for p in sorted(SRC.glob("*.jpg"))[:8]:
        shutil.copy2(p, samples / p.name)
out = HERE / "out"
shutil.rmtree(out, ignore_errors=True)
out.mkdir()


def scale(cap):
    return f"scale='if(gte(iw,ih),min(iw,{cap}),-2)':'if(lt(iw,ih),min(ih,{cap}),-2)'"


def pair(pre, enc, flags=""):
    def cmd(src, tag):
        sf = (lambda c: scale(c) + (f":flags={flags}" if flags else ""))
        g = f"[0:v]split=2[a][b];[a]{sf(320)}[t];[b]{sf(1600)}[p]"
        return ["ffmpeg", "-v", "error", "-y", *pre, "-i", str(src), "-filter_complex", g,
                "-map", "[t]", "-frames:v", "1", *enc, "-f", "webp", str(out / f"{tag}-t.webp"),
                "-map", "[p]", "-frames:v", "1", *enc, "-f", "webp", str(out / f"{tag}-p.webp")]
    return cmd


variants = {
    "default": pair([], []),
    "comp2": pair([], ["-compression_level", "2"]),
    "comp0": pair([], ["-compression_level", "0"]),
    "lowres1": pair(["-lowres", "1"], []),
    "lowres1_comp2": pair(["-lowres", "1"], ["-compression_level", "2"]),
    "bilinear_comp2": pair([], ["-compression_level", "2"], "bilinear"),
}
files = sorted(samples.glob("*.jpg"))
res = {}
for name, cmd in variants.items():
    runs = []
    for _ in range(3):
        t = time.perf_counter()
        for i, f in enumerate(files):
            p = subprocess.run(cmd(f, f"{name}-{i}"), capture_output=True)
            if p.returncode:
                print(name, p.stderr.decode()[-300:])
        runs.append(time.perf_counter() - t)
    sizes = sum((out / f"{name}-{i}-p.webp").stat().st_size for i in range(len(files)))
    dims = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                           str(out / f"{name}-0-p.webp")], capture_output=True, text=True).stdout.strip()
    res[name] = {"perPhotoMs": round(statistics.median(runs) / len(files) * 1000), "previewKB": sizes // 1024, "preview0": dims}
    print(name, res[name], flush=True)
src0 = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(files[0])],
                      capture_output=True, text=True).stdout.strip()
res["_source0"] = src0
(HERE / "results.json").write_text(json.dumps(res, indent=1))
