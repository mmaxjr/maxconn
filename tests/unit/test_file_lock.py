from __future__ import annotations

import threading
import time

from maxconn._file_lock import locked


def test_locked_serializes_concurrent_critical_sections(tmp_path):
    target = tmp_path / "shared.json"
    counter = {"value": 0}

    def bump():
        with locked(target):
            current = counter["value"]
            time.sleep(0.01)  # widen the race window so a missing lock is caught reliably
            counter["value"] = current + 1

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert counter["value"] == 4


def test_locked_creates_the_parent_directory(tmp_path):
    target = tmp_path / "nested" / "shared.json"

    with locked(target):
        pass

    assert target.parent.exists()
