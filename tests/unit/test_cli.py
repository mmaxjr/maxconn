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
