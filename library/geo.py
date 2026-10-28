"""Optional offline cities pack for GPS place names.

The pack lives in <library-root>/geo/ and is never shipped in git.
Nearest-city lookup is reverse_geocoder-class: GeoNames cities, no
cloud call at scan time.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from library.atomic import atomic_write_text, atomic_write_json, load_json
from library.errors import fail

CITIES_CSV = "cities.csv"
ATTRIBUTION = "ATTRIBUTION.txt"
MANIFEST = "manifest.json"

CITIES5000_URL = "https://download.geonames.org/export/dump/cities5000.zip"
ADMIN1_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
USER_AGENT = "photoLibrary-setup-geo/1.0"
DOWNLOAD_TIMEOUT = 120

GEONAMES_ATTRIBUTION = """GeoNames geographical database
https://www.geonames.org/
Licensed under Creative Commons Attribution 4.0
https://creativecommons.org/licenses/by/4.0/

This folder is an optional local reverse-geocode pack. Library does not
call a cloud geocoder while scanning or browsing.
"""

_cache: dict[str, tuple[Path, list[tuple[float, float, str]]]] = {}
_grid_cache: dict[str, tuple[tuple[str, int, int], dict[tuple[int, int], list[tuple[float, float, str]]]]] = {}
_CELL_DEG = 1.0


def geo_dir(root: Path) -> Path:
    return Path(root) / "geo"


def cities_path(root: Path) -> Path:
    return geo_dir(root) / CITIES_CSV


def pack_ready(root: Path) -> bool:
    path = cities_path(root)
    return path.is_file() and path.stat().st_size > 0


def format_place_name(name: str, admin1: str = "", cc: str = "") -> str | None:
    city = (name or "").strip()
    if not city:
        return None
    region = (admin1 or "").strip()
    if region and region.casefold() != city.casefold():
        return f"{city}, {region}"
    return city


def _cities_stamp(path: Path) -> tuple[str, int, int]:
    if not path.is_file():
        return (str(path), 0, 0)
    stat = path.stat()
    return (str(path.resolve()), int(stat.st_mtime_ns), int(stat.st_size))


def _load_cities(root: Path) -> list[tuple[float, float, str]]:
    path = cities_path(root)
    stamp = _cities_stamp(path)
    cached = _cache.get("cities")
    if cached is not None and cached[0] == stamp:
        return cached[1]
    if not pack_ready(root):
        _cache["cities"] = (stamp, [])
        return []
    rows: list[tuple[float, float, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            label = format_place_name(
                row.get("name") or "",
                row.get("admin1") or "",
                row.get("cc") or "",
            )
            if label is None:
                continue
            rows.append((lat, lon, label))
    _cache["cities"] = (stamp, rows)
    return rows


def _lat_cell(lat: float) -> int:
    return max(-90, min(89, math.floor(lat / _CELL_DEG)))


def _lon_cell(lon: float) -> int:
    cell = math.floor(lon / _CELL_DEG)
    if cell >= 180:
        cell -= 360
    if cell < -180:
        cell += 360
    return cell


def _city_grid(root: Path) -> dict[tuple[int, int], list[tuple[float, float, str]]]:
    """Cities grouped by 1-degree cell. The nearest city is in a nearby cell."""
    path = cities_path(root)
    stamp = _cities_stamp(path)
    cached = _grid_cache.get("grid")
    if cached is not None and cached[0] == stamp:
        return cached[1]
    buckets: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    for lat, lon, label in _load_cities(root):
        buckets.setdefault((_lat_cell(lat), _lon_cell(lon)), []).append((lat, lon, label))
    _grid_cache["grid"] = (stamp, buckets)
    return buckets


def _outside_square_meters(lat: float, lon: float, qi: int, qj: int, radius: int) -> float:
    """A lower bound on the distance from this point to any city outside the searched square.

    Underestimated on purpose: a short bound searches one more ring, a long one could
    pick the wrong city.
    """
    if qj - radius < -180 or qj + radius + 1 > 180:
        return 0.0
    lat_span = min(lat - (qi - radius), (qi + radius + 1) - lat)
    lon_span = min(lon - (qj - radius), (qj + radius + 1) - lon)
    lat_m = 110000.0
    lon_m = max(1.0, 111000.0 * math.cos(math.radians(lat)))
    return min(lat_span * lat_m, lon_span * lon_m)


def lookup_name(root: Path, latitude: float, longitude: float) -> str | None:
    from library.places import haversine_meters

    buckets = _city_grid(root)
    if not buckets:
        return None
    qi, qj = _lat_cell(latitude), _lon_cell(longitude)
    best_name: str | None = None
    best_dist = float("inf")
    for radius in range(181):
        cells: list[tuple[int, int]] = []
        if radius == 0:
            cells.append((qi, qj))
        else:
            for di in range(-radius, radius + 1):
                cells.append((qi + di, _lon_cell((qj - radius) * _CELL_DEG)))
                cells.append((qi + di, _lon_cell((qj + radius) * _CELL_DEG)))
            for dj in range(-radius + 1, radius):
                cells.append((qi - radius, _lon_cell((qj + dj) * _CELL_DEG)))
                cells.append((qi + radius, _lon_cell((qj + dj) * _CELL_DEG)))
        for cell in cells:
            for lat, lon, label in buckets.get(cell, ()):
                dist = haversine_meters(latitude, longitude, lat, lon)
                if dist < best_dist:
                    best_dist = dist
                    best_name = label
        if best_name is not None and best_dist <= _outside_square_meters(latitude, longitude, qi, qj, radius):
            return best_name
    return best_name


def city_count(root: Path) -> int:
    return len(_load_cities(root))


def _invalidate() -> None:
    _cache.pop("cities", None)
    _grid_cache.pop("grid", None)


def install_pack(root: Path, source: Path) -> dict[str, Any]:
    source = Path(source)
    if not source.exists():
        raise fail("invalid-argument")
    if source.is_file() and source.name.lower() == CITIES_CSV:
        return _install_csv(root, source, source_label="local")
    if source.is_dir():
        csv_file = source / CITIES_CSV
        if csv_file.is_file():
            return _install_csv(root, csv_file, source_label="local")
        zip_file = source / "cities5000.zip"
        txt_file = source / "cities5000.txt"
        admin = source / "admin1CodesASCII.txt"
        if zip_file.is_file() or txt_file.is_file():
            return _install_geonames(root, zip_file if zip_file.is_file() else txt_file, admin if admin.is_file() else None)
        raise fail("invalid-argument")
    if source.suffix.lower() == ".zip" or source.name.lower() == "cities5000.txt":
        return _install_geonames(root, source, None)
    raise fail("invalid-argument")


def _install_csv(root: Path, csv_file: Path, *, source_label: str) -> dict[str, Any]:
    text = csv_file.read_text(encoding="utf-8")
    _write_pack(root, text, source_label=source_label, downloaded=False)
    attribution = csv_file.parent / ATTRIBUTION
    dest_attr = geo_dir(root) / ATTRIBUTION
    if attribution.is_file() and not dest_attr.exists():
        atomic_write_text(dest_attr, attribution.read_text(encoding="utf-8"))
    return _ready_payload(root, downloaded=False, source=source_label)


def _install_geonames(root: Path, cities_file: Path, admin_file: Path | None) -> dict[str, Any]:
    cities_txt = _read_cities_table(cities_file)
    admin_map = _read_admin1(admin_file.read_text(encoding="utf-8") if admin_file and admin_file.is_file() else "")
    csv_text = convert_geonames(cities_txt, admin_map)
    _write_pack(root, csv_text, source_label="geonames-cities5000", downloaded=False)
    atomic_write_text(geo_dir(root) / ATTRIBUTION, GEONAMES_ATTRIBUTION)
    return _ready_payload(root, downloaded=False, source="geonames-cities5000")


def convert_geonames(cities_txt: str, admin_map: dict[str, str]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["latitude", "longitude", "name", "admin1", "cc"])
    for raw in cities_txt.splitlines():
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 11:
            continue
        try:
            lat = float(parts[4])
            lon = float(parts[5])
        except ValueError:
            continue
        name = parts[1].strip() or parts[2].strip()
        cc = parts[8].strip()
        admin_code = parts[10].strip()
        admin1 = admin_map.get(f"{cc}.{admin_code}", admin_code)
        if not name:
            continue
        writer.writerow([f"{lat:.5f}", f"{lon:.5f}", name, admin1, cc])
    return out.getvalue()


def _read_admin1(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        mapping[parts[0].strip()] = parts[1].strip()
    return mapping


def _read_cities_table(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise fail("io-error")
            with zf.open(names[0]) as handle:
                return handle.read().decode("utf-8")
    return path.read_text(encoding="utf-8")


def _write_pack(root: Path, csv_text: str, *, source_label: str, downloaded: bool) -> None:
    folder = geo_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    atomic_write_text(folder / CITIES_CSV, csv_text)
    atomic_write_json(
        folder / MANIFEST,
        {
            "schemaVersion": 1,
            "source": source_label,
            "downloaded": downloaded,
            "file": CITIES_CSV,
        },
    )
    _invalidate()


def _ready_payload(root: Path, *, downloaded: bool, source: str) -> dict[str, Any]:
    return {
        "ok": True,
        "path": f"geo/{CITIES_CSV}",
        "cityCount": city_count(root),
        "downloaded": downloaded,
        "source": source,
    }


def _http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT) as resp:
            return resp.read()
    except (URLError, TimeoutError, OSError) as exc:
        raise fail("io-error") from exc


def setup_geo(
    root: Path,
    *,
    source: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if source:
        if pack_ready(root) and not force:
            return _ready_payload(root, downloaded=False, source="existing")
        return install_pack(root, Path(source))
    if pack_ready(root) and not force:
        source_label = "existing"
        manifest = geo_dir(root) / MANIFEST
        if manifest.is_file():
            try:
                data = load_json(manifest)
                if isinstance(data, dict) and type(data.get("source")) is str:
                    source_label = data["source"]
            except (OSError, ValueError):
                pass
        return _ready_payload(root, downloaded=False, source=source_label)

    cache = geo_dir(root) / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    zip_path = cache / "cities5000.zip"
    admin_path = cache / "admin1CodesASCII.txt"
    try:
        zip_path.write_bytes(_http_get(CITIES5000_URL))
        admin_path.write_bytes(_http_get(ADMIN1_URL))
    except Exception:
        if zip_path.exists():
            zip_path.unlink()
        raise
    cities_txt = _read_cities_table(zip_path)
    admin_map = _read_admin1(admin_path.read_text(encoding="utf-8"))
    csv_text = convert_geonames(cities_txt, admin_map)
    _write_pack(root, csv_text, source_label="geonames-cities5000", downloaded=True)
    atomic_write_text(geo_dir(root) / ATTRIBUTION, GEONAMES_ATTRIBUTION)
    return _ready_payload(root, downloaded=True, source="geonames-cities5000")
