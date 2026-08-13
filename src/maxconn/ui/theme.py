from __future__ import annotations

from dataclasses import dataclass

from .box import ASCII_BOX, DOUBLE_BOX, ROUNDED_BOX, SINGLE_BOX, Box
from .style import Style


@dataclass(frozen=True)
class Theme:
    name: str
    box: Box
    header: Style
    ok: Style
    warn: Style
    error: Style
    muted: Style
    prompt: Style


THEMES: dict[str, Theme] = {
    "plain": Theme(
        name="plain",
        box=ASCII_BOX,
        header=Style(),
        ok=Style(),
        warn=Style(),
        error=Style(),
        muted=Style(),
        prompt=Style(),
    ),
    "classic": Theme(
        name="classic",
        box=SINGLE_BOX,
        header=Style.parse("bold"),
        ok=Style.parse("green"),
        warn=Style.parse("yellow"),
        error=Style.parse("bold red"),
        muted=Style.parse("dim"),
        prompt=Style.parse("bold cyan"),
    ),
    "solid": Theme(
        name="solid",
        box=DOUBLE_BOX,
        header=Style.parse("bold white on blue"),
        ok=Style.parse("bold green"),
        warn=Style.parse("bold yellow"),
        error=Style.parse("bold white on red"),
        muted=Style.parse("dim"),
        prompt=Style.parse("bold black on cyan"),
    ),
    "matrix": Theme(
        name="matrix",
        box=ROUNDED_BOX,
        header=Style.parse("bold bright_green"),
        ok=Style.parse("bright_green"),
        warn=Style.parse("green"),
        error=Style.parse("bold bright_red"),
        muted=Style.parse("dim green"),
        prompt=Style.parse("bold bright_green"),
    ),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["classic"])
