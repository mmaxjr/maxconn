from __future__ import annotations

import sys

KEY_UP = "\x00KEY_UP"
KEY_DOWN = "\x00KEY_DOWN"
KEY_LEFT = "\x00KEY_LEFT"
KEY_RIGHT = "\x00KEY_RIGHT"

# Normal key reads are always a single character, so these multi-char
# sentinels can never collide with real typed input.
_WINDOWS_EXTENDED = {
    "H": KEY_UP,
    "P": KEY_DOWN,
    "K": KEY_LEFT,
    "M": KEY_RIGHT,
}
_POSIX_ARROWS = {
    "A": KEY_UP,
    "B": KEY_DOWN,
    "C": KEY_RIGHT,
    "D": KEY_LEFT,
}

if sys.platform == "win32":
    import msvcrt

    def read_key() -> str:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            # Extended key (arrows, F-keys, ...): a second call returns the
            # real scan code.
            code = msvcrt.getwch()
            return _WINDOWS_EXTENDED.get(code, "")
        return ch

else:
    import select
    import termios
    import tty

    def read_key() -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch != "\x1b":
                return ch
            # Might be the start of an arrow-key escape sequence (ESC [ X).
            # Peek with a short timeout so a lone Escape press doesn't hang.
            if not select.select([sys.stdin], [], [], 0.05)[0]:
                return ch
            second = sys.stdin.read(1)
            if second != "[" or not select.select([sys.stdin], [], [], 0.05)[0]:
                return ch
            third = sys.stdin.read(1)
            return _POSIX_ARROWS.get(third, "")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


ENTER = ("\r", "\n")
BACKSPACE = ("\x08", "\x7f")
TAB = "\t"
CTRL_C = "\x03"
QUESTION = "?"


class Completer:
    """Two-level completion: command names, then that command's arguments.

    ``argument_options`` maps a command name to its own dict of
    ``{argument_name: description}``, e.g. ``{"theme": {"plain": "...", ...}}``.
    A command with no entry there simply has no argument completion yet.
    """

    def __init__(
        self,
        commands: dict[str, str],
        argument_options: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.commands = commands
        self.argument_options = argument_options or {}

    def _context(self, buffer: str) -> tuple[dict[str, str], str]:
        if " " not in buffer:
            return self.commands, buffer
        head, _, rest = buffer.partition(" ")
        options = self.argument_options.get(head, {})
        return options, rest.lstrip(" ")

    def current_token(self, buffer: str) -> str:
        return self._context(buffer)[1]

    def matches(self, buffer: str) -> list[str]:
        candidates, token = self._context(buffer)
        return sorted(name for name in candidates if name.startswith(token))

    def describe(self, buffer: str) -> list[tuple[str, str]]:
        candidates, _ = self._context(buffer)
        return [(name, candidates[name]) for name in self.matches(buffer)]


def _print_options(options: list[tuple[str, str]], theme, color_enabled: bool) -> None:
    sys.stdout.write("\n")
    width = max((len(name) for name, _ in options), default=0)
    for name, description in options:
        label = theme.header.render(name.ljust(width), enabled=color_enabled)
        sys.stdout.write(f"  {label}  {description}\n")
    sys.stdout.flush()


def _redraw_line(prompt_text: str, buffer: str, cursor: int | None = None) -> None:
    sys.stdout.write("\r\x1b[2K" + prompt_text + buffer)
    if cursor is not None and cursor < len(buffer):
        sys.stdout.write(f"\x1b[{len(buffer) - cursor}D")
    sys.stdout.flush()


def read_line(
    prompt_text: str,
    completer: Completer,
    theme,
    color_enabled: bool,
    history: list[str] | None = None,
) -> str:
    """Read one line with Tab-completion (double-tab lists options), a
    Cisco-style ``?`` that shows context help without being inserted into
    the buffer, and Up/Down browsing through ``history`` (most recent
    submitted lines first), like a normal shell.
    """
    buffer = ""
    cursor = 0
    last_was_tab = False
    history = history if history is not None else []
    history_index = len(history)
    draft = ""  # what was being typed before Up was first pressed
    sys.stdout.write(prompt_text)
    sys.stdout.flush()

    while True:
        key = read_key()

        if not key:
            continue

        if key in ENTER:
            sys.stdout.write("\n")
            return buffer

        if key == CTRL_C:
            raise KeyboardInterrupt

        if key == KEY_UP:
            if history and history_index > 0:
                if history_index == len(history):
                    draft = buffer
                history_index -= 1
                buffer = history[history_index]
                cursor = len(buffer)
                _redraw_line(prompt_text, buffer, cursor)
            last_was_tab = False
            continue

        if key == KEY_DOWN:
            if history_index < len(history):
                history_index += 1
                buffer = draft if history_index == len(history) else history[history_index]
                cursor = len(buffer)
                _redraw_line(prompt_text, buffer, cursor)
            last_was_tab = False
            continue

        if key == KEY_LEFT:
            if cursor > 0:
                cursor -= 1
                sys.stdout.write("\x1b[1D")
                sys.stdout.flush()
            last_was_tab = False
            continue

        if key == KEY_RIGHT:
            if cursor < len(buffer):
                cursor += 1
                sys.stdout.write("\x1b[1C")
                sys.stdout.flush()
            last_was_tab = False
            continue

        if key in BACKSPACE:
            if cursor > 0:
                buffer = buffer[: cursor - 1] + buffer[cursor:]
                cursor -= 1
                _redraw_line(prompt_text, buffer, cursor)
            last_was_tab = False
            continue

        if key == TAB:
            matches = completer.matches(buffer)
            if len(matches) == 1:
                token = completer.current_token(buffer)
                remainder = matches[0][len(token) :]
                buffer = buffer[:cursor] + remainder + buffer[cursor:]
                cursor += len(remainder)
                _redraw_line(prompt_text, buffer, cursor)
                last_was_tab = False
            elif len(matches) > 1:
                if last_was_tab:
                    _print_options(completer.describe(buffer), theme, color_enabled)
                    _redraw_line(prompt_text, buffer, cursor)
                    last_was_tab = False
                else:
                    last_was_tab = True
            continue

        if key == QUESTION:
            options = completer.describe(buffer) or [("(sem opções)", "")]
            _print_options(options, theme, color_enabled)
            sys.stdout.write(prompt_text + buffer)
            sys.stdout.flush()
            last_was_tab = False
            continue

        buffer = buffer[:cursor] + key + buffer[cursor:]
        cursor += len(key)
        _redraw_line(prompt_text, buffer, cursor)
        last_was_tab = False
