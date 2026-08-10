from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceHop:
    hop: int
    address: str
    raw: str


@dataclass(frozen=True)
class TraceRouteResult:
    host: str
    hops: list[TraceHop]
    returncode: int | None
    output: str
    error: str


def traceroute(host: str, *, timeout: float = 30.0) -> TraceRouteResult:
    args = _traceroute_args(host)
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        error = exc.stderr or "traceroute timed out"
        return TraceRouteResult(
            host=host,
            hops=_parse_hops(output),
            returncode=None,
            output=output,
            error=error,
        )

    return TraceRouteResult(
        host=host,
        hops=_parse_hops(completed.stdout),
        returncode=completed.returncode,
        output=completed.stdout,
        error=completed.stderr,
    )


def _traceroute_args(host: str) -> list[str]:
    if platform.system().lower() == "windows":
        return ["tracert", "-d", host]
    return ["traceroute", "-n", host]


def _parse_hops(output: str) -> list[TraceHop]:
    hops: list[TraceHop] = []
    for line in output.splitlines():
        stripped = line.strip()
        match = re.match(r"^(\d+)\s+.*?([A-Za-z0-9_.:-]+)\s*$", stripped)
        if not match:
            continue
        hops.append(TraceHop(hop=int(match.group(1)), address=match.group(2), raw=stripped))
    return hops
