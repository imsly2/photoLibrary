# Taste-Rating — suggested stars, picks, and rejects

Sits on the Processing / Settings tip after #44 transcription. Does not
close a Check. No 23rd Check. No cloud API. Never auto-deletes or
auto-rejects. Export stays on hold.

Read PRODUCT F3 / F17 (`setup-ml aesthetic`, `rate-photos`, `rate`,
`ratingMode`), CONTRACTS quality + user rating, UI-SPEC filter chips +
Info stars, and this file.

## In scope

1. Settings **Rating** = Off / Basic / Smart. Default Basic.
   `ratingLearn` optionally nudges local suggestion weights.
2. Queue stage **Rating** after transcribe. Basic: Laplacian sharpness
   (normalized per resolution), exposure (histogram clip / mean /
   contrast), face quality from existing detections. Combine to a
   suggested 1–5 plus flags (blurry, too dark, too bright). Mark a
   suggested best-of-group on Live/burst stacks and duplicate groups.
3. Smart: local NIMA/MobileNet ONNX via onnxruntime (CPU, GPU if
   present). Downloaded by `setup-ml aesthetic` / Setup.bat. Blend
   with Basic. Fixture backend is for tests only.
4. User rating always wins: 1–5, P pick, X reject (hide only), 0
   clears. Stars on tiles and in Info (suggested vs yours).
5. Filter chips: 4 stars and up, Picks, Hide rejects, Blurry. Sort by
   rating. Rescan / re-rate skips already-scored size+mtime.

## Out of scope

Export, auto-delete, albums, cloud aesthetic APIs, a 23rd Check,
Win7 work.

## Gate

```
python -m tests.qa slice TASTE-RATING --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-rating/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
