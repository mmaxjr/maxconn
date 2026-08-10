from __future__ import annotations

from dataclasses import dataclass

from maxconn.net.ping import ping


@dataclass(frozen=True)
class MTRResult:
    host: str
    sent: int
    received: int
    loss_percent: float
    best: float | None
    worst: float | None
    avg: float | None


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
