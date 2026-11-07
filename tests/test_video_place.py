"""Video location strings and folder-library place roots."""

from pathlib import Path

from library.catalog_io import library_root_of_record
from library.metadata import parse_iso6709


def test_iso6709_allows_a_missing_altitude():
    lat, lon = parse_iso6709("+33.5558-117.7591/")
    assert round(lat, 4) == 33.5558
    assert round(lon, 4) == -117.7591


def test_iso6709_keeps_an_altitude_string():
    lat, lon = parse_iso6709("+33.555836-117.759133+010.000/")
    assert round(lat, 4) == 33.5558
    assert round(lon, 4) == -117.7591


def test_library_root_of_record_is_the_library_folder():
    record = Path(r"K:\Photos\roll\.library\202610_a\IMG_3690.MOV.json")
    assert library_root_of_record(record) == Path(r"K:\Photos\roll\.library")
    assert library_root_of_record(Path(r"J:\library-data\catalog\items\abc.json")) is None
