from __future__ import annotations

import json

import maxconn.cli
from maxconn.exceptions import ConnectionTimeoutError
from maxconn.history import HistoryStore
from maxconn.hosts import HostEntry, HostStore


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


def test_cli_history_list_limit_keeps_only_the_most_recent(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    for i in range(5):
        store.record(
            alias=None,
            host=f"10.0.0.{i}",
            port=22,
            protocol="ssh",
            username="admin",
            command=f"command {i}",
            ok=True,
            exit_status=0,
            duration=0.1,
            origin="cli",
        )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "list", "--limit", "2"]) == 0

    output = capsys.readouterr().out
    assert "10.0.0.3" in output
    assert "10.0.0.4" in output
    assert "10.0.0.0" not in output
    assert "10.0.0.1" not in output
    assert "10.0.0.2" not in output


def test_cli_history_list_limit_zero_shows_nothing(monkeypatch, tmp_path, capsys):
    # Regression: entries[-args.limit:] with limit=0 computes entries[-0:],
    # and -0 == 0 in Python, so entries[0:] is the WHOLE list, not empty -
    # `--limit 0` showed every entry instead of none.
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
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "list", "--limit", "0"]) == 0

    assert "10.0.0.1" not in capsys.readouterr().out


def test_cli_history_list_since_filters_by_time(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    store.record(
        alias=None,
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command="old command",
        ok=True,
        exit_status=0,
        duration=0.1,
        origin="cli",
    )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "list", "--since", "1h"]) == 0
    assert "old command" in capsys.readouterr().out

    # A --since far enough in the future excludes every existing entry.
    assert maxconn.cli.main(["history", "list", "--since", "2099-01-01"]) == 0
    assert "old command" not in capsys.readouterr().out


def test_cli_history_list_output_json(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    store.record(
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

    assert maxconn.cli.main(["history", "list", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["entries"][0]["host"] == "10.0.0.1"


def test_cli_history_list_output_csv(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    store.record(
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

    assert maxconn.cli.main(["history", "list", "--output", "csv"]) == 0

    output = capsys.readouterr().out
    assert output.splitlines()[0].split(",")[0] == "id"
    assert "show version" in output


def test_cli_history_replay_uses_saved_host_credentials(monkeypatch, tmp_path, capsys):
    history_store = HistoryStore(base_dir=tmp_path)
    entry = history_store.record(
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
    host_store = HostStore(base_dir=tmp_path)
    host_store.add(
        HostEntry(
            name="olt-01",
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
            password="supersecret",
        )
    )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: history_store)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: host_store)

    calls = []

    def fake_connect(host, *, protocol, username, password, port, timeout):
        calls.append({"host": host, "username": username, "password": password, "port": port})
        raise ConnectionTimeoutError("simulated: test never hits the network")

    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    maxconn.cli.main(["history", "replay", str(entry.id)])

    assert calls == [{"host": "10.0.0.1", "username": "admin", "password": "supersecret", "port": 22}]


def test_cli_history_replay_without_command_is_a_clean_error(monkeypatch, tmp_path, capsys):
    store = HistoryStore(base_dir=tmp_path)
    entry = store.record(
        alias=None,
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command=None,
        ok=True,
        exit_status=0,
        duration=0.1,
        origin="cli",
    )
    monkeypatch.setattr(maxconn.cli, "_history_store", lambda: store)

    assert maxconn.cli.main(["history", "replay", str(entry.id)]) == 1
    assert "no command to replay" in capsys.readouterr().err
