from __future__ import annotations

import subprocess
from importlib import import_module

from maxconn.net.mtr import mtr
from maxconn.net.traceroute import traceroute


def test_traceroute_runs_platform_command_and_returns_hops(monkeypatch):
    def fake_run(args, capture_output, text, timeout, check):
        assert args[-1] == "example.com"
        return subprocess.CompletedProcess(
            args,
            0,
            stdout="  1     1 ms     1 ms     1 ms  192.0.2.1\n  2    10 ms    11 ms    12 ms  example.com\n",
            stderr="",
        )

    monkeypatch.setattr(import_module("maxconn.net.traceroute").subprocess, "run", fake_run)

    result = traceroute("example.com", timeout=5.0)

    assert result.host == "example.com"
    assert result.returncode == 0
    assert result.hops[0].hop == 1
    assert result.hops[0].address == "192.0.2.1"
    assert result.hops[1].address == "example.com"


def test_mtr_aggregates_repeated_ping_results(monkeypatch):
    values = [True, False, True]

    def fake_ping(host, timeout=1.0, count=1):
        reachable = values.pop(0)

        class Result:
            elapsed = 0.010 if reachable else 0.050
            error = "" if reachable else "timeout"
            returncode = 0 if reachable else 1

        return Result()

    monkeypatch.setattr(import_module("maxconn.net.mtr"), "ping", fake_ping)

    result = mtr("192.0.2.1", count=3, timeout=1.0)

    assert result.host == "192.0.2.1"
    assert result.sent == 3
    assert result.received == 2
    assert result.loss_percent == 33.33
    assert result.avg == 0.01
