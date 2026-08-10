from __future__ import annotations

import socket
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass(frozen=True)
class ScanResult:
    host: str
    port: int
    open: bool
    elapsed: float
    error: str


def scan(
    host: str,
    *,
    ports: Iterable[int],
    timeout: float = 1.0,
    concurrency: int = 100,
) -> list[ScanResult]:
    normalized_ports = [_validate_port(port) for port in ports]
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    worker_count = min(concurrency, len(normalized_ports)) or 1
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(
            executor.map(
                lambda port: _scan_port(host, port, timeout=timeout),
                normalized_ports,
            )
        )
    return sorted(results, key=lambda result: result.port)


def _scan_port(host: str, port: int, *, timeout: float) -> ScanResult:
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ScanResult(
                host=host,
                port=port,
                open=True,
                elapsed=time.monotonic() - start,
                error="",
            )
    except OSError as exc:
        return ScanResult(
            host=host,
            port=port,
            open=False,
            elapsed=time.monotonic() - start,
            error=str(exc),
        )


def _validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return port
