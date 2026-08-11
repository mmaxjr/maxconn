from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from maxconn.net.ping import ping
from maxconn.net.traceroute import traceroute


@dataclass(frozen=True)
class MTRResult:
    host: str
    sent: int
    received: int
    loss_percent: float
    best: float | None
    worst: float | None
    avg: float | None


@dataclass
class WinMTRHop:
    index: int
    host: str
    sent: int = 0
    received: int = 0
    times: list[float] | None = None

    def __post_init__(self) -> None:
        if self.times is None:
            self.times = []

    @property
    def loss_percent(self) -> float:
        if not self.sent:
            return 0.0
        return round(((self.sent - self.received) / self.sent) * 100, 2)

    @property
    def avg_ms(self) -> float | None:
        if not self.times:
            return None
        return round((sum(self.times) / len(self.times)) * 1000, 2)

    @property
    def best_ms(self) -> float | None:
        if not self.times:
            return None
        return round(min(self.times) * 1000, 2)

    @property
    def worst_ms(self) -> float | None:
        if not self.times:
            return None
        return round(max(self.times) * 1000, 2)

    @property
    def last_ms(self) -> float | None:
        if not self.times:
            return None
        return round(self.times[-1] * 1000, 2)


def mtr(host: str, *, count: int = 10, timeout: float = 1.0) -> MTRResult:
    if count < 1:
        raise ValueError("count must be at least 1")

    successful: list[float] = []
    for _ in range(count):
        result = ping(host, timeout=timeout, count=1)
        if result.returncode == 0:
            successful.append(result.elapsed)

    received = len(successful)
    loss_percent = round(((count - received) / count) * 100, 2)
    if not successful:
        return MTRResult(
            host=host,
            sent=count,
            received=0,
            loss_percent=loss_percent,
            best=None,
            worst=None,
            avg=None,
        )
    return MTRResult(
        host=host,
        sent=count,
        received=received,
        loss_percent=loss_percent,
        best=min(successful),
        worst=max(successful),
        avg=sum(successful) / received,
    )


def probe_mtr_once(
    host: str,
    hops: dict[int, WinMTRHop],
    *,
    timeout: float = 1.0,
    trace_timeout: float = 30.0,
) -> None:
    discover_mtr_hops(host, hops, trace_timeout=trace_timeout)
    probe_known_mtr_hops(hops, timeout=timeout)


def discover_mtr_hops(
    host: str,
    hops: dict[int, WinMTRHop],
    *,
    trace_timeout: float = 30.0,
) -> None:
    trace = traceroute(host, timeout=trace_timeout)
    targets = trace.hops or [type("_Hop", (), {"hop": 1, "address": host})()]
    if targets[-1].address != host:
        targets.append(type("_Hop", (), {"hop": targets[-1].hop + 1, "address": host})())

    for trace_hop in targets:
        current = hops.setdefault(
            trace_hop.hop,
            WinMTRHop(index=trace_hop.hop, host=trace_hop.address),
        )
        if current.host == "*" and trace_hop.address != "*":
            current.host = trace_hop.address


def probe_known_mtr_hops(hops: dict[int, WinMTRHop], *, timeout: float = 1.0) -> None:
    for index in sorted(hops):
        current = hops[index]
        current.sent += 1
        if current.host == "*":
            continue
        result = ping(current.host, timeout=timeout, count=1)
        if result.returncode == 0:
            current.received += 1
            assert current.times is not None
            current.times.append(result.elapsed)


def render_mtr_table(hops: dict[int, WinMTRHop]) -> str:
    lines = ["Hostname                         Nr  Loss%  Sent  Recv  Best  Avg   Worst  Last"]
    for index in sorted(hops):
        hop = hops[index]
        hostname = "No response from host" if hop.host == "*" else hop.host
        loss = f"{hop.loss_percent:.0f}%"
        best = _format_ms(hop.best_ms)
        avg = _format_ms(hop.avg_ms)
        worst = _format_ms(hop.worst_ms)
        last = _format_ms(hop.last_ms)
        lines.append(
            f"{hostname:<32} {hop.index:<3} {loss:<6} "
            f"{hop.sent:<5} {hop.received:<5} {best:<5} {avg:<5} {worst:<6} {last:<5}"
        )
    return "\n".join(lines)


def _format_ms(value: float | None) -> str:
    if value is None:
        return "0 ms"
    return f"{round(value)} ms"


def run_mtr_table(
    host: str,
    *,
    count: int | None = None,
    timeout: float = 1.0,
    trace_timeout: float = 30.0,
    rediscover_every: int | None = None,
    interval: float = 1.0,
) -> str:
    hops: dict[int, WinMTRHop] = {}
    discover_mtr_hops(host, hops, trace_timeout=trace_timeout)
    rounds = 0
    while count is None or rounds < count:
        if rediscover_every is not None and rounds > 0 and rounds % rediscover_every == 0:
            discover_mtr_hops(host, hops, trace_timeout=trace_timeout)
        probe_known_mtr_hops(hops, timeout=timeout)
        rounds += 1
        if count is None:
            print("\033[2J\033[H" + render_mtr_table(hops), flush=True)
            sleep(interval)
        elif rounds < count and interval > 0:
            sleep(interval)
    return render_mtr_table(hops)
