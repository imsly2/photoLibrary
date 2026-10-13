"""Write synthetic fixture media. Does not scan user photos."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import piexif
from PIL import Image, ImageDraw, ImageFont

from tests.qa.probe import VALID_HEIF_BRANDS, probe_file, read_ftyp_brands

LIVE_CONTENT_ID = "11111111-2222-4333-8444-555555555555"
CLIP_LOCATION = "+41.8800-087.6300+000.0/"
DEFAULT_MTIME = "2022-01-01T00:00:00Z"
LONG_REL = (
    "nested/deep/level03/level04/level05/dir/dir/dir/"
    "raw_relative_path_would_make_a_bad_pending_json_filename.jpg"
)
UNICODE_REL = "family/旅行 photo.jpg"


def _palette(name: str) -> list[tuple[int, int, int]]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    colors = []
    for i in range(4):
        colors.append(
            (
                40 + digest[i * 3] % 180,
                40 + digest[i * 3 + 1] % 180,
                40 + digest[i * 3 + 2] % 180,
            )
        )
    return colors


def _font(size: int = 28) -> ImageFont.ImageFont:
    for candidate in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _quadrant(name: str, *, asymmetric: bool = False) -> Image.Image:
    image = Image.new("RGB", (640, 480), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    if asymmetric:
        draw.rectangle((0, 0, 120, 480), fill=(210, 30, 30))
        draw.rectangle((120, 0, 640, 160), fill=(30, 40, 180))
        draw.rectangle((120, 160, 640, 480), fill=(40, 160, 70))
        draw.polygon([(400, 200), (600, 200), (500, 420)], fill=(240, 220, 40))
    else:
        colors = _palette(name)
        draw.rectangle((0, 0, 320, 240), fill=colors[0])
        draw.rectangle((320, 0, 640, 240), fill=colors[1])
        draw.rectangle((0, 240, 320, 480), fill=colors[2])
        draw.rectangle((320, 240, 640, 480), fill=colors[3])
    draw.text((16, 16), name, fill=(255, 255, 255), font=_font())
    return image


def _dms(value: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    abs_v = abs(value)
    deg = int(abs_v)
    minutes_f = (abs_v - deg) * 60
    minutes = int(minutes_f)
    seconds = (minutes_f - minutes) * 60
    return ((deg, 1), (minutes, 1), (int(round(seconds * 10000)), 10000))


def _exif_bytes(
    *,
    orientation: int | None = 1,
    datetime_original: str | None = None,
    datetime_digitized: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> bytes | None:
    zeroth: dict[int, Any] = {}
    exif: dict[int, Any] = {}
    gps: dict[int, Any] = {}
    if orientation is not None:
        zeroth[piexif.ImageIFD.Orientation] = orientation
    if datetime_original:
        exif[piexif.ExifIFD.DateTimeOriginal] = datetime_original.encode("ascii")
    if datetime_digitized:
        exif[piexif.ExifIFD.DateTimeDigitized] = datetime_digitized.encode("ascii")
    if latitude is not None and longitude is not None:
        gps[piexif.GPSIFD.GPSLatitudeRef] = b"N" if latitude >= 0 else b"S"
        gps[piexif.GPSIFD.GPSLatitude] = _dms(latitude)
        gps[piexif.GPSIFD.GPSLongitudeRef] = b"E" if longitude >= 0 else b"W"
        gps[piexif.GPSIFD.GPSLongitude] = _dms(longitude)
    if not zeroth and not exif and not gps:
        return None
    payload: dict[str, Any] = {"0th": zeroth, "Exif": exif, "GPS": gps}
    return piexif.dump(payload)


def _inject_xmp(jpeg: bytes, content_id: str) -> bytes:
    xmp = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:apple-exif="http://ns.apple.com/exif/1.0/" '
        + f'apple-exif:ContentIdentifier="{content_id}"/>'.encode("ascii")
        + b"</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
    )
    header = b"http://ns.adobe.com/xap/1.0/\x00"
    payload = header + xmp
    app1 = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    if not jpeg.startswith(b"\xff\xd8"):
        raise RuntimeError("not-jpeg")
    return jpeg[:2] + app1 + jpeg[2:]


def _pin_mtime(path: Path, iso: str) -> None:
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def _write_still(
    dest: Path,
    rel: str,
    *,
    fmt: str = "JPEG",
    orientation: int | None = 1,
    datetime_original: str | None = None,
    datetime_digitized: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    content_id: str | None = None,
    asymmetric: bool = False,
    mtime: str = DEFAULT_MTIME,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    image = _quadrant(rel, asymmetric=asymmetric)
    exif = _exif_bytes(
        orientation=orientation,
        datetime_original=datetime_original,
        datetime_digitized=datetime_digitized,
        latitude=latitude,
        longitude=longitude,
    )
    save_kwargs: dict[str, Any] = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs.update(quality=92, subsampling=0)
        if exif:
            save_kwargs["exif"] = exif
    elif fmt == "WEBP":
        save_kwargs["quality"] = 90
    image.save(dest, **save_kwargs)
    if content_id:
        dest.write_bytes(_inject_xmp(dest.read_bytes(), content_id))
    _pin_mtime(dest, mtime)


def _write_heif(dest: Path, rel: str, mtime: str = DEFAULT_MTIME) -> None:
    import pillow_heif

    dest.parent.mkdir(parents=True, exist_ok=True)
    image = _quadrant(rel)
    heif = pillow_heif.from_pillow(image)
    heif.save(dest, quality=90)
    brands = read_ftyp_brands(dest.read_bytes())
    if dest.read_bytes().startswith(b"\xff\xd8"):
        raise RuntimeError(f"HEIC/HEIF fixture {rel} is a JPEG, not a real HEIF")
    if not any(brand.strip() in VALID_HEIF_BRANDS for brand in brands):
        raise RuntimeError(
            f"HEIC/HEIF fixture {rel} missing ftyp brand heic/heix/heif/mif1; got {brands}"
        )
    _pin_mtime(dest, mtime)


def _ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg-failed")


def _hex_color(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return f"#{digest[0]:02x}{digest[1]:02x}{digest[2]:02x}"


def _write_video(
    dest: Path,
    rel: str,
    *,
    vcodec: str,
    acodec: str,
    extra: list[str] | None = None,
    content_id: str | None = None,
    location: str | None = None,
    creationdate: str | None = None,
    mtime: str = DEFAULT_MTIME,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    color = _hex_color(rel)
    args = [
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=640x480:d=2:r=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=2",
        "-c:v",
        vcodec,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        acodec,
        "-t",
        "2",
        "-shortest",
    ]
    if content_id or location or creationdate:
        args.extend(["-movflags", "use_metadata_tags"])
        if content_id:
            args.extend(
                ["-metadata", f"com.apple.quicktime.content.identifier={content_id}"]
            )
        if location:
            args.extend(
                ["-metadata", f"com.apple.quicktime.location.ISO6709={location}"]
            )
        if creationdate:
            args.extend(
                ["-metadata", f"com.apple.quicktime.creationdate={creationdate}"]
            )
            args.extend(["-metadata", f"creation_time={creationdate}"])
    if extra:
        args.extend(extra)
    args.append(str(dest))
    _ffmpeg(args)
    _pin_mtime(dest, mtime)


def _expected_photo(
    *,
    captured_at: str | None,
    captured_source: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
    orientation: int | None = 1,
    content_id: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": "photo",
        "width": 640,
        "height": 480,
        "orientation": orientation,
        "durationSec": None,
        "hasAudio": None,
        "capturedAt": captured_at,
        "capturedAtSource": captured_source,
        "latitude": latitude,
        "longitude": longitude,
        "contentIdentifier": content_id,
    }


def _expected_video(
    *,
    captured_at: str | None = None,
    captured_source: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    content_id: str | None = None,
    has_audio: bool = True,
) -> dict[str, Any]:
    return {
        "kind": "video",
        "width": 640,
        "height": 480,
        "orientation": None,
        "durationSec": 2.0,
        "hasAudio": has_audio,
        "capturedAt": captured_at,
        "capturedAtSource": captured_source,
        "latitude": latitude,
        "longitude": longitude,
        "contentIdentifier": content_id,
    }


def _record(
    rel: str,
    dest: Path,
    expected: dict[str, Any],
    recipe: str,
    mtime: str,
) -> dict[str, Any]:
    extraction = probe_file(dest)
    return {
        "path": rel.replace("\\", "/"),
        "sha256": extraction["sha256"],
        "sizeBytes": extraction["sizeBytes"],
        "mtime": mtime,
        "expectedMetadata": expected,
        "provenance": {
            "recipe": recipe,
            "verifiedBy": "tests.qa.probe",
            "extraction": extraction,
        },
    }


def generate(output: Path) -> dict[str, Any]:
    if not (80 < len(LONG_REL) < 240):
        raise RuntimeError("long fixture path length lock violated")
    media = output / "media"
    if media.exists():
        shutil.rmtree(media)
    media.mkdir(parents=True)

    files: list[dict[str, Any]] = []

    def still(rel: str, **kwargs: Any) -> None:
        expected = kwargs.pop("expected")
        recipe = kwargs.pop("recipe")
        mtime = kwargs.get("mtime", DEFAULT_MTIME)
        dest = media / Path(rel)
        _write_still(dest, rel, **kwargs)
        files.append(_record(rel, dest, expected, recipe, mtime))

    still(
        "a/IMG_1042.jpg",
        datetime_original="2024:06:12 15:04:00",
        latitude=41.880000,
        longitude=-87.630000,
        mtime="2022-01-01T00:00:00Z",
        expected=_expected_photo(
            captured_at="2024:06:12 15:04:00",
            captured_source="exif",
            latitude=41.880000,
            longitude=-87.630000,
        ),
        recipe="pillow-quadrant-jpeg-exif-gps",
    )
    still(
        "a/near.jpg",
        datetime_original="2024:06:12 15:05:00",
        latitude=41.880450,
        longitude=-87.630000,
        expected=_expected_photo(
            captured_at="2024:06:12 15:05:00",
            captured_source="exif",
            latitude=41.880450,
            longitude=-87.630000,
        ),
        recipe="pillow-quadrant-jpeg-exif-gps",
    )
    still(
        "b/far.jpg",
        datetime_original="2023:06:12 15:04:00",
        latitude=41.925000,
        longitude=-87.630000,
        expected=_expected_photo(
            captured_at="2023:06:12 15:04:00",
            captured_source="exif",
            latitude=41.925000,
            longitude=-87.630000,
        ),
        recipe="pillow-quadrant-jpeg-exif-gps",
    )
    still(
        "b/no-exif.jpg",
        orientation=None,
        mtime="2022-02-03T04:05:06Z",
        expected=_expected_photo(
            captured_at=None,
            captured_source=None,
            orientation=None,
        ),
        recipe="pillow-quadrant-jpeg-no-exif",
    )
    still(
        "b/created.jpg",
        orientation=1,
        datetime_digitized="2024:07:04 12:00:00",
        expected=_expected_photo(
            captured_at="2024:07:04 12:00:00",
            captured_source="exif",
        ),
        recipe="pillow-quadrant-jpeg-createdate-only",
    )
    still(
        "b/holiday_20200102.jpg",
        orientation=None,
        expected=_expected_photo(
            captured_at=None,
            captured_source=None,
            orientation=None,
        ),
        recipe="pillow-quadrant-jpeg-filename-date",
    )
    still(
        "b/holiday_2020-01-03.jpg",
        orientation=None,
        expected=_expected_photo(
            captured_at=None,
            captured_source=None,
            orientation=None,
        ),
        recipe="pillow-quadrant-jpeg-filename-date",
    )
    still(
        "b/oriented.jpg",
        orientation=6,
        datetime_original="2024:06:12 15:06:00",
        asymmetric=True,
        expected=_expected_photo(
            captured_at="2024:06:12 15:06:00",
            captured_source="exif",
            orientation=6,
        ),
        recipe="pillow-raw-640x480-exif-orientation-6",
    )
    still(
        "live/LIVE_0001.jpg",
        datetime_original="2024:06:13 10:00:00",
        content_id=LIVE_CONTENT_ID,
        expected=_expected_photo(
            captured_at="2024:06:13 10:00:00",
            captured_source="exif",
            content_id=LIVE_CONTENT_ID,
        ),
        recipe="pillow-jpeg-xmp-apple-content-identifier",
    )
    still(
        UNICODE_REL,
        expected=_expected_photo(captured_at=None, captured_source=None, orientation=1),
        recipe="pillow-quadrant-jpeg-unicode-path",
    )
    still(
        LONG_REL,
        expected=_expected_photo(captured_at=None, captured_source=None, orientation=1),
        recipe="pillow-quadrant-jpeg-nested-long-path",
    )

    clip = media / "a" / "clip.mp4"
    _write_video(
        clip,
        "a/clip.mp4",
        vcodec="libx264",
        acodec="aac",
        location=CLIP_LOCATION,
        creationdate="2024-06-12T15:07:00Z",
    )
    files.append(
        _record(
            "a/clip.mp4",
            clip,
            _expected_video(
                captured_at="2024-06-12T15:07:00Z",
                captured_source="exif",
                latitude=41.8800,
                longitude=-87.6300,
            ),
            "ffmpeg-h264-aac-qt-location-createdate",
            DEFAULT_MTIME,
        )
    )

    live_mov = media / "live" / "LIVE_0001.mov"
    _write_video(
        live_mov,
        "live/LIVE_0001.mov",
        vcodec="libx264",
        acodec="aac",
        extra=["-f", "mov"],
        content_id=LIVE_CONTENT_ID,
    )
    files.append(
        _record(
            "live/LIVE_0001.mov",
            live_mov,
            _expected_video(content_id=LIVE_CONTENT_ID),
            "ffmpeg-h264-aac-qt-content-identifier",
            DEFAULT_MTIME,
        )
    )

    raster = [
        ("formats/quad.png", "PNG", "pillow-png"),
        ("formats/quad.gif", "GIF", "pillow-gif"),
        ("formats/quad.webp", "WEBP", "pillow-webp"),
        ("formats/quad.tiff", "TIFF", "pillow-tiff"),
        ("formats/quad.bmp", "BMP", "pillow-bmp"),
    ]
    for rel, fmt, recipe in raster:
        dest = media / rel
        _write_still(dest, rel, fmt=fmt, orientation=None)
        files.append(
            _record(
                rel,
                dest,
                _expected_photo(captured_at=None, captured_source=None, orientation=None),
                recipe,
                DEFAULT_MTIME,
            )
        )

    for rel in ("formats/quad.heic", "formats/quad.heif"):
        dest = media / rel
        _write_heif(dest, rel)
        files.append(
            _record(
                rel,
                dest,
                _expected_photo(captured_at=None, captured_source=None, orientation=None),
                "pillow-heif-real-ftyp",
                DEFAULT_MTIME,
            )
        )

    videos = [
        ("formats/clip.mov", "libx264", "aac", ["-f", "mov"]),
        ("formats/clip.m4v", "libx264", "aac", ["-f", "mp4"]),
        ("formats/clip.mkv", "libx264", "aac", ["-f", "matroska"]),
        ("formats/clip.avi", "libx264", "pcm_s16le", ["-f", "avi"]),
        ("formats/clip.webm", "libvpx-vp9", "libopus", ["-f", "webm"]),
    ]
    for rel, vcodec, acodec, extra in videos:
        dest = media / rel
        _write_video(dest, rel, vcodec=vcodec, acodec=acodec, extra=extra)
        files.append(
            _record(
                rel,
                dest,
                _expected_video(),
                f"ffmpeg-{vcodec}-{acodec}",
                DEFAULT_MTIME,
            )
        )

    broken = media / "formats" / "broken.heic"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"not-a-heic-file\x00" * 32)
    _pin_mtime(broken, DEFAULT_MTIME)
    broken_probe = probe_file(broken)
    files.append(
        {
            "path": "formats/broken.heic",
            "sha256": broken_probe["sha256"],
            "sizeBytes": broken_probe["sizeBytes"],
            "mtime": DEFAULT_MTIME,
            "expectedMetadata": {
                "kind": None,
                "width": None,
                "height": None,
                "orientation": None,
                "durationSec": None,
                "hasAudio": None,
                "capturedAt": None,
                "capturedAtSource": None,
                "latitude": None,
                "longitude": None,
                "contentIdentifier": None,
            },
            "provenance": {
                "recipe": "invalid-bytes-not-an-image",
                "verifiedBy": "tests.qa.probe",
                "extraction": broken_probe,
            },
        }
    )

    hashes = [item["sha256"] for item in files if item["path"] != "formats/broken.heic"]
    if len(hashes) != len(set(hashes)):
        raise RuntimeError("fixture hashes are not distinct")

    live_still = next(item for item in files if item["path"] == "live/LIVE_0001.jpg")
    live_movie = next(item for item in files if item["path"] == "live/LIVE_0001.mov")
    still_id = live_still["expectedMetadata"]["contentIdentifier"]
    movie_id = live_movie["provenance"]["extraction"].get("contentIdentifier")
    if still_id != LIVE_CONTENT_ID or movie_id != LIVE_CONTENT_ID:
        raise RuntimeError(
            f"Live Photo identifiers not embedded: still={still_id} movie={movie_id}"
        )

    manifest = {
        "schemaVersion": 1,
        "files": files,
        "scenarios": _scenarios(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "duplicate",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Byte-copy IMG_1042 to second/source/same.jpg; one hash item, two locations, one search result. Seed different explicit place assignments in ordered history on pending/existing records; latest wins, exactly one primary remains, face/thing associations union.",
        },
        {
            "id": "collision",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Seed a different destination photo.jpg and photo_2.jpg; copying photo.jpg writes photo_3.jpg, both seeded hashes unchanged",
        },
        {
            "id": "modified",
            "inputs": ["a/IMG_1042.jpg", "a/near.jpg"],
            "expected": "Same source path gets different quadrant bytes and later mtime; new hash item, old annotations remain with old hash and historical current=false primary. Old item cannot serve new bytes; clipboard retains lastKnownPath.",
        },
        {
            "id": "unsafe/Unicode paths",
            "inputs": [UNICODE_REL, LONG_REL],
            "expected": "family/旅行 photo.jpg and a nested long filename; pending JSON remains flat, final id hashes correctly; path traversal requests rejected",
        },
        {
            "id": "interruption",
            "inputs": ["a/IMG_1042.jpg", "a/clip.mp4"],
            "expected": "Kill at copy temporary write, hash publication, catalog transaction and SQLite rebuild boundaries; restart then rescan; no duplicate items or lost annotation",
        },
        {
            "id": "pending annotation",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Seed a valid pending record with Ada/mug associations and matching history transaction before releasing the hash barrier; later repeat through real annotate in F14. Final item preserves association and history.",
        },
        {
            "id": "absent source",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Resolver maps test volume windows:fixture-offline to no mount, with a known cached preview. Never unplug a real drive.",
        },
        {
            "id": "moved library",
            "inputs": ["a/IMG_1042.jpg", "a/clip.mp4"],
            "expected": "Copy app+data sandbox to a new absolute directory/drive mapping, original root made inaccessible; relative originals still resolve",
        },
        {
            "id": "moved linked volume",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Test resolver remounts the same serial at a different letter; primary resolves there; a different serial at the old letter must not resolve",
        },
        {
            "id": "preview missing",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Remove only sandbox generated rendition; record survives, 404 preview-unavailable and stable placeholder",
        },
        {
            "id": "denied/relocate interrupted",
            "inputs": ["a/IMG_1042.jpg"],
            "expected": "Test filesystem denies write or interrupts copy of rendition; old reference/bytes survive, original checksums unchanged",
        },
        {
            "id": "HEIC failure",
            "inputs": ["formats/broken.heic", "a/IMG_1042.jpg"],
            "expected": "Invalid broken.heic plus valid JPEG in same scan; failed item/placeholder preserved, JPEG completes, scan error reported",
        },
        {
            "id": "format coverage",
            "inputs": [
                "formats/quad.png",
                "formats/quad.gif",
                "formats/quad.webp",
                "formats/quad.heic",
                "formats/quad.heif",
                "formats/quad.tiff",
                "formats/quad.bmp",
                "formats/clip.mov",
                "formats/clip.m4v",
                "formats/clip.avi",
                "formats/clip.mkv",
                "formats/clip.webm",
            ],
            "expected": "One valid PNG,GIF,WebP,HEIC,HEIF,TIFF,BMP and MOV,M4V,AVI,MKV,WEBM. Same quadrant/test-tone recipe, distinct hashes. GIF/TIFF use first frame/page. Browser-unsupported original must play proxy.",
        },
        {
            "id": "orphan/mismatch live",
            "inputs": ["live/LIVE_0001.jpg", "live/LIVE_0001.mov"],
            "expected": "Still alone, movie alone, then complete pair in opposite orders; different identifiers with same basename must stay separate",
        },
        {
            "id": "date edge",
            "inputs": [
                "b/holiday_20200102.jpg",
                "b/holiday_2020-01-03.jpg",
                "b/created.jpg",
                "b/no-exif.jpg",
            ],
            "expected": "Invalid date substring falls back to mtime; valid offset EXIF normalizes UTC; two equal timestamps tie by id; filename containing two valid dates uses leftmost",
        },
        {
            "id": "empty/no-GPS",
            "inputs": ["b/no-exif.jpg"],
            "expected": "Empty media directory and subset of no-exif only; empty grid/search/globe/tour without failures",
        },
        {
            "id": "settings/history",
            "inputs": [],
            "expected": "Port 8765 → 8770 → undo → redo, restart between steps; 501 changes caps 500; new edit clears redo; copy undo leaves every original byte",
        },
        {
            "id": "annotation",
            "inputs": ["a/IMG_1042.jpg", "a/near.jpg"],
            "expected": "Ada on first photo, mug on first+second; alias Cup → mug; second person id merged into Ada; rename place Kitchen; out-of-range boxes rejected",
        },
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent),
        help="Directory that will contain media/ and manifest.json",
    )
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    generate(output)
    print(f"wrote fixtures under {output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
