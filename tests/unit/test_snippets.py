from __future__ import annotations

import threading
import time

import pytest

from maxconn.snippets import SnippetEntry, SnippetStore, format_snippets_table


def test_snippet_store_add_get_list_and_remove(tmp_path):
    store = SnippetStore(base_dir=tmp_path)

    entry = store.add("huawei-cgnat", "nat address-group 1\n 10.0.0.0 10.0.0.255", tags=["huawei", "cgnat"])

    assert entry.name == "huawei-cgnat"
    assert entry.tags == ["huawei", "cgnat"]
    assert entry.created == entry.updated

    fetched_entry, content = store.get("huawei-cgnat")
    assert fetched_entry == entry
    assert content == "nat address-group 1\n 10.0.0.0 10.0.0.255"
    assert [e.name for e in store.list()] == ["huawei-cgnat"]

    store.remove("huawei-cgnat")
    assert store.list() == []
    with pytest.raises(KeyError):
        store.get("huawei-cgnat")


def test_snippet_store_content_is_stored_as_a_readable_text_file(tmp_path):
    # The whole point of this design is that a saved snippet can be opened
    # and edited with any plain text editor, not just through the CLI.
    store = SnippetStore(base_dir=tmp_path)
    store.add("windows-extend-disk", "diskpart\nselect disk 0\nextend")

    content_file = tmp_path / "snippets" / "windows-extend-disk.txt"
    assert content_file.read_text(encoding="utf-8") == "diskpart\nselect disk 0\nextend"


def test_snippet_store_add_rejects_duplicate_name(tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    store.add("dup", "one")

    with pytest.raises(ValueError):
        store.add("dup", "two")


def test_snippet_store_list_can_filter_by_tag(tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "one", tags=["huawei"])
    store.add("b", "two", tags=["cisco"])
    store.add("c", "three", tags=["huawei", "cgnat"])

    assert [e.name for e in store.list(tag="huawei")] == ["a", "c"]


def test_snippet_store_edit_overwrites_content_and_bumps_updated(tmp_path, monkeypatch):
    times = iter(["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"])
    monkeypatch.setattr("maxconn.snippets._now", lambda: next(times))

    store = SnippetStore(base_dir=tmp_path)
    original = store.add("a", "old content", tags=["huawei"])
    edited = store.edit("a", "new content")

    entry, content = store.get("a")
    assert content == "new content"
    assert entry.tags == ["huawei"]
    assert edited.created == original.created == "2026-01-01T00:00:00+00:00"
    assert edited.updated == "2026-01-02T00:00:00+00:00"


def test_snippet_store_edit_can_replace_tags(tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "content", tags=["huawei"])

    store.edit("a", "content", tags=["cisco", "cgnat"])

    entry, _ = store.get("a")
    assert entry.tags == ["cisco", "cgnat"]


def test_snippet_store_edit_missing_snippet_raises(tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    with pytest.raises(KeyError):
        store.edit("missing", "content")


def test_snippet_store_remove_missing_snippet_raises(tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    with pytest.raises(KeyError):
        store.remove("missing")


def test_snippet_store_add_is_safe_under_concurrent_writers(tmp_path, monkeypatch):
    store = SnippetStore(base_dir=tmp_path)
    original_list = SnippetStore.list

    def slow_list(self, *, tag=None):
        result = original_list(self, tag=tag)
        time.sleep(0.01)
        return result

    monkeypatch.setattr(SnippetStore, "list", slow_list)

    def add_one(i):
        store.add(f"snippet-{i}", f"content {i}")

    threads = [threading.Thread(target=add_one, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(store.list()) == 4


def test_format_snippets_table_includes_name_tags_and_updated():
    entry = SnippetEntry(
        name="huawei-cgnat",
        tags=["huawei", "cgnat"],
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
    )

    table = format_snippets_table([entry])

    assert "huawei-cgnat" in table
    assert "huawei,cgnat" in table
    assert "2026-01-01T00:00:00+00:00" in table
