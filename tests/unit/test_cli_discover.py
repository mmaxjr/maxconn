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


def test_cli_discover_only_open_hides_closed_hosts(monkeypatch, capsys):
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "discover",
        lambda *args, **kwargs: [
            DiscoverHost(host="192.0.2.10", open_ports=[], scanned_ports=[80, 443]),
            DiscoverHost(host="192.0.2.11", open_ports=[443], scanned_ports=[80, 443]),
        ],
    )

    assert maxconn.cli.main(["discover", "192.0.2.0/24", "--only-open"]) == 0

    output = capsys.readouterr().out
    assert "192.0.2.11" in output
    assert "192.0.2.10" not in output


def test_cli_discover_save_found_records_open_hosts(monkeypatch, tmp_path, capsys):
    store = maxconn.cli.HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "discover",
        lambda *args, **kwargs: [
            DiscoverHost(host="192.0.2.10", open_ports=[22], scanned_ports=[22, 80]),
            DiscoverHost(host="192.0.2.11", open_ports=[], scanned_ports=[22, 80]),
        ],
    )

    assert maxconn.cli.main(["discover", "192.0.2.0/24", "--ports", "22,80", "--save-found"]) == 0

    capsys.readouterr()
    saved = store.list()
    assert len(saved) == 1
    assert saved[0].host == "192.0.2.10"
    assert saved[0].port == 22
    assert saved[0].protocol == "ssh"
