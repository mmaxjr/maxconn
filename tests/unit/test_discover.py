from __future__ import annotations

import importlib
import socket
import threading

import pytest

from maxconn.net import discover as run_discover
from maxconn.net.discover import (
    CONFIRM_THRESHOLD_HOSTS,
    DEFAULT_DISCOVER_PORTS,
    MAX_DISCOVER_HOSTS,
    DiscoverHost,
)


def test_default_discover_ports_include_http_and_https():
    assert 80 in DEFAULT_DISCOVER_PORTS
    assert 443 in DEFAULT_DISCOVER_PORTS


def test_discover_scans_each_host_in_network(monkeypatch):
    calls = []

    def fake_scan_host(host, *, ports, timeout, concurrency):
        calls.append((host, tuple(ports), timeout, concurrency))
        return DiscoverHost(host=host, open_ports=[80], scanned_ports=list(ports))

    discover_module = importlib.import_module("maxconn.net.discover")
    monkeypatch.setattr(discover_module, "_scan_host", fake_scan_host)

    results = run_discover(
        "192.0.2.0/30",
        ports=[80, 443],
        timeout=0.25,
        concurrency=2,
        workers=2,
    )

    assert [result.host for result in results] == ["192.0.2.1", "192.0.2.2"]
    assert calls == [
        ("192.0.2.1", (80, 443), 0.25, 2),
        ("192.0.2.2", (80, 443), 0.25, 2),
    ]


def test_discover_rejects_a_network_larger_than_the_host_limit():
    # A network this size (a /8, 16M+ addresses) must be rejected instantly
    # from the address count alone - materializing the full host list first
    # would hang/exhaust memory before a single scan even starts.
    assert 2**24 > MAX_DISCOVER_HOSTS  # sanity: /8 is actually bigger than the limit
    with pytest.raises(ValueError, match="exceeds"):
        run_discover("10.0.0.0/8")


def test_discover_requires_confirm_for_a_network_above_the_threshold(monkeypatch):
    discover_module = importlib.import_module("maxconn.net.discover")
    monkeypatch.setattr(
        discover_module,
        "_scan_host",
        lambda host, **kwargs: DiscoverHost(host=host, open_ports=[], scanned_ports=[]),
    )
    # A /20 (4094 usable hosts) is under the hard MAX_DISCOVER_HOSTS cap
    # but well above CONFIRM_THRESHOLD_HOSTS - it must require an explicit
    # opt-in rather than silently scanning thousands of hosts.
    assert 2**12 > CONFIRM_THRESHOLD_HOSTS

    with pytest.raises(ValueError, match="confirm"):
        run_discover("10.0.0.0/20", ports=[80])

    # confirm=True lets it proceed (mocked _scan_host keeps this fast).
    results = run_discover("10.0.0.0/20", ports=[80], confirm=True)
    assert len(results) > CONFIRM_THRESHOLD_HOSTS


def test_discover_grabs_a_banner_from_the_first_open_port():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve_forever():
        while True:
            try:
                conn, _addr = server.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.sendall(b"SSH-2.0-fake-device\r\n")
                except OSError:
                    pass

    threading.Thread(target=serve_forever, daemon=True).start()

    discover_module = importlib.import_module("maxconn.net.discover")
    host = discover_module._scan_host("127.0.0.1", ports=[port], timeout=1.0, concurrency=1)

    assert host.open_ports == [port]
    assert host.banner is not None
    assert "SSH-2.0-fake-device" in host.banner
    server.close()


def test_discover_banner_is_none_when_nothing_is_listening():
    discover_module = importlib.import_module("maxconn.net.discover")
    host = discover_module._scan_host("127.0.0.1", ports=[_unused_port()], timeout=0.2, concurrency=1)

    assert host.open_ports == []
    assert host.banner is None


def _unused_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_discover_caps_total_thread_count_across_both_pools(monkeypatch):
    # discover() spawns one ThreadPoolExecutor per host-scan level, and
    # scan() (called inside each host worker) spawns its own for ports -
    # workers * concurrency must stay bounded, or a large host count with a
    # high --concurrency can spawn thousands of live threads at once.
    discover_module = importlib.import_module("maxconn.net.discover")
    monkeypatch.setattr(
        discover_module,
        "_scan_host",
        lambda host, **kwargs: DiscoverHost(host=host, open_ports=[], scanned_ports=[]),
    )

    seen_max_workers = []
    real_executor_cls = discover_module.ThreadPoolExecutor

    class RecordingExecutor(real_executor_cls):
        def __init__(self, max_workers=None, *args, **kwargs):
            seen_max_workers.append(max_workers)
            super().__init__(max_workers, *args, **kwargs)

    monkeypatch.setattr(discover_module, "ThreadPoolExecutor", RecordingExecutor)

    run_discover("192.0.2.0/24", workers=64, concurrency=32)

    assert len(seen_max_workers) == 1
    (host_level_workers,) = seen_max_workers
    assert host_level_workers * 32 <= discover_module.MAX_TOTAL_SCAN_THREADS
