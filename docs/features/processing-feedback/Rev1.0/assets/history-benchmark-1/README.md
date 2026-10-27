# Source history benchmark

Run `python benchmark.py` in this directory (or pass its absolute path). The
script writes only `results.json` beside itself. It never scans media or writes a
catalog. Python 3.12 was used for the recorded run.

`baseline-plan.py` freezes the original planner from the Git revision recorded
in `provenance.json`; `coalesced-plan.py` freezes the working implementation.
The benchmark executes those exact functions with an in-memory `load_entry`.
It uses the application's canonical JSON formatting, frozen in `benchmark.py`.

Each synthetic file adds a pending and an indexed source snapshot. The measured
call performs the final indexed update at 50, 100, and 200 files. The baseline
starts with all previous snapshots. The coalesced variant starts with a history
already coalesced by prior updates: this measures steady-state performance,
excluding one-time migration of a large existing entry. The fixture includes
source records only, so item snapshots and real disk costs are excluded.

Byte counts and elapsed times are measured; no extrapolated file counts appear
in `results.json`. Timing includes planning and a single serialization of the
transaction changes. It excludes loading files, synthetic fixture creation,
prepared/committed manifest writes, fsync, and the portable mirror. One sample
per size is descriptive evidence, not a performance threshold.

Assertions verify that rollback snapshots and actual transaction changes are
preserved, and that baseline/coalesced undo/redo endpoints are identical.
This is a throughput diagnostic, not a closing F5/F7 acceptance Check.
