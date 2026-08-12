from __future__ import annotations

from dataclasses import dataclass

_COLOR_CODES = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
}
_BG_OFFSET = 10


@dataclass(frozen=True)
class Style:
    color: str | None = None
    bgcolor: str | None = None
    bold: bool = False
    dim: bool = False
    underline: bool = False

    @classmethod
    def parse(cls, spec: str) -> Style:
        """Parse a small DSL like "bold red on blue" into a Style."""
        if not spec:
            return cls()
        tokens = spec.split()
        if "on" in tokens:
            split_at = tokens.index("on")
            fg_tokens, bg_tokens = tokens[:split_at], tokens[split_at + 1 :]
        else:
            fg_tokens, bg_tokens = tokens, []
        color = next((t for t in fg_tokens if t in _COLOR_CODES), None)
        bgcolor = next((t for t in bg_tokens if t in _COLOR_CODES), None)
        return cls(
            color=color,
            bgcolor=bgcolor,
            bold="bold" in tokens,
            dim="dim" in tokens,
            underline="underline" in tokens,
        )

    def render(self, text: str, *, enabled: bool = True) -> str:
        if not enabled:
            return text
        codes: list[str] = []
        if self.bold:
            codes.append("1")
        if self.dim:
            codes.append("2")
        if self.underline:
            codes.append("4")
        if self.color:
            codes.append(str(_COLOR_CODES[self.color]))
        if self.bgcolor:
            codes.append(str(_COLOR_CODES[self.bgcolor] + _BG_OFFSET))
        if not codes:
            return text
        return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"
