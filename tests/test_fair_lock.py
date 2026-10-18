from __future__ import annotations

import threading
import time
import unittest

from library.lock import FairLock


class FairLockTest(unittest.TestCase):
    def test_waiters_get_the_lock_in_arrival_order(self) -> None:
        lock = FairLock()
        order: list[str] = []
        lock.acquire()

        def waiter(name: str) -> None:
            with lock:
                order.append(name)

        threads = []
        for name in ("reader", "encoder-1", "encoder-2"):
            thread = threading.Thread(target=waiter, args=(name,))
            thread.start()
            threads.append(thread)
            time.sleep(0.05)
        lock.release()
        lock.acquire()  # the releasing thread queues behind everyone already waiting
        order.append("releaser")
        lock.release()
        for thread in threads:
            thread.join(2)
        self.assertEqual(order, ["reader", "encoder-1", "encoder-2", "releaser"])

    def test_background_threads_wait_behind_foreground_ones(self) -> None:
        lock = FairLock()
        order: list[str] = []
        lock.acquire()

        def waiter(name: str, background: bool) -> None:
            if background:
                FairLock.mark_background()
            with lock:
                order.append(name)

        threads = []
        for name, background in (("encoder", True), ("scan", False), ("reader", False)):
            thread = threading.Thread(target=waiter, args=(name, background))
            thread.start()
            threads.append(thread)
            time.sleep(0.05)
        lock.release()
        for thread in threads:
            thread.join(2)
        self.assertEqual(order, ["scan", "reader", "encoder"])


if __name__ == "__main__":
    unittest.main()
