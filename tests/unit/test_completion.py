from __future__ import annotations

import argparse

from maxconn.completion import (
    build_command_tree,
    candidates_for_path,
    render_bash,
    render_powershell,
    render_zsh,
)


def _sample_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maxconn")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="protocol", required=True)

    ping = subparsers.add_parser("ping")
    ping.add_argument("host")
    ping.add_argument("--timeout", type=float)

    hosts = subparsers.add_parser("hosts")
    hosts_sub = hosts.add_subparsers(dest="hosts_action", required=True)
    hosts_add = hosts_sub.add_parser("add")
    hosts_add.add_argument("--host", required=True)
    hosts_add.add_argument("--port", type=int)
    hosts_sub.add_parser("list")

    return parser


def test_build_command_tree_collects_top_level_flags_and_subcommands():
    tree = build_command_tree(_sample_parser())

    assert "--version" in tree["flags"]
    assert set(tree["subcommands"].keys()) == {"ping", "hosts"}


def test_build_command_tree_collects_flags_on_a_subcommand():
    tree = build_command_tree(_sample_parser())

    assert "--timeout" in tree["subcommands"]["ping"]["flags"]
    assert "-h" not in tree["subcommands"]["ping"]["flags"]
    assert "--help" not in tree["subcommands"]["ping"]["flags"]


def test_build_command_tree_recurses_into_nested_subparsers():
    tree = build_command_tree(_sample_parser())

    hosts_subcommands = tree["subcommands"]["hosts"]["subcommands"]
    assert set(hosts_subcommands.keys()) == {"add", "list"}
    assert "--host" in hosts_subcommands["add"]["flags"]
    assert "--port" in hosts_subcommands["add"]["flags"]


def test_candidates_for_path_at_root_lists_top_level_subcommands_and_flags():
    tree = build_command_tree(_sample_parser())

    candidates = candidates_for_path(tree, [])

    assert "ping" in candidates
    assert "hosts" in candidates
    assert "--version" in candidates


def test_candidates_for_path_descends_into_nested_subcommands():
    tree = build_command_tree(_sample_parser())

    candidates = candidates_for_path(tree, ["hosts"])
    assert set(candidates) == {"add", "list"}

    candidates = candidates_for_path(tree, ["hosts", "add"])
    assert "--host" in candidates
    assert "--port" in candidates


def test_candidates_for_path_returns_empty_for_an_unknown_path():
    tree = build_command_tree(_sample_parser())

    assert candidates_for_path(tree, ["does-not-exist"]) == []


def test_render_bash_mentions_the_program_name():
    tree = build_command_tree(_sample_parser())
    script = render_bash(tree, prog="maxconn")

    assert "maxconn" in script
    assert "complete -F" in script


def test_render_zsh_wraps_bashcompinit():
    tree = build_command_tree(_sample_parser())
    script = render_zsh(tree, prog="maxconn")

    assert "bashcompinit" in script
    assert "maxconn" in script


def test_render_powershell_registers_an_argument_completer():
    tree = build_command_tree(_sample_parser())
    script = render_powershell(tree, prog="maxconn")

    assert "Register-ArgumentCompleter" in script
    assert "maxconn" in script
