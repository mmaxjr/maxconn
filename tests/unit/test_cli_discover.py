from __future__ import annotations

import json

import maxconn.cli
from maxconn.net.discover import DiscoverHost


def test_cli_discover_uses_default_ports_and_prints_table(monkeypatch, capsys):
    calls = []

    def fake_discover(network, *, ports, timeout, concurrency, workers):
        calls.append((network, ports, timeout, concurrency, workers))
        return [DiscoverHost(host="192.0.2.10", open_ports=[80, 443], scanned_ports=ports)]

    monkeypatch.setattr(maxconn.cli.maxconn, "discover", fake_discover)

    assert maxconn.cli.main(["discover", "192.0.2.0/24"]) == 0

    output = capsys.readouterr().out
    assert calls
    assert 80 in calls[0][1]
    assert 443 in calls[0][1]
    assert "192.0.2.10" in output
    assert "80,443" in output


def test_cli_discover_can_print_json(monkeypatch, capsys):
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "discover",
        lambda *args, **kwargs: [
            DiscoverHost(host="192.0.2.10", open_ports=[443], scanned_ports=[80, 443])
        ],
    )

    assert maxconn.cli.main(["discover", "192.0.2.0/24", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["network"] == "192.0.2.0/24"
    assert payload["hosts"][0]["host"] == "192.0.2.10"
    assert payload["hosts"][0]["open_ports"] == [443]
