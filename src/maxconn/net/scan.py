from __future__ import annotations

import socket
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeoutError
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

    try:
        connect_host = _resolve(host, timeout)
    except (OSError, TimeoutError) as exc:
        return [
            ScanResult(host=host, port=port, open=False, elapsed=0.0, error=str(exc)) for port in normalized_ports
        ]

    worker_count = min(concurrency, len(normalized_ports)) or 1
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(
            executor.map(
                lambda port: _scan_port(host, connect_host, port, timeout=timeout),
                normalized_ports,
            )
        )
    return sorted(results, key=lambda result: result.port)


def _resolve(host: str, timeout: float) -> str:
    """Resolve host to an IP with a hard timeout.

    socket.create_connection()'s own timeout only covers the TCP connect
    step - the getaddrinfo() lookup it does internally for a hostname has
    no timeout of its own, so a hung/slow resolver could otherwise block
    far longer than the caller's timeout. Resolving once up front (instead
    of once per port) also avoids redundant concurrent DNS lookups for the
    same hostname.
    """
    # Not using `with ThreadPoolExecutor() as executor:` on purpose: its
    # __exit__ calls shutdown(wait=True), which would block until the
    # abandoned lookup thread finishes - defeating the timeout entirely
    # when the resolver is genuinely hung rather than just slow.
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    try:
        results = future.result(timeout=timeout)
    except _FutureTimeoutError as exc:
        executor.shutdown(wait=False)
        raise TimeoutError(f"DNS resolution for {host!r} timed out after {timeout}s") from exc
    executor.shutdown(wait=False)
    return results[0][4][0]


def _scan_port(display_host: str, connect_host: str, port: int, *, timeout: float) -> ScanResult:
    start = time.monotonic()
    try:
        with socket.create_connection((connect_host, port), timeout=timeout):
            return ScanResult(
                host=display_host,
                port=port,
                open=True,
                elapsed=time.monotonic() - start,
                error="",
            )
    except OSError as exc:
        return ScanResult(
            host=display_host,
            port=port,
            open=False,
            elapsed=time.monotonic() - start,
            error=str(exc),
        )


def _validate_port(port: int) -> int:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return port
