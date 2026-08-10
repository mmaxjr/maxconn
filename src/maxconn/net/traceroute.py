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
        return ["tracert", "-d", "-w", "1000", host]
    return ["traceroute", "-n", host]


def _parse_hops(output: str) -> list[TraceHop]:
    hops: list[TraceHop] = []
    for line in output.splitlines():
        stripped = line.strip()
        hop_match = re.match(r"^(\d+)\s+(.*)$", stripped)
        if not hop_match:
            continue
        hop = int(hop_match.group(1))
        rest = hop_match.group(2)
        if rest.count("*") >= 3:
            hops.append(TraceHop(hop=hop, address="*", raw=stripped))
            continue
        match = _IP_OR_HOST_RE.findall(rest)
        if not match:
            continue
        hops.append(TraceHop(hop=hop, address=match[-1], raw=stripped))
    return hops


_IP_OR_HOST_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9_.:-]*[A-Za-z0-9]")
