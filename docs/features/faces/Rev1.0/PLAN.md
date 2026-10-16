# FACES — Optional local face inference

Locked 2026-10-14 on `cursor/grid-density-date-6efb`. **Extends F14. No 23rd Check.**
YOLO / object inference is a parallel track and is out of scope.

Read PRODUCT optional local face inference, F14, CONTRACTS faces routes /
`faces-infer` history / `models-missing`, UI-SPEC unnamed Info naming,
FIXTURES `face-cluster`, and this file. Face quality lives in
`faceMatchThreshold` (default 0.80, Settings slider) / `faceMinSidePx`.
Detect stays full-frame 640 → map boxes → original 112 crop. Large stills
add overlapping 1280 tiles, NMS-merged, then the same 112 embed. Do not
guess real names. Do not upload faces. Do not align-before-detect.

## In scope

- `setup-ml faces` / `POST /api/faces/setup` installs InsightFace buffalo_s
  ONNX under `library-data/models/faces/`. Windows-friendly CPU
  (`onnxruntime`). Gender/age models are not loaded and are removed after
  install.
- `LIBRARY_TEST=1` + `backend=fixture` installs a deterministic local
  detector for synthetic beacon/identity stills. Production ignores fixture.
- `infer-faces` / `POST /api/faces/infer` detects faces, embeds, clusters
  unnamed people (`name: null`), reuses the people catalog only when
  cosine is strictly above `faceMatchThreshold` (InsightFace **0.80**;
  fixture 0.85), writes boxes plus optional det/match scores, stores
  embeddings in `models/faces/index.json`. Tiny faces below
  `faceMinSidePx` (default 80) are dropped. Weak/small boxes need a
  higher score before they join an already-named person.
- After Update on an existing catalog: `python -m library infer-faces --force`
  or Processing **Re-run Faces**. That re-detects with the new gates and
  rebuilds centroids. Named people are kept. `--cleanup` drops stored
  faces that fail min-size / stored scores without a model pass.
- `GET /api/faces` reports ready/backend.
- Info lists Unnamed; select + Person field names via existing annotate
  `{id,name}`. Search is existing `person=` / `q=`. `people merge` merges
  embeddings too.
- `python -m tests.qa slice FACES` on fixture-owned roots.

## Out of scope

YOLO / things inference, auto real-name guess, cloud upload, a merge
wizard, F23. Align-before-detect is impossible without a box and stays
out. Face-quality keys are Settings page controls (slider + min side)
plus settings.json.

## Gate

```powershell
python -m tests.qa slice FACES --root "$qaRoot/library-data" --artifacts $evidence
```

The gate must:

1. Install fixture models; `GET /api/faces` ready.
2. Infer two unnamed people; same person on two photos; both-faces photo
   uses both ids; no-face photo has none; boxes in range; names null.
3. Name one person Ada via `{id,name}`; `?person=Ada` and `?q=Ada` hit
   that person's items only.
4. Merge the other cluster into Ada; drop file gone; embeddings merged.
5. Infer without models → `models-missing`.
6. Original hashes unchanged. Exit 0 only when every proof ran.
