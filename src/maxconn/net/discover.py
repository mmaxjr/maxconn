from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from maxconn.net.scan import scan

DEFAULT_DISCOVER_PORTS = (22, 23, 80, 443, 161, 8291, 8080, 8443)
# Prevents materializing (and scanning) an implausibly large host list from
# one CLI invocation - a /8 or any IPv6 CIDR would otherwise try to build a
# list with millions/quintillions of entries before scanning a single host.
MAX_DISCOVER_HOSTS = 65536
# Above this host count, discover() requires an explicit confirm=True - a
# large block scan can take a long time and hit a lot of unrelated hosts,
# so it shouldn't happen as a side effect of a typo in a CIDR mask.
CONFIRM_THRESHOLD_HOSTS = 1024
# discover() spawns one ThreadPoolExecutor for host-level parallelism
# (`workers`), and each worker's scan() call spawns its own for port-level
# parallelism (`concurrency`) - without a shared ceiling, worst case is
# `workers * concurrency` live threads at once (2048 at the historical
# defaults of workers=64, concurrency=32).
MAX_TOTAL_SCAN_THREADS = 256
BANNER_READ_SIZE = 128


@dataclass(frozen=True)
class DiscoverHost:
    host: str
    open_ports: list[int]
    scanned_ports: list[int]
    banner: str | None = None

    @property
    def reachable(self) -> bool:
        return bool(self.open_ports)


def discover(
    network: str,
    *,
    ports: Iterable[int] | None = None,
    timeout: float = 1.0,
    concurrency: int = 32,
    workers: int = 64,
    confirm: bool = False,
) -> list[DiscoverHost]:
    net = ipaddress.ip_network(network, strict=False)
    if net.num_addresses > MAX_DISCOVER_HOSTS:
        raise ValueError(
            f"network {network} has {net.num_addresses} addresses, which exceeds the "
            f"{MAX_DISCOVER_HOSTS}-host discover() limit; scan a smaller CIDR block"
        )
    if net.num_addresses > CONFIRM_THRESHOLD_HOSTS and not confirm:
        raise ValueError(
            f"network {network} has {net.num_addresses} addresses, which exceeds the "
            f"{CONFIRM_THRESHOLD_HOSTS}-host confirmation threshold; pass confirm=True "
            "(or --confirm on the CLI) to scan it anyway"
        )
    hosts = [str(host) for host in net.hosts()]
    resolved_ports = list(ports) if ports is not None else list(DEFAULT_DISCOVER_PORTS)
    if workers < 1:
        raise ValueError("workers must be at least 1")

    worker_count = min(workers, len(hosts)) or 1
    worker_count = min(worker_count, max(1, MAX_TOTAL_SCAN_THREADS // max(1, concurrency)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(
            executor.map(
                lambda host: _scan_host(
                    host,
                    ports=resolved_ports,
                    timeout=timeout,
                    concurrency=concurrency,
                ),
                hosts,
            )
        )
    return results


def _scan_host(
    host: str,
    *,
    ports: Iterable[int],
    timeout: float,
    concurrency: int,
) -> DiscoverHost:
    scanned = scan(host, ports=ports, timeout=timeout, concurrency=concurrency)
    scanned_ports = [result.port for result in scanned]
    open_ports = [result.port for result in scanned if result.open]
    banner = _grab_banner(host, open_ports[0], timeout) if open_ports else None
    return DiscoverHost(host=host, open_ports=open_ports, scanned_ports=scanned_ports, banner=banner)


def _grab_banner(host: str, port: int, timeout: float) -> str | None:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            data = sock.recv(BANNER_READ_SIZE)
    except OSError:
        return None
    if not data:
        return None
    return data.decode(errors="replace").strip() or None
