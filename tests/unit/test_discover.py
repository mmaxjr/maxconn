from __future__ import annotations

import importlib

from maxconn.net import discover as run_discover
from maxconn.net.discover import DEFAULT_DISCOVER_PORTS, DiscoverHost


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
