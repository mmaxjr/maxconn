import json
import threading
import time

import maxconn.cli
from maxconn.exceptions import ConnectionTimeoutError, ProtocolError
from maxconn.hosts import HostEntry, HostStore
from maxconn.ui.theme import get_theme


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

    def read_until(self, marker, timeout=10.0):
        return ""


class FakePromptConnection(FakeConnection):
    def __init__(self):
        self.prompts = []

    def read_until(self, marker, timeout=10.0):
        return "JUNOS 13.3R4.6 built 2014-09-18 15:10:39 UTC\nbgp_view@lg.sp.itx.br>"

    def run(self, command, prompt_markers=None, timeout=None):
        self.command = command
        self.prompts.append(prompt_markers)

        class Result:
            text = "routes...\nbgp_view@lg.sp.itx.br>"
            ok = True

        return Result()


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


def test_cli_ssh_can_resolve_saved_host_alias(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="olt-01",
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
            profile="huawei",
        )
    )
    calls = {}

    def fake_connect(host, **kwargs):
        calls["host"] = host
        calls["kwargs"] = kwargs
        return FakeConnection()

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    assert maxconn.cli.main(["ssh", "olt-01", "--command", "show version"]) == 0

    assert "device output" in capsys.readouterr().out
    assert calls["host"] == "10.0.0.1"
    assert calls["kwargs"]["username"] == "admin"
    assert calls["kwargs"]["port"] == 22


def test_cli_ssh_accepts_username_at_host_syntax(monkeypatch, capsys):
    calls = {}

    def fake_connect(host, **kwargs):
        calls["host"] = host
        calls["kwargs"] = kwargs
        return FakeConnection()

    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    assert (
        maxconn.cli.main(
            [
                "ssh",
                "bgp_view@177.84.161.226",
                "--password",
                "public-view-password",
                "--command",
                "show version",
            ]
        )
        == 0
    )

    assert "device output" in capsys.readouterr().out
    assert calls["host"] == "177.84.161.226"
    assert calls["kwargs"]["username"] == "bgp_view"


def test_cli_ssh_without_command_opens_interactive_session(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="bgp-view",
            host="177.84.161.226",
            port=22,
            protocol="ssh",
            username="bgp_view",
            password="public-view-password",
        )
    )
    inputs = iter(["show version", "exit"])
    connection = FakeConnection()
    calls = {}

    def fake_connect(host, **kwargs):
        calls["host"] = host
        calls["kwargs"] = kwargs
        return connection

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli, "_interactive_input", lambda prompt: next(inputs))
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    assert maxconn.cli.main(["ssh", "bgp-view"]) == 0

    output = capsys.readouterr().out
    assert "connected: bgp-view (177.84.161.226) ssh" in output
    assert "device output" in output
    assert connection.command == "show version"
    assert calls["host"] == "177.84.161.226"
    assert calls["kwargs"]["password"] == "public-view-password"


def test_cli_prints_clean_error_when_connection_protocol_fails(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="bgp-view",
            host="177.84.161.226",
            port=22,
            protocol="ssh",
            username="bgp_view",
            password="public-view-password",
        )
    )

    def fake_connect(host, **kwargs):
        raise ProtocolError("Connection closed by remote host")

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    assert maxconn.cli.main(["ssh", "bgp-view"]) == 1

    captured = capsys.readouterr()
    assert "Error: Connection closed by remote host" in captured.err
    assert "Traceback" not in captured.err


