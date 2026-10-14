# Stack local AI — places + objects + faces on the People tip

Stacks PR #13 / #15 / #16 onto `cursor/reveal-spaces-hover-proxy-c876`.
Does not close a new Check. Combined Setup.bat is a follow-up.

## In scope

1. Offline GPS city names (`setup-geo` / `analyze-places`). Never overwrite
   a human place name.
2. Optional YOLO Things (`setup-ml objects` / `analyze`). Ignore COCO person.
3. Optional InsightFace unnamed clusters (`setup-ml faces` / `infer-faces`).
   Never guess a name.
4. Serve-time `drain_step` runs those workers when jobs are not paused and
   the pack/models are installed. Missing models: idle, no crash.
5. People panel shows real clusters after infer. Keep Unnamed / POI ≥3 /
   named-always / AND multi-select from the tip.

## Gates

`python -m tests.qa slice GEO`
`python -m tests.qa slice TASTE-OBJECTS`
`python -m tests.qa slice FACES`
`python -m tests.qa slice TASTE-PEOPLE`
