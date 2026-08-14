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


def test_tab_completion_uses_text_up_to_cursor_not_the_whole_buffer(monkeypatch):
    # Regression: typing "disextra" then moving the cursor back to right
    # after "dis" and pressing Tab must complete against "dis" (the text
    # up to the cursor), not against the literal string "disextra" (which
    # matches nothing) - completion should work the same way when editing
    # mid-line as it does when the cursor is at the end.
    queued = iter(list("disextra") + [ui_input.KEY_LEFT] * 5 + [ui_input.TAB, "\n"])
    monkeypatch.setattr(ui_input, "read_key", lambda: next(queued))

    line = ui_input.read_line(
        "maxconn> ",
        Completer({"discover": "scan a subnet", "diff": "compare two backups"}),
        get_theme("plain"),
        False,
    )

    assert line == "discoverextra"


def test_read_line_pasted_text_at_end_does_not_redraw_every_character(monkeypatch, capsys):
    line = _run_keys(
        monkeypatch,
        list("maxconn hosts list") + ["\n"],
    )

    assert line == "maxconn hosts list"
    output = capsys.readouterr().out
    assert output.count("maxconn> ") == 1
    assert "\x1b[2K" not in output
