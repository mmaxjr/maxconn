from __future__ import annotations

COMMANDS: dict[str, str] = {
    "ping": "probe host reachability",
    "scan": "scan tcp ports",
    "traceroute": "show network path to a host",
    "mtr": "live path monitoring",
    "inventory": "list known devices",
    "backup": "backup device configuration",
    "diff": "compare two backups",
    "discover": "scan a subnet for devices",
    "connect": "open a session with a device",
    "theme": "change the visual theme (plain, classic, solid, matrix)",
    "reboot": "restart the shell with the current saved theme",
    "help": "show this list of commands",
    "exit": "leave the maxconn shell",
}

ARGUMENT_OPTIONS: dict[str, dict[str, str]] = {
    "theme": {
        "plain": "no color, ascii borders",
        "classic": "16-color palette, single-line borders",
        "solid": "bold headers with background, double-line borders",
        "matrix": "monochrome green on black, rounded borders",
    },
}
