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
    assert "maxconn 0.1.8" in capsys.readouterr().out


def test_cli_prints_package_version_from_sys_argv(monkeypatch, capsys):
    monkeypatch.setattr(maxconn.cli.sys, "argv", ["maxconn", "--version"])

    exit_code = maxconn.cli.main()

    assert exit_code == 0
    assert "maxconn 0.1.8" in capsys.readouterr().out


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


def test_cli_traceroute_prints_hops(monkeypatch, capsys):
    class Hop:
        hop = 1
        address = "192.0.2.1"
        raw = "1 192.0.2.1"

    class Result:
        returncode = 0
        error = ""

        def __init__(self):
            self.hops = [Hop()]

    monkeypatch.setattr(maxconn.cli.maxconn, "traceroute", lambda host, timeout=30.0: Result())

    exit_code = maxconn.cli.main(["traceroute", "192.0.2.1", "--timeout", "5"])

    assert exit_code == 0
    assert "1 192.0.2.1" in capsys.readouterr().out


def test_cli_mtr_prints_summary(monkeypatch, capsys):
    def fake_run_mtr_table(
        host,
        count=None,
        timeout=1.0,
        trace_timeout=30.0,
        rediscover_every=None,
        interval=1.0,
        output="table",
        clear=True,
    ):
        assert count == 5
        assert trace_timeout == 30.0
        assert rediscover_every is None
        assert interval == 0.0
        assert output == "table"
        assert clear is True
        return (
            "Hostname                         Nr  Loss%  Sent  Recv  Best  Avg   Worst  Last\n"
            "192.0.2.1                        1   20     5     4     10    15    20     18"
        )

    monkeypatch.setattr(maxconn.cli, "run_mtr_table", fake_run_mtr_table)

    exit_code = maxconn.cli.main(
        ["mtr", "192.0.2.1", "--count", "5", "--timeout", "1", "--interval", "0"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Hostname" in output
    assert "Loss%" in output
    assert "192.0.2.1" in output


def test_cli_mtr_can_print_json(monkeypatch, capsys):
    def fake_run_mtr_table(
        host,
        count=None,
        timeout=1.0,
        trace_timeout=30.0,
        rediscover_every=None,
        interval=1.0,
        output="table",
        clear=True,
    ):
        assert output == "json"
        return '{"hops": []}'

    monkeypatch.setattr(maxconn.cli, "run_mtr_table", fake_run_mtr_table)

    exit_code = maxconn.cli.main(["mtr", "192.0.2.1", "--count", "1", "--json"])

    assert exit_code == 0
    assert '{"hops": []}' in capsys.readouterr().out


def test_cli_mtr_can_export_output(monkeypatch, tmp_path):
    export_path = tmp_path / "mtr.txt"

    def fake_run_mtr_table(
        host,
        count=None,
        timeout=1.0,
        trace_timeout=30.0,
        rediscover_every=None,
        interval=1.0,
        output="table",
        clear=True,
    ):
        assert clear is False
        return "mtr report"

    monkeypatch.setattr(maxconn.cli, "run_mtr_table", fake_run_mtr_table)

    exit_code = maxconn.cli.main(
        ["mtr", "192.0.2.1", "--count", "1", "--export", str(export_path), "--no-clear"]
    )

    assert exit_code == 0
    assert export_path.read_text() == "mtr report"


def test_cli_snmp_get_prints_value(monkeypatch, capsys):
    class Result:
        oid = "1.3.6.1.2.1.1.5.0"
        value = "router-01"

    class Client:
        def __init__(self, host, community="public", port=161, timeout=2.0):
            self.host = host
            self.community = community
            self.port = port
            self.timeout = timeout

        def get(self, oid):
            return Result()

    monkeypatch.setattr(maxconn.cli, "SNMPClient", Client)

    exit_code = maxconn.cli.main(
        ["snmp", "get", "192.0.2.1", "1.3.6.1.2.1.1.5.0", "--community", "private"]
    )

    assert exit_code == 0
    assert "1.3.6.1.2.1.1.5.0 = router-01" in capsys.readouterr().out


def test_cli_snmp_walk_prints_values(monkeypatch, capsys):
    class Client:
        def __init__(self, host, community="public", port=161, timeout=2.0):
            pass

        def walk(self, oid, limit=100):
            class First:
                oid = "1.3.6.1.2.1.1.1.0"
                value = "description"

            class Second:
                oid = "1.3.6.1.2.1.1.5.0"
                value = "router-01"

            return [First(), Second()]

    monkeypatch.setattr(maxconn.cli, "SNMPClient", Client)

    exit_code = maxconn.cli.main(["snmp", "walk", "192.0.2.1", "1.3.6.1.2.1.1", "--limit", "10"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "description" in output
    assert "router-01" in output


def test_cli_sftp_ls_prints_remote_names(monkeypatch, capsys):
    class Client:
        def listdir(self, path):
            assert path == "/configs"
            return ["startup.cfg", "backup.cfg"]

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    exit_code = maxconn.cli.main(
        ["sftp", "ls", "192.0.2.10", "/configs", "--username", "admin", "--password", "secret"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "startup.cfg" in output
    assert "backup.cfg" in output


def test_cli_sftp_get_downloads_file(monkeypatch, tmp_path):
    target = tmp_path / "startup.cfg"
    calls = []

    class Client:
        def download(self, remote, local):
            calls.append((remote, local))

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    exit_code = maxconn.cli.main(
        [
            "sftp",
            "get",
            "192.0.2.10",
            "/remote/startup.cfg",
            str(target),
            "--username",
            "admin",
            "--password",
            "secret",
        ]
    )

    assert exit_code == 0
    assert calls == [("/remote/startup.cfg", str(target))]


def test_cli_sftp_put_uploads_file(monkeypatch, tmp_path):
    source = tmp_path / "startup.cfg"
    source.write_text("config")
    calls = []

    class Client:
        def upload(self, local, remote):
            calls.append((local, remote))

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    exit_code = maxconn.cli.main(
        [
            "sftp",
            "put",
            "192.0.2.10",
            str(source),
            "/remote/startup.cfg",
            "--username",
            "admin",
            "--password",
            "secret",
        ]
    )

    assert exit_code == 0
    assert calls == [(str(source), "/remote/startup.cfg")]


def test_cli_sftp_stat_prints_size(monkeypatch, capsys):
    class Attrs:
        size = 4096
        permissions = 0o644

    class Client:
        def stat(self, path):
            assert path == "/remote/startup.cfg"
            return Attrs()

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    exit_code = maxconn.cli.main(
        ["sftp", "stat", "192.0.2.10", "/remote/startup.cfg", "--username", "admin"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "size=4096" in output
    assert "permissions=0o644" in output


def test_cli_sftp_mkdir_rm_and_rename_call_client(monkeypatch):
    calls = []

    class Client:
        def mkdir(self, path):
            calls.append(("mkdir", path))

        def remove(self, path):
            calls.append(("remove", path))

        def rename(self, old_path, new_path):
            calls.append(("rename", old_path, new_path))

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    assert maxconn.cli.main(["sftp", "mkdir", "192.0.2.10", "/new", "--username", "admin"]) == 0
    assert maxconn.cli.main(["sftp", "rm", "192.0.2.10", "/old.cfg", "--username", "admin"]) == 0
    assert (
        maxconn.cli.main(
            ["sftp", "rename", "192.0.2.10", "/a.cfg", "/b.cfg", "--username", "admin"]
        )
        == 0
    )

    assert calls == [
        ("mkdir", "/new"),
        ("remove", "/old.cfg"),
        ("rename", "/a.cfg", "/b.cfg"),
    ]


def test_cli_doctor_prints_environment(capsys):
    exit_code = maxconn.cli.main(["doctor"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "maxconn=" in output
    assert "python=" in output
    assert "platform=" in output
    assert "ping=" in output
