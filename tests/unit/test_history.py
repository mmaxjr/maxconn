from __future__ import annotations

from maxconn.history import HistoryEntry, HistoryStore, format_history_table


def test_history_store_records_entries_without_secrets(tmp_path):
    store = HistoryStore(base_dir=tmp_path)

    entry = store.record(
        alias="olt-01",
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command="show password supersecret",
        ok=True,
        exit_status=0,
        duration=0.25,
        origin="cli",
    )

    entries = store.list()
    assert entries == [entry]
    assert entries[0].command == "show password <redacted>"
    assert "supersecret" not in (tmp_path / "history.jsonl").read_text(encoding="utf-8")


def test_history_redacts_equals_sign_flag_form(tmp_path):
    store = HistoryStore(base_dir=tmp_path)

    entry = store.record(
        alias=None,
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        command="maxconn ssh 10.0.0.1 --password=supersecret --command 'show version'",
        ok=True,
        exit_status=0,
        duration=0.25,
        origin="cli",
    )

    assert "supersecret" not in entry.command
    assert "supersecret" not in (tmp_path / "history.jsonl").read_text(encoding="utf-8")


def test_history_redacts_credentials_embedded_in_a_url(tmp_path):
    store = HistoryStore(base_dir=tmp_path)

    entry = store.record(
        alias=None,
        host="10.0.0.1",
        port=None,
        protocol="ssh",
        username=None,
        command="curl ftp://admin:supersecret@10.0.0.1/backup.cfg",
        ok=True,
        exit_status=0,
        duration=0.25,
        origin="cli",
    )

    assert "supersecret" not in entry.command
    assert "admin" in entry.command  # the username itself isn't a secret
    assert "10.0.0.1" in entry.command  # nor is the host
    assert "supersecret" not in (tmp_path / "history.jsonl").read_text(encoding="utf-8")


def test_history_table_shows_core_fields():
    table = format_history_table(
        [
            HistoryEntry(
                id=1,
                timestamp="2026-08-14T10:00:00+00:00",
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
        ]
    )

    assert "ID" in table
    assert "HOST/IP" in table
    assert "COMMAND" in table
    assert "olt-01" in table
    assert "show version" in table
