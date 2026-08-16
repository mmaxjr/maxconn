from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from datetime import datetime

import maxconn
from maxconn import cli as _cli
from maxconn.history import format_history_csv, format_history_table, parse_since


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    history_command = subparsers.add_parser("history", help="manage local command history")
    history_subcommands = history_command.add_subparsers(dest="history_action", required=True)
    history_list = history_subcommands.add_parser("list", help="list command history")
    history_list.add_argument("--host")
    history_list.add_argument("--protocol", dest="history_protocol")
    history_list.add_argument("--limit", type=int, help="only show the N most recent entries")
    history_list.add_argument(
        "--since", help="only show entries at/after this time: today, yesterday, 24h, 7d, or an ISO date"
    )
    history_list.add_argument("--json", action="store_true", help="print JSON output")
    history_list.add_argument("--output", choices=("text", "json", "csv"), default="text")
    history_list.add_argument("--export", help="write the rendered output to a file")
    history_show = history_subcommands.add_parser("show", help="show one history entry")
    history_show.add_argument("id", type=int)
    history_replay = history_subcommands.add_parser("replay", help="re-run a stored history command")
    history_replay.add_argument("id", type=int)
    history_replay.add_argument("--username")
    history_replay.add_argument("--password")
    history_replay.add_argument("--ask-password", action="store_true")
    history_replay.add_argument("--timeout", type=float, default=10.0)
    history_subcommands.add_parser("clear", help="clear command history")


def dispatch(args: argparse.Namespace) -> int:
    store = _cli._history_store()
    if args.history_action == "list":
        entries = store.list()
        if args.host:
            entries = [entry for entry in entries if entry.host == args.host or entry.alias == args.host]
        if args.history_protocol:
            entries = [entry for entry in entries if entry.protocol == args.history_protocol.lower()]
        if args.since:
            since_dt = parse_since(args.since)
            entries = [entry for entry in entries if datetime.fromisoformat(entry.timestamp) >= since_dt]
        if args.limit is not None:
            entries = entries[-args.limit :]
        if _cli._is_json_output(args):
            _cli._json_output({"entries": [entry.__dict__ for entry in entries]}, args.export)
        elif args.output == "csv":
            _cli._write_output(format_history_csv(entries), args.export)
        else:
            _cli._write_output(format_history_table(entries), args.export)
        return 0
    if args.history_action == "show":
        print(json.dumps(store.get(args.id).__dict__, indent=2, default=str))
        return 0
    if args.history_action == "replay":
        entry = store.get(args.id)
        if not entry.command:
            raise ValueError(f"history entry {args.id} has no command to replay")
        if "<redacted>" in entry.command:
            print(
                "Warning: this command was stored with a secret redacted; the "
                "redacted placeholder is sent as-is, not the original value.",
                file=sys.stderr,
            )
        host_store = _cli._host_store()
        saved = None
        if entry.alias:
            try:
                saved = host_store.get(entry.alias)
            except KeyError:
                saved = None
        if saved is not None:
            resolved_host = saved.host
            resolved_port = saved.port
            resolved_protocol = saved.protocol
            resolved_username = args.username or saved.username
            resolved_password = args.password if args.password is not None else saved.password
        else:
            resolved_host = entry.host
            resolved_port = entry.port
            resolved_protocol = entry.protocol
            resolved_username = args.username or entry.username
            resolved_password = args.password
        if args.ask_password:
            resolved_password = getpass.getpass("Password: ")
        if not resolved_username:
            raise ValueError("--username is required to replay this entry (no saved host credentials)")
        started = time.monotonic()
        with maxconn.connect(
            resolved_host,
            protocol=resolved_protocol,
            username=resolved_username,
            password=resolved_password,
            port=resolved_port,
            timeout=args.timeout,
        ) as conn:
            result = conn.run(entry.command, timeout=args.timeout)
            print(result.text, end="" if result.text.endswith("\n") else "\n")
            store.record(
                alias=entry.alias,
                host=resolved_host,
                port=resolved_port,
                protocol=resolved_protocol,
                username=resolved_username,
                command=entry.command,
                ok=result.ok,
                exit_status=getattr(result, "exit_status", None),
                duration=time.monotonic() - started,
                origin="cli-replay",
            )
        return 0 if result.ok else 1
    if args.history_action == "clear":
        store.clear()
        print("history cleared")
        return 0
    raise AssertionError(f"unhandled history action: {args.history_action}")
