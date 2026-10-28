"""Read-only local profiling. Blocks filesystem mutations while examining live data.

Usage: python -m tests.perf.profile_reads output.json
No server lock is shared: this is phase attribution, not live request latency.
"""
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
import time

from library.service import Library
from library.settings import load_settings_file
from library import item_index


def main():
    root = Path('library-data').resolve()
    guarded = True

    def audit(event, args):
        if not guarded:
            return
        if event == 'open':
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                raise RuntimeError('profile prohibits writes')
        if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.truncate', 'subprocess.Popen'}:
            raise RuntimeError('profile prohibits mutation/processes')

    sys.addaudithook(audit)
    lib = Library.__new__(Library)
    lib.root, lib._scanning, lib._jobs_paused = root, False, False
    result = {'note': 'Separate process, concurrent live writers; read-only filesystem guard. No live lock wait measured.', 'phases': []}

    def phase(name, fn):
        profile = cProfile.Profile()
        start = time.perf_counter()
        error = None
        value = None
        try:
            value = profile.runcall(fn)
        except Exception as exc:
            error = type(exc).__name__ + ': ' + str(exc)
        stats = pstats.Stats(profile)
        rows = sorted(stats.stats.items(), key=lambda pair: pair[1][3], reverse=True)[:25]
        result['phases'].append({'name': name, 'ms': (time.perf_counter()-start)*1000, 'error': error,
            'functions': [{'file': Path(k[0]).name, 'line': k[1], 'function': k[2], 'calls': v[1], 'selfMs': v[2]*1000, 'totalMs': v[3]*1000} for k,v in rows]})
        print(name, round(result['phases'][-1]['ms']), error, flush=True)
        return value

    phase('recover', lib.recover)
    # ensure_settings may write missing defaults; use the read-only loader.
    lib.ensure_settings = lambda: load_settings_file(root)
    lib.recover = lambda: None
    snap = phase('snapshot-without-recovery', lib.snapshot_catalog)
    result['items'] = len(snap['items'])
    from collections import Counter
    counts = Counter(f['personId'] for item in snap['items'] for f in item.get('faces') or [] if f.get('personId'))
    person = counts.most_common(1)[0][0]
    for n in range(2):
        for label, query in [('all', {}), ('person', {'person': person}), ('person-name', {'person':person, 'sort':'name'})]:
            rows = phase(f'{label}-prepare-{n}', lambda: lib.items_iter_from_snapshot(snap, query))
            phase(f'{label}-first-{n}', lambda: next(rows, None))
    ids = [item['id'] for item in snap['items'] if (item.get('renditions') or {}).get('status', {}).get('thumb') == 'ready'][:128]
    phase('128-ready-thumb-resolve-and-read', lambda: [lib.media_resolve(i, {'which':'thumb'})['path'].read_bytes() for i in ids])
    from library.faces import load_index, cluster_detections
    index = phase('face-index-read', lambda: load_index(root))
    phase('face-empty-cluster', lambda: cluster_detections(root, [], index))
    centroid = next(row['centroid'] for row in index['people'].values() if row.get('centroid'))
    phase('face-one-existing-cluster', lambda: cluster_detections(root,
        [{'itemId':'profile-only', 'box':[0.1,0.1,0.2,0.2], 'embedding':centroid}], index))
    guarded = False
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
