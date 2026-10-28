"""Opt-in diagnostic launcher: same server/workers with bounded anonymous timings.

python -m tests.perf.serve_profile ROOT OUTPUT.json
Output stores only function labels, durations, and counters, never paths or items.
"""
from collections import defaultdict, deque
import functools
import json
from pathlib import Path
import sys
import threading
import time

from library import faces, item_index, server, service


def main():
    output = Path(sys.argv[2]).resolve()
    guard = threading.Lock()
    samples = defaultdict(lambda: deque(maxlen=256))
    counts = defaultdict(int)

    def wrap(owner, name, label):
        real = getattr(owner, name)
        @functools.wraps(real)
        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return real(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                with guard:
                    samples[label].append(round(elapsed, 3))
                    counts[label] += 1
        setattr(owner, name, timed)

    for name in ('load_index', 'write_index', 'cluster_detections', 'detect_faces_on_still',
                 'detect_insightface', 'decode_still_rgb', 'infer_faces', 'infer_faces_step'):
        wrap(faces, name, 'faces.' + name)
    for name in ('snapshot_catalog', 'items_iter_from_snapshot', 'media_resolve', 'recover'):
        wrap(service.Library, name, 'catalog.' + name)
    wrap(item_index, 'resync', 'catalog.resync')
    wrap(server.LibraryHandler, '_items_stream', 'http.stream-total')
    wrap(server.LibraryHandler, '_send_media', 'http.media-total')

    def save():
        while True:
            time.sleep(2)
            with guard:
                body = {'timestamp': time.time(), 'samplesMs': {k: list(v) for k,v in samples.items()}, 'counts':dict(counts)}
            try:
                output.write_text(json.dumps(body, indent=2), encoding='utf-8')
            except OSError:
                pass
    threading.Thread(target=save, daemon=True).start()
    server.serve(Path(sys.argv[1]).resolve())


if __name__ == '__main__':
    main()
