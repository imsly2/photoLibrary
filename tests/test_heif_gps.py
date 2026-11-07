"""HEIC GPS lives in an Exif item, which ffprobe tags do not show."""

from __future__ import annotations

from library.metadata import _apply_tiff_fields, _heif_tiff
from library.records import empty_metadata

# piexif dump of Make=Apple and a GPS fix near 33.56 N, 117.76 W.
EXIF = bytes.fromhex(
    "4578696600004d4d002a000000080002010f000200000006000000268825000400000001"
    "0000002c000000004170706c6500000400010002000000024e0000000002000500000003"
    "0000005e0003000200000002570000000004000500000003000000760000002100000001"
    "0000002100000001000008340000006400000075000000010000002d0000000100000ce4"
    "00000064"
)


def test_heif_tiff_skips_a_false_exif_marker():
    blob = b"xxxxExif\x00\x00NOPE" + EXIF
    tiff = _heif_tiff(blob)
    assert tiff is not None
    assert tiff.startswith(b"MM\x00*")
    meta = empty_metadata()
    _apply_tiff_fields(meta, tiff)
    assert meta["latitude"] is not None and abs(meta["latitude"] - 33.558) < 0.01
    assert meta["longitude"] is not None and meta["longitude"] < 0
    assert meta["camera"] == "Apple"
