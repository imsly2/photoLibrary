# Paired stills evidence

This folder contains copies of the 11 JPEGs from `tests/fixtures/media`, the
two-process and paired outputs, `results.json`, and the one-off comparison
script `measure.py`. It does not read or modify a live library or original
photo. Caps were thumb 320 px and preview 1600 px. The fixture JPEGs are only
640×480 except the EXIF-oriented portrait, so this is a bounded local sample,
not the F7 family-PC performance check.

Across three runs over the same 11 copied inputs, median total time was
1.586 s for 22 separate `write_webp` FFmpeg processes and 0.951 s for 11
paired processes (1.67× faster, 0.636 s saved). Every corresponding output
had the same byte size and dimensions; the oriented portrait stayed
480×640 at preview size and 240×320 at thumb size. Per first item, median
thumb-only time was 64 ms; paired thumb+preview time was 90 ms, a 26 ms
tradeoff before that first thumb can publish. The paired path then makes the
viewer preview available at the same publication point.

Focused verification passed:

```powershell
& 'C:\Users\SLY2.0\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tests.qa.processing_feedback --artifacts docs/features/processing-feedback/Rev1.0/assets/paired-stills/qa
& 'C:\Users\SLY2.0\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' docs/features/processing-feedback/Rev1.0/assets/paired-stills/measure.py
```

The diagnostic exercises the existing rendition priority, scanning interleave,
single-preview fallback, annotation/removal revalidation, and video jobs. The
measurement script checks output byte sizes and dimensions item by item.
