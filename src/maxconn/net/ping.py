from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True)
class PingResult:
    host: str
    reachable: bool
    elapsed: float
    returncode: int | None
    output: str
    error: str


def ping(host: str, *, timeout: float = 2.0, count: int = 1) -> PingResult:
    args = _ping_args(host, timeout=timeout, count=count)
    start = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout + 1.0,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # subprocess.run() was called with text=True, so stdout/stderr are
        # always str at runtime - see the matching comment in traceroute.py.
        return PingResult(
            host=host,
            reachable=False,
            elapsed=time.monotonic() - start,
            returncode=None,
            output=cast(str, exc.stdout or ""),
            error=cast(str, exc.stderr or "ping timed out"),
        )

    return PingResult(
        host=host,
        reachable=completed.returncode == 0,
        elapsed=time.monotonic() - start,
        returncode=completed.returncode,
        output=completed.stdout,
        error=completed.stderr,
    )


def _ping_args(host: str, *, timeout: float, count: int) -> list[str]:
    if platform.system().lower() == "windows":
        return ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), host]
    return ["ping", "-c", str(count), "-W", str(max(int(timeout), 1)), host]
