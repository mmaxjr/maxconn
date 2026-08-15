from __future__ import annotations

import json
import platform
import re
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path


def check_dir_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".maxconn-doctor-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def check_dns(hostname: str = "pypi.org", *, timeout: float = 3.0) -> bool:
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except OSError:
        return False


def check_internet(host: str = "1.1.1.1", port: int = 443, *, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_terminal() -> dict[str, bool]:
    from maxconn.ui.caps import supports_color

    try:
        is_tty = sys.stdout.isatty()
    except (AttributeError, OSError, ValueError):
        is_tty = False
    return {"isatty": is_tty, "color": supports_color()}


def default_gateway(*, timeout: float = 3.0) -> str | None:
    if platform.system().lower() == "windows":
        return _default_gateway_windows(timeout=timeout)
    return _default_gateway_linux()


def _default_gateway_windows(*, timeout: float) -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in completed.stdout.splitlines():
        if "Default Gateway" in line:
            _, _, value = line.partition(":")
            value = value.strip()
            if value:
                return value
    return None


def _default_gateway_linux() -> str | None:
    try:
        with open("/proc/net/route", encoding="utf-8") as handle:
            lines = handle.readlines()[1:]
    except OSError:
        return None
    for line in lines:
        fields = line.split()
        if len(fields) < 3 or fields[1] != "00000000":
            continue
        hex_gateway = fields[2]
        if not re.fullmatch(r"[0-9A-Fa-f]{8}", hex_gateway):
            continue
        octets = [int(hex_gateway[i : i + 2], 16) for i in (6, 4, 2, 0)]
        return ".".join(str(octet) for octet in octets)
    return None


def fetch_latest_pypi_version(package: str = "maxconn", *, timeout: float = 3.0) -> str | None:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data["info"]["version"])
    except (urllib.error.URLError, OSError, ValueError, KeyError, TimeoutError):
        return None


def compare_versions(local: str, latest: str | None) -> str:
    if latest is None:
        return "unknown"
    local_parts = _version_tuple(local)
    latest_parts = _version_tuple(latest)
    if local_parts == latest_parts:
        return "up-to-date"
    if local_parts < latest_parts:
        return "update-available"
    return "ahead"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))
