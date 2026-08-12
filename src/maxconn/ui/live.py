from __future__ import annotations

import sys


class LiveRegion:
    """Redraws a fixed block of lines in place, without a full-screen clear.

    Moves the cursor up by exactly the number of lines drawn last time and
    erases each one before writing the new content. This replaces the
    "clear whole screen" approach (``\\033[2J\\033[H``) used by
    ``maxconn mtr`` today, which causes visible flicker/scroll jump.
    """

    def __init__(self) -> None:
        self._last_height = 0

    def update(self, lines: list[str]) -> None:
        out = sys.stdout
        if self._last_height:
            out.write("\r\x1b[2K")
            out.write("\x1b[1A\x1b[2K" * (self._last_height - 1))
        out.write("\n".join(lines) + "\n")
        out.flush()
        self._last_height = len(lines)

    def clear(self) -> None:
        if not self._last_height:
            return
        out = sys.stdout
        out.write("\r\x1b[2K")
        out.write("\x1b[1A\x1b[2K" * (self._last_height - 1))
        out.flush()
        self._last_height = 0
