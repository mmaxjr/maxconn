from __future__ import annotations

import sys

if sys.platform == "win32":
    import msvcrt

    def read_key() -> str:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            # Extended key (arrows, F-keys, ...): a second call returns the
            # real code. We discard it for this preview and report nothing.
            msvcrt.getwch()
            return ""
        return ch

else:
    import termios
    import tty

    def read_key() -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


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


def read_line(prompt_text: str, completer: Completer, theme, color_enabled: bool) -> str:
    """Read one line with Tab-completion (double-tab lists options) and
    a Cisco-style ``?`` that shows context help without being inserted
    into the buffer.
    """
    buffer = ""
    last_was_tab = False
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

        if key in BACKSPACE:
            if buffer:
                buffer = buffer[:-1]
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            last_was_tab = False
            continue

        if key == TAB:
            matches = completer.matches(buffer)
            if len(matches) == 1:
                token = completer.current_token(buffer)
                remainder = matches[0][len(token) :]
                buffer += remainder
                sys.stdout.write(remainder)
                sys.stdout.flush()
                last_was_tab = False
            elif len(matches) > 1:
                if last_was_tab:
                    _print_options(completer.describe(buffer), theme, color_enabled)
                    sys.stdout.write(prompt_text + buffer)
                    sys.stdout.flush()
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

        buffer += key
        sys.stdout.write(key)
        sys.stdout.flush()
        last_was_tab = False
