from __future__ import annotations

import pytest

import maxconn.cli
from maxconn.snippets import SnippetStore


def test_cli_snippet_add_from_command_then_list_and_show(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert (
        maxconn.cli.main(
            [
                "snippet",
                "add",
                "huawei-cgnat",
                "--command",
                "nat address-group 1 10.0.0.0 10.0.0.255",
                "--tags",
                "huawei,cgnat",
            ]
        )
        == 0
    )

    assert maxconn.cli.main(["snippet", "list"]) == 0
    listing = capsys.readouterr().out
    assert "huawei-cgnat" in listing
    assert "huawei,cgnat" in listing

    assert maxconn.cli.main(["snippet", "show", "huawei-cgnat"]) == 0
    assert capsys.readouterr().out.strip() == "nat address-group 1 10.0.0.0 10.0.0.255"


def test_cli_snippet_add_from_file(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)
    source_file = tmp_path / "extend.txt"
    source_file.write_text("diskpart\nselect disk 0\nextend", encoding="utf-8")

    assert maxconn.cli.main(["snippet", "add", "windows-extend", "--file", str(source_file)]) == 0
    capsys.readouterr()

    assert maxconn.cli.main(["snippet", "show", "windows-extend"]) == 0
    assert capsys.readouterr().out == "diskpart\nselect disk 0\nextend\n"


def test_cli_snippet_add_requires_command_or_file(monkeypatch, tmp_path, capsys):
    # argparse's own mutually-exclusive-group validation raises SystemExit
    # before dispatch() ever runs - it never reaches main()'s try/except.
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    with pytest.raises(SystemExit):
        maxconn.cli.main(["snippet", "add", "x"])


def test_cli_snippet_add_rejects_both_command_and_file(monkeypatch, tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    with pytest.raises(SystemExit):
        maxconn.cli.main(["snippet", "add", "x", "--command", "a", "--file", "b.txt"])


def test_cli_snippet_list_filters_by_tag(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "one", tags=["huawei"])
    store.add("b", "two", tags=["cisco"])
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "list", "--tag", "huawei"]) == 0
    output = capsys.readouterr().out
    assert "a" in output
    assert "b" not in output


def test_cli_snippet_edit_overwrites_content_via_command(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "old content", tags=["huawei"])
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "edit", "a", "--command", "new content"]) == 0

    entry, content = store.get("a")
    assert content == "new content"
    assert entry.tags == ["huawei"]


def test_cli_snippet_edit_can_replace_tags(monkeypatch, tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "content", tags=["huawei"])
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "edit", "a", "--command", "content", "--tags", "cisco"]) == 0

    entry, _ = store.get("a")
    assert entry.tags == ["cisco"]


def test_cli_snippet_remove(monkeypatch, tmp_path):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "content")
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "remove", "a"]) == 0
    assert store.list() == []


def test_cli_snippet_show_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "show", "does-not-exist"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_snippet_remove_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "remove", "does-not-exist"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_snippet_add_duplicate_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = SnippetStore(base_dir=tmp_path)
    store.add("a", "content")
    monkeypatch.setattr(maxconn.cli, "_snippet_store", lambda: store)

    assert maxconn.cli.main(["snippet", "add", "a", "--command", "other"]) == 1
    assert "a" in capsys.readouterr().err
