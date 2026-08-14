from __future__ import annotations

COMMANDS: dict[str, str] = {
    "hosts": "manage local saved hosts",
    "history": "manage local command history",
    "ping": "probe host reachability",
    "scan": "scan tcp ports",
    "doctor": "print local environment diagnostics",
    "selftest": "run quick local CLI checks",
    "discover": "scan a subnet for devices",
    "traceroute": "show network path to a host",
    "mtr": "live path monitoring",
    "sftp": "copy and manage files over SFTP",
    "snmp": "read SNMP v2c values",
    "connect": "open a session with a device",
    "open": "open a saved host in an interactive session",
    "ssh": "open an interactive SSH session",
    "telnet": "open an interactive Telnet session",
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
