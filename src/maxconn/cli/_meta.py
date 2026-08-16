from __future__ import annotations

import argparse
import json
import sys

import maxconn
from maxconn import cli as _cli


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("selftest", help="run quick local CLI checks")
    subparsers.add_parser("start", help="launch the interactive maxconn shell")

    completion_command = subparsers.add_parser("completion", help="print a shell completion script")
    completion_command.add_argument("shell", choices=("bash", "zsh", "powershell"), nargs="?")
    completion_command.add_argument("--_list", nargs="*", dest="list_path", help=argparse.SUPPRESS)

    config_command = subparsers.add_parser("config", help="manage local CLI defaults")
    config_subcommands = config_command.add_subparsers(dest="config_action", required=True)
    config_set = config_subcommands.add_parser("set", help="set a default value")
    config_set.add_argument("key", choices=_cli.ALLOWED_CONFIG_KEYS)
    config_set.add_argument("value")
    config_get = config_subcommands.add_parser("get", help="print a default value")
    config_get.add_argument("key", choices=_cli.ALLOWED_CONFIG_KEYS)
    config_unset = config_subcommands.add_parser("unset", help="remove a default value")
    config_unset.add_argument("key", choices=_cli.ALLOWED_CONFIG_KEYS)
    config_subcommands.add_parser("list", help="list all default values")


def dispatch_selftest(args: argparse.Namespace) -> int:
    json.loads(json.dumps({"ok": True}))
    print(f"maxconn={maxconn.__version__}")
    print("import=ok")
    print("json=ok")
    print("cli=ok")
    return 0


def dispatch_start(args: argparse.Namespace) -> int:
    from maxconn.ui.shell import main as shell_main

    return shell_main()


def dispatch_completion(args: argparse.Namespace) -> int:
    from maxconn.completion import (
        build_command_tree,
        candidates_for_path,
        render_bash,
        render_powershell,
        render_zsh,
    )

    tree = build_command_tree(_cli._build_parser())
    if args.list_path is not None:
        for candidate in candidates_for_path(tree, args.list_path):
            print(candidate)
        return 0
    if not args.shell:
        raise ValueError("completion requires a shell: bash, zsh, or powershell")
    renderer = {"bash": render_bash, "zsh": render_zsh, "powershell": render_powershell}[args.shell]
    print(renderer(tree))
    return 0


def dispatch_config(args: argparse.Namespace) -> int:
    store = _cli._config_store()
    if args.config_action == "set":
        store.set(args.key, args.value)
        print(f"set {args.key} = {args.value}")
        return 0
    if args.config_action == "get":
        value = store.get(args.key)
        if value is None:
            print(f"{args.key} is not set", file=sys.stderr)
            return 1
        print(value)
        return 0
    if args.config_action == "unset":
        store.unset(args.key)
        print(f"unset {args.key}")
        return 0
    if args.config_action == "list":
        data = store.load()
        if not data:
            print("no config values set")
            return 0
        for key, value in sorted(data.items()):
            print(f"{key} = {value}")
        return 0
    raise AssertionError(f"unhandled config action: {args.config_action}")
