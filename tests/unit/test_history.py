from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from maxconn.history import (
    HistoryEntry,
    HistoryStore,
    format_history_csv,
    format_history_table,
    parse_since,
)


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


def test_history_store_record_is_safe_under_concurrent_writers(tmp_path, monkeypatch):
    # Regression: record() computes the next id via list() (a read of the
    # whole file) then appends a line - with no lock, two concurrent
    # record() calls can compute the same "next id" and each append a line,
    # producing duplicate ids instead of a clean sequence.
    store = HistoryStore(base_dir=tmp_path)
    original_list = HistoryStore.list

    def slow_list(self):
        result = original_list(self)
        time.sleep(0.01)
        return result

    monkeypatch.setattr(HistoryStore, "list", slow_list)

    def record_one(i):
        store.record(
            alias=None,
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
            command=f"command {i}",
            ok=True,
            exit_status=0,
            duration=0.1,
            origin="cli",
        )

    threads = [threading.Thread(target=record_one, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    entries = store.list()
    assert len(entries) == 4
    assert len({entry.id for entry in entries}) == 4  # no duplicate ids


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


def test_history_csv_includes_header_and_rows():
    csv_text = format_history_csv(
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

    lines = csv_text.strip().splitlines()
    assert lines[0].split(",")[:3] == ["id", "timestamp", "alias"]
    assert "olt-01" in lines[1]
    assert "show version" in lines[1]


def test_parse_since_today_matches_start_of_current_utc_day():
    now = datetime(2026, 8, 14, 15, 30, tzinfo=timezone.utc)
    assert parse_since("today", now=now) == datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)


def test_parse_since_yesterday_is_one_day_before_today():
    now = datetime(2026, 8, 14, 15, 30, tzinfo=timezone.utc)
    assert parse_since("yesterday", now=now) == datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)


def test_parse_since_relative_hours_and_days():
    now = datetime(2026, 8, 14, 15, 30, tzinfo=timezone.utc)
    assert parse_since("24h", now=now) == now - timedelta(hours=24)
    assert parse_since("7d", now=now) == now - timedelta(days=7)


def test_parse_since_accepts_an_iso_date():
    assert parse_since("2026-08-01") == datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_parse_since_rejects_garbage():
    with pytest.raises(ValueError):
        parse_since("not-a-real-date")
