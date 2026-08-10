from __future__ import annotations

import subprocess
from importlib import import_module

from maxconn.net.mtr import WinMTRHop, mtr, probe_mtr_once, render_mtr_table
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


def test_probe_mtr_once_updates_each_traceroute_hop(monkeypatch):
    class FirstHop:
        hop = 1
        address = "192.0.2.1"

    class SecondHop:
        hop = 2
        address = "8.8.8.8"

    class Trace:
        def __init__(self):
            self.hops = [FirstHop(), SecondHop()]

    elapsed_by_host = {"192.0.2.1": 0.004, "8.8.8.8": 0.012}

    def fake_traceroute(host, timeout=30.0):
        return Trace()

    def fake_ping(host, timeout=1.0, count=1):
        class Result:
            returncode = 0
            elapsed = elapsed_by_host[host]

        return Result()

    monkeypatch.setattr(import_module("maxconn.net.mtr"), "traceroute", fake_traceroute)
    monkeypatch.setattr(import_module("maxconn.net.mtr"), "ping", fake_ping)

    hops: dict[int, WinMTRHop] = {}
    probe_mtr_once("8.8.8.8", hops, timeout=1.0)

    assert hops[1].host == "192.0.2.1"
    assert hops[1].sent == 1
    assert hops[1].received == 1
    assert hops[1].avg_ms == 4.0
    assert hops[2].host == "8.8.8.8"
    assert hops[2].avg_ms == 12.0


def test_probe_mtr_once_adds_destination_when_trace_is_partial(monkeypatch):
    class FirstHop:
        hop = 1
        address = "192.0.2.1"

    class Trace:
        def __init__(self):
            self.hops = [FirstHop()]

    def fake_traceroute(host, timeout=30.0):
        return Trace()

    def fake_ping(host, timeout=1.0, count=1):
        class Result:
            returncode = 0
            elapsed = 0.010

        return Result()

    monkeypatch.setattr(import_module("maxconn.net.mtr"), "traceroute", fake_traceroute)
    monkeypatch.setattr(import_module("maxconn.net.mtr"), "ping", fake_ping)

    hops: dict[int, WinMTRHop] = {}
    probe_mtr_once("8.8.8.8", hops, timeout=1.0)

    assert hops[1].host == "192.0.2.1"
    assert hops[2].host == "8.8.8.8"


def test_render_mtr_table_matches_winmtr_style_columns():
    hops = {
        1: WinMTRHop(index=1, host="192.168.1.1", sent=10, received=10, times=[0.001]),
        2: WinMTRHop(index=2, host="8.8.8.8", sent=10, received=8, times=[0.010, 0.020]),
    }

    table = render_mtr_table(hops)

    assert "#  Loss%  Sent  Avg  Host" in table
    assert "1  0%" in table
    assert "10" in table
    assert "1ms" in table
    assert "192.168.1.1" in table
    assert "2  20%" in table
    assert "15ms" in table
    assert "8.8.8.8" in table
