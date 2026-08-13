from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    top_left: str
    top: str
    top_right: str
    mid_left: str
    mid_vertical: str
    mid_right: str
    bottom_left: str
    bottom: str
    bottom_right: str


ASCII_BOX = Box("+", "-", "+", "|", "|", "|", "+", "-", "+")
SINGLE_BOX = Box("┌", "─", "┐", "│", "│", "│", "└", "─", "┘")
DOUBLE_BOX = Box("╔", "═", "╗", "║", "║", "║", "╚", "═", "╝")
ROUNDED_BOX = Box("╭", "─", "╮", "│", "│", "│", "╰", "─", "╯")
