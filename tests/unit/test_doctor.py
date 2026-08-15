from __future__ import annotations

import socket

from maxconn.doctor import (
    check_dir_writable,
    check_dns,
    check_internet,
    check_terminal,
    compare_versions,
    default_gateway,
)


def test_check_dir_writable_true_for_a_writable_directory(tmp_path):
    assert check_dir_writable(tmp_path) is True


def test_check_dir_writable_creates_a_missing_directory_then_confirms(tmp_path):
    missing = tmp_path / "does-not-exist" / "still-missing"
    assert check_dir_writable(missing) is True
    assert missing.is_dir()


def test_check_dns_true_when_resolution_succeeds(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert check_dns("example.com", timeout=1.0) is True


def test_check_dns_false_when_resolution_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no dns")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert check_dns("example.invalid", timeout=1.0) is False


def test_check_internet_true_when_connect_succeeds(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: socket.socket())
    assert check_internet(timeout=1.0) is True


def test_check_internet_false_when_connect_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("unreachable")

    monkeypatch.setattr(socket, "create_connection", boom)
    assert check_internet(timeout=1.0) is False


def test_check_terminal_reports_tty_and_color_flags():
    result = check_terminal()
    assert "isatty" in result
    assert "color" in result


def test_default_gateway_returns_none_or_a_string():
    # Best-effort/platform-dependent - just must not raise, and must return
    # either a gateway IP string or None (never crash doctor --network).
    result = default_gateway()
    assert result is None or isinstance(result, str)


def test_compare_versions_up_to_date():
    assert compare_versions("0.1.19", "0.1.19") == "up-to-date"


def test_compare_versions_update_available():
    assert compare_versions("0.1.19", "0.1.20") == "update-available"


def test_compare_versions_ahead_of_pypi():
    assert compare_versions("0.1.20", "0.1.19") == "ahead"


def test_compare_versions_unknown_when_latest_missing():
    assert compare_versions("0.1.19", None) == "unknown"
