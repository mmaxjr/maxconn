from __future__ import annotations

import argparse
import getpass
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

import maxconn
from maxconn import cli as _cli
from maxconn.hosts import HostEntry, format_hosts_table, format_seen_hosts_table, parse_tags


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    hosts_command = subparsers.add_parser("hosts", help="manage local saved hosts")
    hosts_subcommands = hosts_command.add_subparsers(dest="hosts_action", required=True)
    hosts_add = hosts_subcommands.add_parser("add", help="save a local host entry")
    hosts_add.add_argument("name")
    hosts_add.add_argument("--host", required=True)
    hosts_add.add_argument("--port", type=int, required=True)
    hosts_add.add_argument("--protocol", choices=("ssh", "telnet"), required=True, dest="host_protocol")
    hosts_add.add_argument("--username")
    hosts_add.add_argument("--password")
    hosts_add.add_argument("--save-password", action="store_true")
    hosts_add.add_argument("--ask-password", action="store_true")
    hosts_add.add_argument("--profile")
    hosts_add.add_argument("--tags")
    hosts_add.add_argument("--notes")
    hosts_list = hosts_subcommands.add_parser("list", help="list saved hosts")
    hosts_list.add_argument("--json", action="store_true", help="print JSON output")
    hosts_show = hosts_subcommands.add_parser("show", help="show one saved host")
    hosts_show.add_argument("name")
    hosts_remove = hosts_subcommands.add_parser("remove", help="remove one saved host")
    hosts_remove.add_argument("name")
    hosts_test = hosts_subcommands.add_parser("test", help="test saved host(s)")
    hosts_test.add_argument("name", nargs="?", help="host name (omit with --all or --tag)")
    hosts_test.add_argument("--timeout", type=float, default=1.0)
    hosts_test.add_argument("--all", action="store_true", help="test every saved host")
    hosts_test.add_argument("--tag", help="test every saved host with this tag")
    hosts_subcommands.add_parser("recent", help="list recently used hosts")
    hosts_save_recent = hosts_subcommands.add_parser("save-recent", help="save a recently used host")
    hosts_save_recent.add_argument("id", type=int)
    hosts_save_recent.add_argument("--name", required=True)
    hosts_save_recent.add_argument("--profile")
    hosts_save_recent.add_argument("--tags")
    hosts_save_recent.add_argument("--notes")
    hosts_edit = hosts_subcommands.add_parser("edit", aliases=["set"], help="edit fields on a saved host")
    hosts_edit.add_argument("name")
    hosts_edit.add_argument("--host")
    hosts_edit.add_argument("--port", type=int)
    hosts_edit.add_argument("--protocol", choices=("ssh", "telnet"), dest="host_protocol")
    hosts_edit.add_argument("--username")
    hosts_edit.add_argument("--password")
    hosts_edit.add_argument("--save-password", action="store_true")
    hosts_edit.add_argument("--ask-password", action="store_true")
    hosts_edit.add_argument("--profile")
    hosts_edit.add_argument("--tags")
    hosts_edit.add_argument("--notes")
    hosts_export = hosts_subcommands.add_parser("export", help="export saved hosts to a JSON file")
    hosts_export.add_argument("--file", required=True, dest="export_file")
    hosts_import = hosts_subcommands.add_parser("import", help="import saved hosts from a JSON file")
    hosts_import.add_argument("--file", required=True, dest="import_file")


def _host_payload(entry: HostEntry) -> dict[str, Any]:
    data = asdict(entry)
    data["has_password"] = data.pop("password") is not None
    return data


def dispatch(args: argparse.Namespace) -> int:
    store = _cli._host_store()
    if args.hosts_action == "add":
        password = getpass.getpass("Password: ") if args.ask_password else args.password
        password_to_save = password if args.save_password else None
        if password_to_save:
            print(
                "Warning: password saved locally in plain text; password saved only because "
                "--save-password was used.",
                file=sys.stderr,
            )
        store.add(
            HostEntry(
                name=args.name,
                host=args.host,
                port=args.port,
                protocol=args.host_protocol,
                username=args.username,
                profile=args.profile,
                tags=parse_tags(args.tags),
                notes=args.notes,
                password=password_to_save,
            )
        )
        print(f"saved host: {args.name}")
        return 0
    if args.hosts_action == "list":
        entries = store.list()
        if args.json:
            _cli._json_output({"hosts": [_host_payload(entry) for entry in entries]})
            return 0
        print(format_hosts_table(entries))
        return 0
    if args.hosts_action == "show":
        print(format_hosts_table([store.get(args.name)]))
        return 0
    if args.hosts_action == "remove":
        store.remove(args.name)
        print(f"removed host: {args.name}")
        return 0
    if args.hosts_action == "test":
        if args.all or args.tag:
            entries = store.list()
            if args.tag:
                entries = [entry for entry in entries if args.tag in (entry.tags or [])]
            if not entries:
                print("no matching hosts", file=sys.stderr)
                return 1

            def _test_one(entry: HostEntry) -> Any:
                return maxconn.scan(entry.host, ports=[entry.port], timeout=args.timeout, concurrency=1)[0]

            worker_count = min(_cli.HOSTS_TEST_MAX_WORKERS, len(entries))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                results = list(executor.map(_test_one, entries))
            all_open = True
            for entry, result in zip(entries, results):
                status = "open" if result.open else "closed"
                all_open = all_open and result.open
                print(
                    f"{entry.name} {entry.host}:{entry.port} {entry.protocol} {status} "
                    f"({result.elapsed:.3f}s)"
                )
            return 0 if all_open else 1
        if not args.name:
            raise ValueError("hosts test requires a name, or --all / --tag")
        entry = store.get(args.name)
        results = maxconn.scan(entry.host, ports=[entry.port], timeout=args.timeout, concurrency=1)
        result = results[0]
        status = "open" if result.open else "closed"
        print(f"{entry.name} {entry.host}:{entry.port} {entry.protocol} {status} ({result.elapsed:.3f}s)")
        return 0 if result.open else 1
    if args.hosts_action == "recent":
        print(format_seen_hosts_table(store.list_seen()))
        return 0
    if args.hosts_action == "save-recent":
        saved = store.save_seen(
            args.id,
            name=args.name,
            profile=args.profile,
            tags=parse_tags(args.tags),
            notes=args.notes,
        )
        print(f"saved host: {saved.name}")
        return 0
    if args.hosts_action in ("edit", "set"):
        password = getpass.getpass("Password: ") if args.ask_password else args.password
        password_to_save = password if args.save_password else None
        if password_to_save:
            print(
                "Warning: password saved locally in plain text; password saved only because "
                "--save-password was used.",
                file=sys.stderr,
            )
        updated = store.update(
            args.name,
            host=args.host,
            port=args.port,
            protocol=args.host_protocol,
            username=args.username,
            profile=args.profile,
            tags=parse_tags(args.tags) if args.tags else None,
            notes=args.notes,
            password=password_to_save,
        )
        print(f"updated host: {updated.name}")
        return 0
    if args.hosts_action == "export":
        entries = store.list()
        Path(args.export_file).write_text(
            json.dumps([asdict(entry) for entry in entries], indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"exported {len(entries)} host(s) to {args.export_file}")
        return 0
    if args.hosts_action == "import":
        data = json.loads(Path(args.import_file).read_text(encoding="utf-8"))
        imported = 0
        for item in data:
            store.add(HostEntry(**item))
            imported += 1
        print(f"imported {imported} host(s) from {args.import_file}")
        return 0
    raise AssertionError(f"unhandled hosts action: {args.hosts_action}")
