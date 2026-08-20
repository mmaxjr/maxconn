from __future__ import annotations

import inspect

from maxconn.ui import shell
from maxconn.ui.theme import get_theme


def test_cli_commands_is_derived_from_commands_registry_not_hand_duplicated():
    # CLI_COMMANDS used to be a second, separately hand-typed set that had
    # to be kept in sync with COMMANDS by hand every time a command was
    # added - deriving it once from the same registry makes that class of
    # drift impossible.
    assert shell.CLI_COMMANDS == set(shell.COMMANDS) - shell.SPECIAL_COMMANDS
    assert "hosts" in shell.CLI_COMMANDS  # a real CLI-dispatched command
    assert "theme" not in shell.CLI_COMMANDS  # has its own bespoke handling


def test_cli_commands_includes_every_top_level_maxconn_command():
    # Regression: COMMANDS was hand-maintained and drifted - backup, diff,
    # inventory, audit, config, and completion were all added to the real
    # CLI's dispatch table across several sessions but never added here, so
    # none of them were reachable (or tab-completable) from inside
    # `maxconn start`. Cross-check against the actual dispatch table so this
    # can't silently drift again.
    from maxconn.cli import _dispatch_table

    # "start" itself is excluded on purpose - launching a nested interactive
    # shell from inside the shell isn't a meaningful action.
    real_commands = set(_dispatch_table().keys()) - {"start"}
    missing = real_commands - set(shell.COMMANDS) - shell.SPECIAL_COMMANDS
    assert not missing, f"maxconn start is missing these real CLI commands: {missing}"


def test_run_command_has_no_unreachable_preview_fallback():
    # Every name in COMMANDS is either specially handled above or lands in
    # CLI_COMMANDS by construction, so the old "[preview] executaria: ..."
    # branch could never actually run - dead code, now removed.
    source = inspect.getsource(shell.run_command)
    assert "[preview]" not in source


def test_shell_ssh_dispatches_to_maxconn_cli(monkeypatch):
    calls = []

    def fake_main(argv):
        calls.append(argv)
        return 0

    monkeypatch.setattr(shell, "_run_maxconn_cli", fake_main)

    signal = shell.run_command(
        "ssh",
        ["bgp-view"],
        get_theme("plain"),
        False,
        "ssh bgp-view",
    )

    assert signal == shell.CONTINUE
    assert calls == [["ssh", "bgp-view"]]


def test_shell_ssh_without_host_prints_usage(capsys):
    signal = shell.run_command(
        "ssh",
        [],
        get_theme("plain"),
        False,
        "ssh",
    )

    assert signal == shell.CONTINUE
    assert "uso: ssh <host-salvo|host>" in capsys.readouterr().out


def test_shell_keeps_running_when_cli_connection_fails(monkeypatch, capsys):
    from maxconn.exceptions import ProtocolError

    def fake_main(argv):
        raise ProtocolError("Connection closed by remote host")

    monkeypatch.setattr(shell, "_run_maxconn_cli", fake_main)

    signal = shell.run_command(
        "ssh",
        ["bgp-view"],
        get_theme("plain"),
        False,
        "ssh bgp-view",
    )

    captured = capsys.readouterr()
    assert signal == shell.CONTINUE
    assert "Error: Connection closed by remote host" in captured.err


def test_shell_open_uses_saved_host_protocol(monkeypatch, tmp_path):
    from maxconn.hosts import HostEntry, HostStore

    calls = []
    store = HostStore(base_dir=tmp_path)
    store.add(
        HostEntry(
            name="olt-telnet",
            host="10.0.0.3",
            port=23,
            protocol="telnet",
            username="admin",
        )
    )

    monkeypatch.setattr(shell, "_host_store", lambda: store)
    monkeypatch.setattr(shell, "_run_maxconn_cli", lambda argv: calls.append(argv) or 0)

    signal = shell.run_command(
        "open",
        ["olt-telnet"],
        get_theme("plain"),
        False,
        "open olt-telnet",
    )

    assert signal == shell.CONTINUE
    assert calls == [["telnet", "olt-telnet"]]


def test_shell_help_does_not_show_preview_only_commands(capsys):
    # backup/diff/inventory used to be the go-to example of not-yet-real
    # commands here - now that they're real (and in COMMANDS), the guard
    # this test exists for (help must not show anything outside COMMANDS)
    # needs a name that's guaranteed to never be a real maxconn command.
    signal = shell.run_command(
        "help",
        [],
        get_theme("plain"),
        False,
        "help",
    )

    output = capsys.readouterr().out
    assert signal == shell.CONTINUE
    assert "not-a-real-maxconn-command" not in output
    assert {line.split()[0] for line in output.splitlines() if line.strip()} <= set(shell.COMMANDS)


def test_shell_dispatches_real_cli_commands(monkeypatch):
    calls = []
    monkeypatch.setattr(shell, "_run_maxconn_cli", lambda argv: calls.append(argv) or 0)

    signal = shell.run_command(
        "hosts",
        ["list"],
        get_theme("plain"),
        False,
        "hosts list",
    )

    assert signal == shell.CONTINUE
    assert calls == [["hosts", "list"]]
