import subprocess
from importlib import import_module

from maxconn.net.ping import ping


def test_ping_returns_reachable_result(monkeypatch):
    def fake_run(args, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(args, 0, stdout="Reply from 127.0.0.1 time=1ms", stderr="")

    ping_module = import_module("maxconn.net.ping")
    monkeypatch.setattr(ping_module.subprocess, "run", fake_run)

    result = ping("127.0.0.1", timeout=1.0)

    assert result.host == "127.0.0.1"
    assert result.reachable is True
    assert result.returncode == 0
    assert result.elapsed >= 0


def test_ping_returns_unreachable_result(monkeypatch):
    def fake_run(args, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="timeout")

    ping_module = import_module("maxconn.net.ping")
    monkeypatch.setattr(ping_module.subprocess, "run", fake_run)

    result = ping("192.0.2.1", timeout=1.0)

    assert result.reachable is False
    assert result.error == "timeout"
