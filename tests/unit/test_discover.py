from __future__ import annotations

import importlib

import pytest

from maxconn.net import discover as run_discover
from maxconn.net.discover import DEFAULT_DISCOVER_PORTS, MAX_DISCOVER_HOSTS, DiscoverHost


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
