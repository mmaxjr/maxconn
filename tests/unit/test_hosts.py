from __future__ import annotations

import threading
import time

from maxconn.hosts import (
    HostEntry,
    HostStore,
    format_hosts_table,
    format_seen_hosts_table,
)


def test_host_store_add_list_show_and_remove(tmp_path):
    store = HostStore(base_dir=tmp_path)
    entry = HostEntry(
        name="olt-01",
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        profile="huawei",
        tags=["olt", "pop-centro"],
        notes="core pop",
    )

    store.add(entry)

    assert store.get("olt-01") == entry
    assert store.list() == [entry]

    store.remove("olt-01")
    assert store.list() == []


def test_host_store_add_is_safe_under_concurrent_writers(tmp_path, monkeypatch):
    # Regression: add() does read-all -> merge -> write-all with no lock,
    # so two concurrent add() calls can both read the same snapshot and
    # each write back a version missing the other's entry (lost update).
    # Widen the race window deterministically by slowing down the read.
    store = HostStore(base_dir=tmp_path)
    original_list = HostStore.list

    def slow_list(self):
        result = original_list(self)
        time.sleep(0.01)
        return result

    monkeypatch.setattr(HostStore, "list", slow_list)

    def add_one(i):
        store.add(HostEntry(name=f"host-{i}", host="10.0.0.1", port=22, protocol="ssh", username="admin"))

    threads = [threading.Thread(target=add_one, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(store.list()) == 4


def test_host_store_remove_reads_the_host_list_only_once(tmp_path, monkeypatch):
    # remove() must not re-read/re-parse hosts.json a second time just to
    # check whether the name existed - besides being wasteful, a second
    # read is racy against a concurrent write between the two reads.
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh", username="admin"))

    calls = []
    original_list = HostStore.list

    def counting_list(self):
        calls.append(1)
        return original_list(self)

    monkeypatch.setattr(HostStore, "list", counting_list)

    store.remove("olt-01")

    assert len(calls) == 1


def test_hosts_table_uses_required_columns():
    entry = HostEntry(
        name="olt-01",
        host="10.0.0.1",
        port=22,
        protocol="ssh",
        username="admin",
        profile="huawei",
        tags=["olt", "pop-centro"],
        notes=None,
    )

    table = format_hosts_table([entry])

    assert "NAME" in table
    assert "HOST/IP" in table
    assert "PORT" in table
    assert "PROTOCOL" in table
    assert "USER" in table
    assert "PROFILE" in table
    assert "TAGS" in table
    assert "olt-01" in table
    assert "10.0.0.1" in table


def test_record_seen_tracks_count_and_never_password(tmp_path):
    store = HostStore(base_dir=tmp_path)

    first = store.record_seen("10.0.0.1", protocol="ssh", port=22, username="admin")
    second = store.record_seen("10.0.0.1", protocol="ssh", port=22, username="admin")

    seen = store.list_seen()
    assert len(seen) == 1
    assert seen[0].count == 2
    assert seen[0].host == "10.0.0.1"
    assert seen[0].username == "admin"
    assert not hasattr(first, "password")
    assert not hasattr(second, "password")


def test_save_seen_promotes_recent_host_to_saved_host(tmp_path):
    store = HostStore(base_dir=tmp_path)
    store.record_seen("10.0.0.1", protocol="ssh", port=22, username="admin")

    saved = store.save_seen(1, name="olt-01", profile="huawei", tags=["olt"], notes="pop")

    assert saved.name == "olt-01"
    assert saved.host == "10.0.0.1"
    assert saved.protocol == "ssh"
    assert store.get("olt-01").profile == "huawei"


def test_seen_hosts_table_has_index_and_recent_fields(tmp_path):
    store = HostStore(base_dir=tmp_path)
    store.record_seen("10.0.0.1", protocol="ssh", port=22, username="admin")

    table = format_seen_hosts_table(store.list_seen())

    assert "ID" in table
    assert "HOST/IP" in table
    assert "COUNT" in table
    assert "10.0.0.1" in table


def test_hosts_saved_password_is_explicit_and_hidden_from_table(tmp_path):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="olt-01",
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
            profile=None,
            tags=[],
            notes=None,
            password="secret",
        )
    )

    table = format_hosts_table(store.list())

    assert "secret" not in table
    assert store.get("olt-01").password == "secret"
