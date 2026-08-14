"""Cross-platform, zero-dependency exclusive file locking for maxconn's
local JSON/JSONL stores (hosts.json, seen_hosts.json, history.jsonl).

Protects the read-modify-write sequence in HostStore/HistoryStore mutating
methods against concurrent maxconn processes racing on the same file - a
lost update or, in the worst case, a torn write, if two processes read the
same snapshot and each write back their own version.

Advisory locking via a sidecar `<path>.lock` file: cooperative between
maxconn processes, not enforced against arbitrary external writers.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def locked(path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.parent / f"{path.name}.lock"
        with open(lock_path, "a+b") as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    @contextmanager
    def locked(path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.parent / f"{path.name}.lock"
        with open(lock_path, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
