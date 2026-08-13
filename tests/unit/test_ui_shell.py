from __future__ import annotations

from maxconn.ui import shell
from maxconn.ui.theme import get_theme


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
