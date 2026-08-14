from __future__ import annotations

import maxconn.cli
from maxconn.history import HistoryStore


def test_cli_history_list_show_and_clear(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    entry = store.record(
        alias="olt-01",
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command="show version",
        ok=True,
        exit_status=0,
        duration=0.1,
        origin="cli",
    )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "list"]) == 0
    assert "show version" in capsys.readouterr().out

    assert maxconn.cli.main(["history", "show", str(entry.id)]) == 0
    assert '"host": "10.0.0.1"' in capsys.readouterr().out

    assert maxconn.cli.main(["history", "clear"]) == 0
    assert store.list() == []


def test_cli_history_list_filters_by_protocol(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    store.record(
        alias=None,
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command="show version",
        ok=True,
        exit_status=0,
        duration=0.1,
        origin="cli",
    )
    store.record(
        alias=None,
        host="10.0.0.2",
        port=23,
        protocol="telnet",
        username="admin",
        command="show status",
        ok=True,
        exit_status=0,
        duration=0.1,
        origin="cli",
    )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "list", "--protocol", "ssh"]) == 0

    output = capsys.readouterr().out
    assert "10.0.0.1" in output
    assert "10.0.0.2" not in output
