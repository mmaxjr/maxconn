from __future__ import annotations

from maxconn.ui import input as ui_input
from maxconn.ui.input import Completer
from maxconn.ui.theme import get_theme


def _run_keys(monkeypatch, keys: list[str], history: list[str] | None = None) -> str:
    queued = iter(keys)
    monkeypatch.setattr(ui_input, "read_key", lambda: next(queued))
    return ui_input.read_line(
        "maxconn> ",
        Completer({}),
        get_theme("plain"),
        False,
        history=history,
    )


def test_read_line_can_move_left_and_insert_text(monkeypatch, capsys):
    line = _run_keys(
        monkeypatch,
        ["s", "s", "h", " ", "b", "p", ui_input.KEY_LEFT, "g", "\n"],
    )

    assert line == "ssh bgp"
    assert "ssh bgp" in capsys.readouterr().out


def test_read_line_backspace_deletes_before_cursor(monkeypatch):
    line = _run_keys(
        monkeypatch,
        ["s", "s", "h", "x", ui_input.KEY_LEFT, ui_input.KEY_RIGHT, "\b", "\n"],
    )

    assert line == "ssh"


def test_read_line_history_entry_can_be_edited_with_arrows(monkeypatch):
    line = _run_keys(
        monkeypatch,
        [ui_input.KEY_UP, ui_input.KEY_LEFT, ui_input.KEY_LEFT, "2", "\n"],
        history=["ssh bgp-view"],
    )

    assert line == "ssh bgp-vi2ew"


def test_read_line_pasted_text_at_end_does_not_redraw_every_character(monkeypatch, capsys):
    line = _run_keys(
        monkeypatch,
        list("maxconn hosts list") + ["\n"],
    )

    assert line == "maxconn hosts list"
    output = capsys.readouterr().out
    assert output.count("maxconn> ") == 1
    assert "\x1b[2K" not in output
