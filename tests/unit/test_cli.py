import maxconn.cli


class FakeResult:
    text = "device output"
    ok = True


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def run(self, command, prompt_markers=None, timeout=None):
        self.command = command
        self.prompt_markers = prompt_markers
        self.timeout = timeout
        return FakeResult()


def test_cli_runs_command_and_prints_output(monkeypatch, capsys):
    calls = {}

    def fake_connect(host, **kwargs):
        calls["host"] = host
        calls["kwargs"] = kwargs
        return FakeConnection()

    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    exit_code = maxconn.cli.main(
        [
            "ssh",
            "192.0.2.10",
            "--username",
            "admin",
            "--password",
            "secret",
            "--command",
            "show version",
        ]
    )

    assert exit_code == 0
    assert "device output" in capsys.readouterr().out
    assert calls["host"] == "192.0.2.10"
    assert calls["kwargs"]["protocol"] == "ssh"


def test_cli_prints_package_version(capsys):
    exit_code = maxconn.cli.main(["--version"])

    assert exit_code == 0
    assert "maxconn 0.1.2" in capsys.readouterr().out


def test_cli_prints_package_version_from_sys_argv(monkeypatch, capsys):
    monkeypatch.setattr(maxconn.cli.sys, "argv", ["maxconn", "--version"])

    exit_code = maxconn.cli.main()

    assert exit_code == 0
    assert "maxconn 0.1.2" in capsys.readouterr().out


def test_cli_ping_prints_reachable_status(monkeypatch, capsys):
    class FakePingResult:
        host = "192.0.2.1"
        reachable = True
        elapsed = 0.025
        error = ""

    monkeypatch.setattr(maxconn.cli.maxconn, "ping", lambda host, timeout=2.0, count=1: FakePingResult())

    exit_code = maxconn.cli.main(["ping", "192.0.2.1", "--timeout", "1", "--count", "2"])

    assert exit_code == 0
    assert "192.0.2.1 reachable" in capsys.readouterr().out


def test_cli_scan_prints_open_ports(monkeypatch, capsys):
    class FakeScanResult:
        host = "192.0.2.1"
        port = 22
        open = True
        elapsed = 0.01
        error = ""

    calls = {}

    def fake_scan(host, *, ports, timeout=1.0, concurrency=100):
        calls["host"] = host
        calls["ports"] = ports
        calls["timeout"] = timeout
        calls["concurrency"] = concurrency
        return [FakeScanResult()]

    monkeypatch.setattr(maxconn.cli.maxconn, "scan", fake_scan)

    exit_code = maxconn.cli.main(
        ["scan", "192.0.2.1", "--ports", "22,80", "--timeout", "0.5", "--concurrency", "5"]
    )

    assert exit_code == 0
    assert "22 open" in capsys.readouterr().out
    assert calls == {
        "host": "192.0.2.1",
        "ports": [22, 80],
        "timeout": 0.5,
        "concurrency": 5,
    }