def test_cli_interactive_session_uses_device_prompt(monkeypatch, capsys):
    inputs = iter(["show route", "exit"])
    connection = FakePromptConnection()

    monkeypatch.setattr(maxconn.cli, "_interactive_input", lambda prompt: connection.prompts.append(prompt) or next(inputs))

    exit_code = maxconn.cli._run_interactive_connection(
        connection,
        label="bgp-view",
        host="177.84.161.226",
        protocol="ssh",
        prompt_markers=(">", "#"),
        timeout=10.0,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "JUNOS 13.3R4.6" in output
    assert "bgp_view@lg.sp.itx.br>" in output
    assert "routes..." in output
    assert "bgp_view@lg.sp.itx.br> " in connection.prompts


def test_cli_interactive_session_uses_saved_theme_for_device_prompt(monkeypatch, capsys):
    inputs = iter(["exit"])
    connection = FakePromptConnection()

    monkeypatch.setattr(maxconn.cli, "_interactive_input", lambda prompt: connection.prompts.append(prompt) or next(inputs))
    monkeypatch.setattr(maxconn.cli, "_interactive_theme", lambda: (get_theme("matrix"), True))

    exit_code = maxconn.cli._run_interactive_connection(
        connection,
        label="bgp-view",
        host="177.84.161.226",
        protocol="ssh",
        prompt_markers=(">", "#"),
        timeout=10.0,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "\x1b[" in output
    assert "\x1b[" in connection.prompts[0]
    assert "bgp_view@lg.sp.itx.br>" in connection.prompts[0]


def test_cli_ssh_save_records_host_and_recent(monkeypatch, tmp_path):
    store = HostStore(base_dir=tmp_path)

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", lambda host, **kwargs: FakeConnection())

    assert (
        maxconn.cli.main(
            [
                "ssh",
                "10.0.0.1",
                "--username",
                "admin",
                "--command",
                "show version",
                "--save",
                "olt-01",
                "--profile",
                "huawei",
                "--tags",
                "olt",
            ]
        )
        == 0
    )

    assert store.get("olt-01").host == "10.0.0.1"
    assert store.list_seen()[0].host == "10.0.0.1"


def test_cli_ssh_save_preserves_explicit_port_zero(monkeypatch, tmp_path):
    # Regression: `resolved_port or default_port` treats an explicit
    # `--port 0` the same as "no port given" (0 is falsy in Python) and
    # silently substitutes the protocol default instead.
    store = HostStore(base_dir=tmp_path)

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", lambda host, **kwargs: FakeConnection())

    assert (
        maxconn.cli.main(
            [
                "ssh",
                "10.0.0.1",
                "--username",
                "admin",
                "--port",
                "0",
                "--command",
                "show version",
                "--save",
                "olt-01",
            ]
        )
        == 0
    )

    assert store.get("olt-01").port == 0
    assert store.list_seen()[0].port == 0


def test_cli_ssh_save_password_is_explicit(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(maxconn.cli.maxconn, "connect", lambda host, **kwargs: FakeConnection())

    assert (
        maxconn.cli.main(
            [
                "ssh",
                "10.0.0.1",
                "--username",
                "admin",
                "--password",
                "secret",
                "--command",
                "show version",
                "--save",
                "olt-01",
                "--save-password",
            ]
        )
        == 0
    )

    assert store.get("olt-01").password == "secret"
    captured = capsys.readouterr()
    assert "password saved" in captured.err
    assert "secret" not in captured.out


def test_cli_prints_package_version(capsys):
    exit_code = maxconn.cli.main(["--version"])

    assert exit_code == 0
    assert f"maxconn {maxconn.__version__}" in capsys.readouterr().out


def test_cli_prints_package_version_from_sys_argv(monkeypatch, capsys):
    monkeypatch.setattr(maxconn.cli.sys, "argv", ["maxconn", "--version"])

    exit_code = maxconn.cli.main()

    assert exit_code == 0
    assert f"maxconn {maxconn.__version__}" in capsys.readouterr().out


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


def test_cli_ping_can_print_json_and_export(monkeypatch, capsys, tmp_path):
    class FakePingResult:
        host = "192.0.2.1"
        reachable = True
        elapsed = 0.025
        returncode = 0
        output = "ok"
        error = ""

    export_path = tmp_path / "ping.json"
    calls = {}

    def fake_ping(host, timeout=2.0, count=1):
        calls["count"] = count
        return FakePingResult()

    monkeypatch.setattr(maxconn.cli.maxconn, "ping", fake_ping)

    exit_code = maxconn.cli.main(
        ["ping", "192.0.2.1", "--json", "--export", str(export_path), "--retries", "3"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["reachable"] is True
    assert payload["returncode"] == 0
    assert json.loads(export_path.read_text())["host"] == "192.0.2.1"
    assert calls["count"] == 3


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


def test_cli_scan_can_print_json(monkeypatch, capsys):
    class FakeScanResult:
        host = "192.0.2.1"
        port = 22
        open = True
        elapsed = 0.01
        error = ""

    monkeypatch.setattr(maxconn.cli.maxconn, "scan", lambda *args, **kwargs: [FakeScanResult()])

    exit_code = maxconn.cli.main(["scan", "192.0.2.1", "--ports", "22", "--output", "json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["ports"][0]["port"] == 22


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


def test_cli_traceroute_can_print_json(monkeypatch, capsys):
    class Hop:
        hop = 1
        address = "192.0.2.1"
        raw = "1 192.0.2.1"

    class Result:
        host = "example.com"
        returncode = 0
        output = "trace"
        error = ""

        def __init__(self):
            self.hops = [Hop()]

    monkeypatch.setattr(maxconn.cli.maxconn, "traceroute", lambda host, timeout=30.0: Result())

    exit_code = maxconn.cli.main(["traceroute", "example.com", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hops"][0]["address"] == "192.0.2.1"


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


def test_cli_mtr_accepts_output_json_alias(monkeypatch, capsys):
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

    exit_code = maxconn.cli.main(["mtr", "192.0.2.1", "--count", "1", "--output", "json"])

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


def test_cli_mtr_export_uses_utf8_regardless_of_system_locale(monkeypatch, tmp_path):
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
        return "mtr report: ☎ 100% loss"  # U+260E, outside cp1252 entirely

    monkeypatch.setattr(maxconn.cli, "run_mtr_table", fake_run_mtr_table)

    exit_code = maxconn.cli.main(["mtr", "192.0.2.1", "--count", "1", "--export", str(export_path)])

    assert exit_code == 0
    assert export_path.read_text(encoding="utf-8") == "mtr report: ☎ 100% loss"


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


def test_cli_snmp_get_can_retry_and_print_json(monkeypatch, capsys):
    class Result:
        oid = "1.3.6.1.2.1.1.5.0"
        value = "router-01"

    class Client:
        attempts = 0

        def __init__(self, host, community="public", port=161, timeout=2.0):
            pass

        def get(self, oid):
            Client.attempts += 1
            if Client.attempts == 1:
                raise TimeoutError("timed out")
            return Result()

    monkeypatch.setattr(maxconn.cli, "SNMPClient", Client)

    exit_code = maxconn.cli.main(
        ["snmp", "get", "192.0.2.1", "1.3.6.1.2.1.1.5.0", "--json", "--retries", "2"]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["value"] == "router-01"
    assert Client.attempts == 2


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


def test_cli_snmp_walk_can_print_json(monkeypatch, capsys):
    class Client:
        def __init__(self, host, community="public", port=161, timeout=2.0):
            pass

        def walk(self, oid, limit=100):
            class Result:
                oid = "1.3.6.1.2.1.1.1.0"
                value = "description"

            return [Result()]

    monkeypatch.setattr(maxconn.cli, "SNMPClient", Client)

    exit_code = maxconn.cli.main(["snmp", "walk", "192.0.2.1", "1.3.6.1.2.1.1", "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["value"] == "description"


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


def test_cli_sftp_stat_can_print_json(monkeypatch, capsys):
    class Attrs:
        size = 4096
        uid = 1000
        gid = 1000
        permissions = 0o644
        atime = 1
        mtime = 2

    class Client:
        def stat(self, path):
            return Attrs()

        def close(self):
            pass

    monkeypatch.setattr(maxconn.cli.maxconn, "connect_sftp", lambda host, **kwargs: Client())

    exit_code = maxconn.cli.main(
        ["sftp", "stat", "192.0.2.10", "/remote/startup.cfg", "--username", "admin", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["permissions"] == "0o644"
    assert payload["path"] == "/remote/startup.cfg"


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


def test_cli_hosts_add_and_list(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: HostStore(base_dir=tmp_path))

    assert (
        maxconn.cli.main(
            [
                "hosts",
                "add",
                "olt-01",
                "--host",
                "10.0.0.1",
                "--port",
                "22",
                "--protocol",
                "ssh",
                "--username",
                "admin",
                "--profile",
                "huawei",
                "--tags",
                "olt,pop-centro",
            ]
        )
        == 0
    )

    assert maxconn.cli.main(["hosts", "list"]) == 0
    output = capsys.readouterr().out
    assert "NAME" in output
    assert "HOST/IP" in output
    assert "olt-01" in output
    assert "10.0.0.1" in output


def test_cli_hosts_add_can_save_password_explicitly(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert (
        maxconn.cli.main(
            [
                "hosts",
                "add",
                "bgp-view",
                "--host",
                "177.84.161.226",
                "--port",
                "22",
                "--protocol",
                "ssh",
                "--username",
                "bgp_view",
                "--password",
                "public-view-password",
                "--save-password",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert store.get("bgp-view").password == "public-view-password"
    assert "password saved" in captured.err
    assert "public-view-password" not in captured.out


def test_cli_hosts_show_and_remove(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="olt-01",
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
        )
    )
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "show", "olt-01"]) == 0
    assert "10.0.0.1" in capsys.readouterr().out

    assert maxconn.cli.main(["hosts", "remove", "olt-01"]) == 0
    assert store.list() == []


def test_write_output_export_uses_utf8_regardless_of_system_locale(tmp_path):
    # Path.write_text() without an explicit encoding uses
    # locale.getpreferredencoding(), which on Windows is often a legacy
    # codepage (cp1252/cp850) that cannot represent every character -
    # --export must not depend on the OS locale to avoid data loss/crashes.
    export_path = tmp_path / "out.txt"
    text_with_non_latin1_char = "device reply: ☎ ok"  # U+260E, outside cp1252 entirely

    maxconn.cli._write_output(text_with_non_latin1_char, str(export_path))

    assert export_path.read_text(encoding="utf-8") == text_with_non_latin1_char


def test_cli_hosts_show_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "show", "does-not-exist"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_hosts_remove_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "remove", "does-not-exist"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_hosts_test_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "test", "does-not-exist"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_hosts_save_recent_out_of_range_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "save-recent", "1", "--name", "olt-01"]) == 1
    assert "out of range" in capsys.readouterr().err


def test_cli_ssh_resolves_saved_host_when_given_as_user_at_alias(monkeypatch, tmp_path, capsys):
    # Regression: `maxconn ssh admin@bgp-view` must resolve the saved host
    # "bgp-view", not silently skip it because the lookup used the raw
    # "admin@bgp-view" string instead of the already-split alias.
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="bgp-view",
            host="177.84.161.226",
            port=22,
            protocol="ssh",
            username="bgp_view",
        )
    )
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    calls = []

    def fake_connect(host, *, protocol, username, password, port, timeout):
        calls.append({"host": host, "username": username, "port": port})
        raise ConnectionTimeoutError("simulated: test never hits the network")

    monkeypatch.setattr(maxconn.cli.maxconn, "connect", fake_connect)

    maxconn.cli.main(["ssh", "admin@bgp-view", "--command", "show version"])

    assert calls == [{"host": "177.84.161.226", "username": "admin", "port": 22}]


def test_cli_hosts_recent_and_save_recent(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.record_seen("10.0.0.1", protocol="ssh", port=22, username="admin")
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "recent"]) == 0
    assert "10.0.0.1" in capsys.readouterr().out

    assert (
        maxconn.cli.main(
            [
                "hosts",
                "save-recent",
                "1",
                "--name",
                "olt-01",
                "--profile",
                "huawei",
                "--tags",
                "olt",
            ]
        )
        == 0
    )
    assert store.get("olt-01").host == "10.0.0.1"


def test_cli_hosts_test_scans_saved_host_port(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="olt-01",
            host="10.0.0.1",
            port=22,
            protocol="ssh",
            username="admin",
        )
    )
    calls = []

    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "scan",
        lambda host, *, ports, timeout, concurrency: calls.append((host, ports, timeout, concurrency))
        or [type("Result", (), {"open": True, "port": 22, "elapsed": 0.01})()],
    )

    assert maxconn.cli.main(["hosts", "test", "olt-01"]) == 0

    output = capsys.readouterr().out
    assert calls == [("10.0.0.1", [22], 1.0, 1)]
    assert "olt-01" in output
    assert "open" in output


def test_cli_hosts_test_all_tests_every_saved_host(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh"))
    store.add(HostEntry(name="olt-02", host="10.0.0.2", port=22, protocol="ssh"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "scan",
        lambda host, *, ports, timeout, concurrency: [
            type("Result", (), {"open": True, "port": ports[0], "elapsed": 0.01})()
        ],
    )

    assert maxconn.cli.main(["hosts", "test", "--all"]) == 0

    output = capsys.readouterr().out
    assert "olt-01" in output
    assert "olt-02" in output


def test_cli_hosts_test_tag_filters_by_tag(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh", tags=["core"]))
    store.add(HostEntry(name="olt-02", host="10.0.0.2", port=22, protocol="ssh", tags=["edge"]))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "scan",
        lambda host, *, ports, timeout, concurrency: [
            type("Result", (), {"open": True, "port": ports[0], "elapsed": 0.01})()
        ],
    )

    assert maxconn.cli.main(["hosts", "test", "--tag", "core"]) == 0

    output = capsys.readouterr().out
    assert "olt-01" in output
    assert "olt-02" not in output


def test_cli_hosts_test_all_returns_nonzero_when_any_host_is_closed(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)
    monkeypatch.setattr(
        maxconn.cli.maxconn,
        "scan",
        lambda host, *, ports, timeout, concurrency: [
            type("Result", (), {"open": False, "port": ports[0], "elapsed": 0.01})()
        ],
    )

    assert maxconn.cli.main(["hosts", "test", "--all"]) == 1


def test_cli_hosts_test_all_runs_scans_concurrently(monkeypatch, tmp_path, capsys):
    # Regression: hosts test --all/--tag used to scan hosts one at a time in
    # a plain for-loop, so N saved hosts took N * timeout in the worst case
    # instead of running in parallel like discover() already does.
    store = HostStore(base_dir=tmp_path)
    for i in range(5):
        store.add(HostEntry(name=f"olt-0{i}", host=f"10.0.0.{i}", port=22, protocol="ssh"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    started = threading.Event()
    max_concurrent = []
    active = []
    lock = threading.Lock()

    def fake_scan(host, *, ports, timeout, concurrency):
        with lock:
            active.append(1)
            max_concurrent.append(len(active))
        started.wait(timeout=2.0)
        with lock:
            active.pop()
        return [type("Result", (), {"open": True, "port": ports[0], "elapsed": 0.01})()]

    monkeypatch.setattr(maxconn.cli.maxconn, "scan", fake_scan)

    def release_soon():
        time.sleep(0.1)
        started.set()

    threading.Thread(target=release_soon).start()

    assert maxconn.cli.main(["hosts", "test", "--all"]) == 0

    assert max(max_concurrent) > 1


def test_cli_hosts_test_all_prints_results_in_host_name_order(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh"))
    store.add(HostEntry(name="olt-02", host="10.0.0.2", port=22, protocol="ssh"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    def fake_scan(host, *, ports, timeout, concurrency):
        # olt-01 finishes slower than olt-02, but output order must still
        # follow host order, not completion order.
        if host == "10.0.0.1":
            time.sleep(0.05)
        return [type("Result", (), {"open": True, "port": ports[0], "elapsed": 0.01})()]

    monkeypatch.setattr(maxconn.cli.maxconn, "scan", fake_scan)

    assert maxconn.cli.main(["hosts", "test", "--all"]) == 0

    output = capsys.readouterr().out
    assert output.index("olt-01") < output.index("olt-02")


def test_cli_hosts_edit_updates_only_given_fields(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh", username="admin", profile="huawei")
    )
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "edit", "olt-01", "--host", "10.0.0.2"]) == 0

    updated = store.get("olt-01")
    assert updated.host == "10.0.0.2"
    assert updated.username == "admin"
    assert updated.profile == "huawei"


def test_cli_hosts_set_is_an_alias_for_edit(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "set", "olt-01", "--tags", "core,pop"]) == 0

    assert store.get("olt-01").tags == ["core", "pop"]


def test_cli_hosts_edit_missing_name_prints_clean_error(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "edit", "does-not-exist", "--host", "10.0.0.9"]) == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_cli_hosts_export_and_import_round_trip(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path / "store-a")
    store.add(HostEntry(name="olt-01", host="10.0.0.1", port=22, protocol="ssh", tags=["core"]))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    export_path = tmp_path / "hosts-export.json"
    assert maxconn.cli.main(["hosts", "export", "--file", str(export_path)]) == 0
    assert export_path.exists()

    other_store = HostStore(base_dir=tmp_path / "store-b")
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: other_store)

    assert maxconn.cli.main(["hosts", "import", "--file", str(export_path)]) == 0
    assert other_store.get("olt-01").host == "10.0.0.1"
    assert other_store.get("olt-01").tags == ["core"]


def test_cli_hosts_list_json_includes_has_password_but_not_the_value(monkeypatch, tmp_path, capsys):
    store = HostStore(base_dir=tmp_path)
    store.add(HostEntry(name="bgp-view", host="10.0.0.1", port=22, protocol="ssh", password="topsecret"))
    monkeypatch.setattr(maxconn.cli, "_host_store", lambda: store)

    assert maxconn.cli.main(["hosts", "list", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["hosts"][0]["name"] == "bgp-view"
    assert payload["hosts"][0]["has_password"] is True
    assert "password" not in payload["hosts"][0]
    assert "topsecret" not in capsys.readouterr().out


def test_cli_doctor_prints_environment(capsys):
    exit_code = maxconn.cli.main(["doctor"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "maxconn=" in output
    assert "python=" in output
    assert "platform=" in output
    assert "ping=" in output


def test_cli_doctor_prints_local_checks_without_network_flag(capsys):
    exit_code = maxconn.cli.main(["doctor"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "maxconn_dir_writable=" in output
    assert "terminal_tty=" in output
    assert "terminal_color=" in output
    assert "dns=" not in output
    assert "internet=" not in output
    assert "pypi_latest=" not in output


def test_cli_doctor_network_runs_dns_internet_and_version_checks(monkeypatch, capsys):
    monkeypatch.setattr(maxconn.cli.doctor, "check_dns", lambda *a, **k: True)
    monkeypatch.setattr(maxconn.cli.doctor, "check_internet", lambda *a, **k: False)
    monkeypatch.setattr(maxconn.cli.doctor, "default_gateway", lambda *a, **k: "192.168.1.1")
    monkeypatch.setattr(maxconn.cli.doctor, "fetch_latest_pypi_version", lambda *a, **k: "99.0.0")

    exit_code = maxconn.cli.main(["doctor", "--network"])

    output = capsys.readouterr().out
    assert exit_code == 1  # internet check failed
    assert "dns=ok" in output
    assert "internet=fail" in output
    assert "gateway=192.168.1.1" in output
    assert "pypi_latest=99.0.0" in output
    assert "version_status=update-available" in output


def test_cli_doctor_network_handles_unknown_pypi_version(monkeypatch, capsys):
    monkeypatch.setattr(maxconn.cli.doctor, "check_dns", lambda *a, **k: True)
    monkeypatch.setattr(maxconn.cli.doctor, "check_internet", lambda *a, **k: True)
    monkeypatch.setattr(maxconn.cli.doctor, "default_gateway", lambda *a, **k: None)
    monkeypatch.setattr(maxconn.cli.doctor, "fetch_latest_pypi_version", lambda *a, **k: None)

    exit_code = maxconn.cli.main(["doctor", "--network"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "gateway=unknown" in output
    assert "pypi_latest=unknown" in output
    assert "version_status=unknown" in output


def test_cli_selftest_prints_basic_checks(capsys):
    exit_code = maxconn.cli.main(["selftest"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "import=ok" in output
    assert "json=ok" in output


def test_cli_completion_bash_prints_a_script(capsys):
    assert maxconn.cli.main(["completion", "bash"]) == 0

    output = capsys.readouterr().out
    assert "complete -F" in output
    assert "maxconn" in output


def test_cli_completion_zsh_prints_a_script(capsys):
    assert maxconn.cli.main(["completion", "zsh"]) == 0

    output = capsys.readouterr().out
    assert "bashcompinit" in output


def test_cli_completion_powershell_prints_a_script(capsys):
    assert maxconn.cli.main(["completion", "powershell"]) == 0

    output = capsys.readouterr().out
    assert "Register-ArgumentCompleter" in output


def test_cli_completion_without_shell_prints_clean_error(capsys):
    assert maxconn.cli.main(["completion"]) == 1
    assert "shell" in capsys.readouterr().err


def test_cli_completion_list_at_root_includes_top_level_commands(capsys):
    assert maxconn.cli.main(["completion", "--_list"]) == 0

    output = capsys.readouterr().out.splitlines()
    assert "hosts" in output
    assert "discover" in output
    assert "--version" in output


def test_cli_completion_list_descends_into_hosts_subcommands(capsys):
    assert maxconn.cli.main(["completion", "--_list", "hosts"]) == 0

    output = capsys.readouterr().out.splitlines()
    assert "add" in output
    assert "test" in output
    assert "export" in output


def test_cli_completion_list_shows_flags_for_a_leaf_subcommand(capsys):
    assert maxconn.cli.main(["completion", "--_list", "discover"]) == 0

    output = capsys.readouterr().out.splitlines()
    assert "--confirm" in output
    assert "--name-prefix" in output


def test_cli_prints_friendly_error(monkeypatch, capsys):
    def fake_scan(*args, **kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(maxconn.cli.maxconn, "scan", fake_scan)

    exit_code = maxconn.cli.main(["scan", "192.0.2.1", "--ports", "22"])

    assert exit_code == 1
    assert "Error: bad input" in capsys.readouterr().err
