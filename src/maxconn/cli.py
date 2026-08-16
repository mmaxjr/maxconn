from __future__ import annotations

import argparse
import getpass
import json
import platform
import shutil
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import maxconn
from maxconn import doctor
from maxconn.config import ALLOWED_KEYS as ALLOWED_CONFIG_KEYS
from maxconn.config import ConfigStore
from maxconn.exceptions import MaxConnError
from maxconn.history import HistoryStore, format_history_csv, format_history_table, parse_since
from maxconn.hosts import (
    DEFAULT_BASE_DIR,
    HostEntry,
    HostStore,
    format_hosts_table,
    format_seen_hosts_table,
    parse_tags,
)
from maxconn.net.mtr import run_mtr_table
from maxconn.protocol.snmp import SNMPClient

HOSTS_TEST_MAX_WORKERS = 16


def _config_store() -> ConfigStore:
    return ConfigStore()


def _apply_config_defaults(parser: argparse.ArgumentParser, config: dict[str, str]) -> None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for subparser in action.choices.values():
                _apply_config_defaults(subparser, config)
            continue
        if action.dest in config:
            raw = config[action.dest]
            action.default = action.type(raw) if action.type else raw
            action.required = False


def _parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _host_store() -> HostStore:
    return HostStore()


def _history_store() -> HistoryStore:
    return HistoryStore()


def _interactive_input(prompt: str) -> str:
    return input(prompt)


def _interactive_theme() -> tuple[Any, bool]:
    from maxconn.ui.caps import supports_color
    from maxconn.ui.config import load_theme
    from maxconn.ui.theme import get_theme

    return get_theme(load_theme() or "plain"), supports_color()


def _run_interactive_connection(
    conn: Any,
    *,
    label: str,
    host: str,
    protocol: str,
    prompt_markers: tuple[str, ...],
    timeout: float,
) -> int:
    theme, color_enabled = _interactive_theme()
    print(theme.ok.render(f"connected: {label} ({host}) {protocol}", enabled=color_enabled))
    print(theme.muted.render("type exit or quit to return", enabled=color_enabled))
    device_prompt = f"{label}>"
    try:
        initial_output = conn.read_until(prompt_markers[0], timeout=min(timeout, 3.0))
    except (MaxConnError, OSError, TimeoutError):
        initial_output = ""
    if initial_output:
        print(initial_output, end="" if initial_output.endswith("\n") else "\n")
        device_prompt = _extract_device_prompt(initial_output, fallback=device_prompt)
    while True:
        try:
            command = _interactive_input(theme.prompt.render(f"{device_prompt} ", enabled=color_enabled)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            return 0
        result = conn.run(command, prompt_markers=prompt_markers, timeout=timeout)
        print(result.text, end="" if result.text.endswith("\n") else "\n")
        device_prompt = _extract_device_prompt(result.text, fallback=device_prompt)


def _extract_device_prompt(text: str, *, fallback: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.endswith((">", "#")) and stripped not in {">", "#"}:
            return stripped
    return fallback


def _is_json_output(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "output", None) == "json")


def _write_output(text: str, export: str | None = None) -> None:
    if export:
        Path(export).write_text(text, encoding="utf-8")
    print(text)


def _json_output(payload: dict[str, Any], export: str | None = None) -> None:
    _write_output(json.dumps(payload, indent=2, default=str), export)


def _run_with_retries(operation: Callable[[], Any], *, attempts: int) -> Any:
    last_error: Exception | None = None
    for _ in range(max(attempts, 1)):
        try:
            return operation()
        except (OSError, TimeoutError, ValueError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _split_username_host(value: str) -> tuple[str | None, str]:
    username, separator, host = value.partition("@")
    if separator and username and host:
        return username, host
    return None, value


def _ping_payload(result: Any) -> dict[str, Any]:
    return {
        "host": result.host,
        "reachable": result.reachable,
        "elapsed": result.elapsed,
        "returncode": result.returncode,
        "output": result.output,
        "error": result.error,
    }


def _scan_payload(host: str, results: list[Any]) -> dict[str, Any]:
    return {
        "host": host,
        "ports": [
            {
                "host": result.host,
                "port": result.port,
                "open": result.open,
                "elapsed": result.elapsed,
                "error": result.error,
            }
            for result in results
        ],
    }


def _discover_payload(network: str, results: list[Any]) -> dict[str, Any]:
    return {
        "network": network,
        "hosts": [
            {
                "host": result.host,
                "reachable": result.reachable,
                "open_ports": result.open_ports,
                "scanned_ports": result.scanned_ports,
                "banner": result.banner,
            }
            for result in results
        ],
    }


def _host_payload(entry: HostEntry) -> dict[str, Any]:
    data = asdict(entry)
    data["has_password"] = data.pop("password") is not None
    return data


def _protocol_for_port(port: int) -> str:
    if port == 23:
        return "telnet"
    return "ssh"


def _traceroute_payload(result: Any) -> dict[str, Any]:
    return {
        "host": result.host,
        "returncode": result.returncode,
        "output": result.output,
        "error": result.error,
        "hops": [
            {"hop": hop.hop, "address": hop.address, "raw": hop.raw}
            for hop in result.hops
        ],
    }


def _sftp_attrs_payload(host: str, path: str, attrs: Any) -> dict[str, Any]:
    permissions = None if attrs.permissions is None else oct(attrs.permissions)
    return {
        "host": host,
        "path": path,
        "size": attrs.size,
        "uid": getattr(attrs, "uid", None),
        "gid": getattr(attrs, "gid", None),
        "permissions": permissions,
        "atime": getattr(attrs, "atime", None),
        "mtime": getattr(attrs, "mtime", None),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maxconn", description="Network automation toolkit CLI.")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="protocol", required=True)
    for protocol in ("ssh", "telnet"):
        command = subparsers.add_parser(protocol, help=f"run a command over {protocol.upper()}")
        command.add_argument("host")
        command.add_argument("--username")
        command.add_argument("--password")
        command.add_argument("--port", type=int)
        command.add_argument("--command")
        command.add_argument("--timeout", type=float, default=10.0)
        command.add_argument("--prompt", action="append", default=None)
        command.add_argument("--profile")
        command.add_argument("--tags")
        command.add_argument("--notes")
        command.add_argument("--save", metavar="NAME", help="save this connection as a local host")
        command.add_argument("--save-password", action="store_true")
        command.add_argument("--ask-password", action="store_true")

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

    ping_command = subparsers.add_parser("ping", help="probe host reachability")
    ping_command.add_argument("host")
    ping_command.add_argument("--timeout", type=float, default=2.0)
    ping_command.add_argument("--count", type=int, default=1)
    ping_command.add_argument("--retries", type=int, default=None, help="number of ping attempts")
    ping_command.add_argument("--json", action="store_true", help="print JSON output")
    ping_command.add_argument("--output", choices=("text", "json"), default="text")
    ping_command.add_argument("--export", help="write the rendered output to a file")

    scan_command = subparsers.add_parser("scan", help="scan TCP ports")
    scan_command.add_argument("host")
    scan_command.add_argument("--ports", required=True)
    scan_command.add_argument("--timeout", type=float, default=1.0)
    scan_command.add_argument("--concurrency", type=int, default=100)
    scan_command.add_argument("--json", action="store_true", help="print JSON output")
    scan_command.add_argument("--output", choices=("text", "json"), default="text")
    scan_command.add_argument("--export", help="write the rendered output to a file")

    discover_command = subparsers.add_parser("discover", help="scan a subnet for devices")
    discover_command.add_argument("network")
    discover_command.add_argument(
        "--ports",
        default=",".join(str(port) for port in maxconn.DEFAULT_DISCOVER_PORTS),
        help="comma-separated TCP ports to test",
    )
    discover_command.add_argument("--timeout", type=float, default=1.0)
    discover_command.add_argument("--concurrency", type=int, default=32)
    discover_command.add_argument("--workers", type=int, default=64)
    discover_command.add_argument("--json", action="store_true", help="print JSON output")
    discover_command.add_argument("--output", choices=("text", "json"), default="text")
    discover_command.add_argument("--export", help="write the rendered output to a file")
    discover_command.add_argument("--only-open", action="store_true", help="show only hosts with open ports")
    discover_command.add_argument("--save-found", action="store_true", help="save discovered open hosts locally")
    discover_command.add_argument(
        "--name-prefix", default="discovered", help="prefix used when naming saved hosts (with --save-found)"
    )
    discover_command.add_argument("--tags", help="comma-separated tags for saved hosts (with --save-found)")
    discover_command.add_argument(
        "--confirm", action="store_true", help="allow scanning networks above the confirmation threshold"
    )

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

    doctor_command = subparsers.add_parser("doctor", help="print local environment diagnostics")
    doctor_command.add_argument("--network", action="store_true", help="also run DNS/gateway/internet checks")
    subparsers.add_parser("selftest", help="run quick local CLI checks")
    subparsers.add_parser("start", help="launch the interactive maxconn shell")

    completion_command = subparsers.add_parser("completion", help="print a shell completion script")
    completion_command.add_argument("shell", choices=("bash", "zsh", "powershell"), nargs="?")
    completion_command.add_argument("--_list", nargs="*", dest="list_path", help=argparse.SUPPRESS)

    config_command = subparsers.add_parser("config", help="manage local CLI defaults")
    config_subcommands = config_command.add_subparsers(dest="config_action", required=True)
    config_set = config_subcommands.add_parser("set", help="set a default value")
    config_set.add_argument("key", choices=ALLOWED_CONFIG_KEYS)
    config_set.add_argument("value")
    config_get = config_subcommands.add_parser("get", help="print a default value")
    config_get.add_argument("key", choices=ALLOWED_CONFIG_KEYS)
    config_unset = config_subcommands.add_parser("unset", help="remove a default value")
    config_unset.add_argument("key", choices=ALLOWED_CONFIG_KEYS)
    config_subcommands.add_parser("list", help="list all default values")

    traceroute_command = subparsers.add_parser("traceroute", help="show network path to a host")
    traceroute_command.add_argument("host")
    traceroute_command.add_argument("--timeout", type=float, default=30.0)
    traceroute_command.add_argument("--json", action="store_true", help="print JSON output")
    traceroute_command.add_argument("--output", choices=("text", "json"), default="text")
    traceroute_command.add_argument("--export", help="write the rendered output to a file")

    mtr_command = subparsers.add_parser("mtr", help="live WinMTR-style path monitoring")
    mtr_command.add_argument("host")
    mtr_command.add_argument("--count", type=int, default=None)
    mtr_command.add_argument("--timeout", type=float, default=1.0)
    mtr_command.add_argument("--trace-timeout", type=float, default=30.0)
    mtr_command.add_argument("--rediscover-every", type=int, default=None)
    mtr_command.add_argument("--interval", type=float, default=1.0)
    mtr_command.add_argument("--json", action="store_true", help="print JSON output")
    mtr_command.add_argument("--output", choices=("table", "json"), default="table")
    mtr_command.add_argument("--export", help="write the rendered output to a file")
    mtr_command.add_argument("--no-clear", action="store_true")

    sftp_command = subparsers.add_parser("sftp", help="copy and manage files over SFTP")
    sftp_subcommands = sftp_command.add_subparsers(dest="sftp_action", required=True)
    sftp_ls = sftp_subcommands.add_parser("ls", help="list a remote directory")
    sftp_ls.add_argument("host")
    sftp_ls.add_argument("remote_path")
    sftp_get = sftp_subcommands.add_parser("get", help="download a remote file")
    sftp_get.add_argument("host")
    sftp_get.add_argument("remote_path")
    sftp_get.add_argument("local_path")
    sftp_put = sftp_subcommands.add_parser("put", help="upload a local file")
    sftp_put.add_argument("host")
    sftp_put.add_argument("local_path")
    sftp_put.add_argument("remote_path")
    sftp_stat = sftp_subcommands.add_parser("stat", help="show remote file attributes")
    sftp_stat.add_argument("host")
    sftp_stat.add_argument("remote_path")
    sftp_stat.add_argument("--json", action="store_true", help="print JSON output")
    sftp_stat.add_argument("--output", choices=("text", "json"), default="text")
    sftp_stat.add_argument("--export", help="write the rendered output to a file")
    sftp_mkdir = sftp_subcommands.add_parser("mkdir", help="create a remote directory")
    sftp_mkdir.add_argument("host")
    sftp_mkdir.add_argument("remote_path")
    sftp_rm = sftp_subcommands.add_parser("rm", help="remove a remote file")
    sftp_rm.add_argument("host")
    sftp_rm.add_argument("remote_path")
    sftp_rename = sftp_subcommands.add_parser("rename", help="rename a remote path")
    sftp_rename.add_argument("host")
    sftp_rename.add_argument("old_path")
    sftp_rename.add_argument("new_path")
    for sftp_action in (sftp_ls, sftp_get, sftp_put, sftp_stat, sftp_mkdir, sftp_rm, sftp_rename):
        sftp_action.add_argument("--username", required=True)
        sftp_action.add_argument("--password")
        sftp_action.add_argument("--port", type=int, default=22)
        sftp_action.add_argument("--timeout", type=float, default=10.0)

    snmp_command = subparsers.add_parser("snmp", help="read SNMP v2c values")
    snmp_subcommands = snmp_command.add_subparsers(dest="snmp_action", required=True)
    for action in ("get", "walk"):
        snmp_action = snmp_subcommands.add_parser(action, help=f"SNMP {action}")
        snmp_action.add_argument("host")
        snmp_action.add_argument("oid")
        snmp_action.add_argument("--community", default="public")
        snmp_action.add_argument("--port", type=int, default=161)
        snmp_action.add_argument("--timeout", type=float, default=2.0)
        snmp_action.add_argument("--retries", type=int, default=1)
        snmp_action.add_argument("--json", action="store_true", help="print JSON output")
        snmp_action.add_argument("--output", choices=("text", "json"), default="text")
        snmp_action.add_argument("--export", help="write the rendered output to a file")
        if action == "walk":
            snmp_action.add_argument("--limit", type=int, default=100)

    config = _config_store().load()
    if config:
        _apply_config_defaults(parser, config)
    return parser


def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv[1:] if argv is None else argv
    if resolved_argv == ["--version"]:
        print(f"maxconn {maxconn.__version__}")
        return 0

    parser = _build_parser()
    try:
        args = parser.parse_args(resolved_argv)
        if args.protocol == "hosts":
            store = _host_store()
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
                    _json_output({"hosts": [_host_payload(entry) for entry in entries]})
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

                    worker_count = min(HOSTS_TEST_MAX_WORKERS, len(entries))
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

        if args.protocol == "history":
            store = _history_store()
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
                if _is_json_output(args):
                    _json_output({"entries": [entry.__dict__ for entry in entries]}, args.export)
                elif args.output == "csv":
                    _write_output(format_history_csv(entries), args.export)
                else:
                    _write_output(format_history_table(entries), args.export)
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
                host_store = _host_store()
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

        if args.protocol == "ping":
            count = args.retries if args.retries is not None else args.count
            result = maxconn.ping(args.host, timeout=args.timeout, count=count)
            if _is_json_output(args):
                _json_output(_ping_payload(result), args.export)
                return 0 if result.reachable else 1
            status = "reachable" if result.reachable else "unreachable"
            lines = [f"{result.host} {status} in {result.elapsed:.3f}s"]
            if result.error:
                lines.append(result.error)
            _write_output("\n".join(lines), args.export)
            return 0 if result.reachable else 1

        if args.protocol == "scan":
            results = maxconn.scan(
                args.host,
                ports=_parse_ports(args.ports),
                timeout=args.timeout,
                concurrency=args.concurrency,
            )
            if _is_json_output(args):
                _json_output(_scan_payload(args.host, results), args.export)
                return 0 if any(result.open for result in results) else 1
            lines = []
            for result in results:
                status = "open" if result.open else "closed"
                lines.append(f"{result.port} {status} ({result.elapsed:.3f}s)")
            _write_output("\n".join(lines), args.export)
            return 0 if any(result.open for result in results) else 1

        if args.protocol == "discover":
            ports = _parse_ports(args.ports)
            results = maxconn.discover(
                args.network,
                ports=ports,
                timeout=args.timeout,
                concurrency=args.concurrency,
                workers=args.workers,
                confirm=args.confirm,
            )
            if args.only_open:
                results = [result for result in results if result.reachable]
            if args.save_found:
                store = _host_store()
                tags = parse_tags(args.tags) or ["discovered"]
                for result in results:
                    if not result.reachable:
                        continue
                    port = result.open_ports[0]
                    store.add(
                        HostEntry(
                            name=f"{args.name_prefix}-{result.host}",
                            host=result.host,
                            port=port,
                            protocol=_protocol_for_port(port),
                            username=None,
                            profile=None,
                            tags=tags,
                            notes=f"discovered from {args.network}",
                        )
                    )
            if _is_json_output(args):
                _json_output(_discover_payload(args.network, results), args.export)
                return 0 if any(result.reachable for result in results) else 1
            lines = ["HOST           STATUS      OPEN_PORTS       BANNER"]
            for result in results:
                status = "open" if result.reachable else "closed"
                open_ports = ",".join(str(port) for port in result.open_ports) or "-"
                banner = result.banner or ""
                lines.append(f"{result.host:<14} {status:<11} {open_ports:<16} {banner}")
            _write_output("\n".join(lines), args.export)
            return 0 if any(result.reachable for result in results) else 1

        if args.protocol == "doctor":
            tools = {
                "ping": shutil.which("ping"),
                "tracert": shutil.which("tracert"),
                "traceroute": shutil.which("traceroute"),
            }
            print(f"maxconn={maxconn.__version__}")
            print(f"python={platform.python_version()}")
            print(f"platform={platform.platform()}")
            for name, path in tools.items():
                print(f"{name}={path or 'not found'}")
            try:
                import cryptography  # noqa: F401
            except ImportError:
                print("ssh_extra=not installed")
            else:
                print("ssh_extra=installed")
            print(f"maxconn_dir_writable={'yes' if doctor.check_dir_writable(DEFAULT_BASE_DIR) else 'no'}")
            terminal = doctor.check_terminal()
            print(f"terminal_tty={'yes' if terminal['isatty'] else 'no'}")
            print(f"terminal_color={'yes' if terminal['color'] else 'no'}")
            if not args.network:
                return 0
            dns_ok = doctor.check_dns()
            print(f"dns={'ok' if dns_ok else 'fail'}")
            internet_ok = doctor.check_internet()
            print(f"internet={'ok' if internet_ok else 'fail'}")
            gateway = doctor.default_gateway()
            print(f"gateway={gateway or 'unknown'}")
            latest = doctor.fetch_latest_pypi_version()
            print(f"pypi_latest={latest or 'unknown'}")
            print(f"version_status={doctor.compare_versions(maxconn.__version__, latest)}")
            return 0 if dns_ok and internet_ok else 1

        if args.protocol == "selftest":
            json.loads(json.dumps({"ok": True}))
            print(f"maxconn={maxconn.__version__}")
            print("import=ok")
            print("json=ok")
            print("cli=ok")
            return 0

        if args.protocol == "start":
            from maxconn.ui.shell import main as shell_main

            return shell_main()

        if args.protocol == "completion":
            from maxconn.completion import (
                build_command_tree,
                candidates_for_path,
                render_bash,
                render_powershell,
                render_zsh,
            )

            tree = build_command_tree(_build_parser())
            if args.list_path is not None:
                for candidate in candidates_for_path(tree, args.list_path):
                    print(candidate)
                return 0
            if not args.shell:
                raise ValueError("completion requires a shell: bash, zsh, or powershell")
            renderer = {"bash": render_bash, "zsh": render_zsh, "powershell": render_powershell}[args.shell]
            print(renderer(tree))
            return 0

        if args.protocol == "config":
            store = _config_store()
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

        if args.protocol == "traceroute":
            result = maxconn.traceroute(args.host, timeout=args.timeout)
            if _is_json_output(args):
                _json_output(_traceroute_payload(result), args.export)
                return 0 if result.returncode == 0 else 1
            lines = [f"{hop.hop} {hop.address}" for hop in result.hops]
            if result.error:
                lines.append(result.error)
            _write_output("\n".join(lines), args.export)
            return 0 if result.returncode == 0 else 1

        if args.protocol == "mtr":
            try:
                table = run_mtr_table(
                    args.host,
                    count=args.count,
                    timeout=args.timeout,
                    trace_timeout=args.trace_timeout,
                    rediscover_every=args.rediscover_every,
                    interval=args.interval,
                    output="json" if args.json else args.output,
                    clear=not args.no_clear,
                )
            except KeyboardInterrupt:
                print()
                return 0
            if args.export:
                Path(args.export).write_text(table, encoding="utf-8")
            if args.count is not None:
                print(table)
            return 0

        if args.protocol == "sftp":
            client = maxconn.connect_sftp(
                args.host,
                username=args.username,
                password=args.password,
                port=args.port,
                timeout=args.timeout,
            )
            try:
                if args.sftp_action == "ls":
                    for name in client.listdir(args.remote_path):
                        print(name)
                elif args.sftp_action == "get":
                    client.download(args.remote_path, args.local_path)
                elif args.sftp_action == "put":
                    client.upload(args.local_path, args.remote_path)
                elif args.sftp_action == "stat":
                    attrs = client.stat(args.remote_path)
                    if _is_json_output(args):
                        _json_output(_sftp_attrs_payload(args.host, args.remote_path, attrs), args.export)
                    else:
                        permissions = "None" if attrs.permissions is None else oct(attrs.permissions)
                        _write_output(f"size={attrs.size} permissions={permissions}", args.export)
                elif args.sftp_action == "mkdir":
                    client.mkdir(args.remote_path)
                elif args.sftp_action == "rm":
                    client.remove(args.remote_path)
                elif args.sftp_action == "rename":
                    client.rename(args.old_path, args.new_path)
            finally:
                client.close()
            return 0

        if args.protocol == "snmp":
            client = SNMPClient(
                args.host,
                community=args.community,
                port=args.port,
                timeout=args.timeout,
            )
            if args.snmp_action == "get":
                result = _run_with_retries(lambda: client.get(args.oid), attempts=args.retries)
                if _is_json_output(args):
                    _json_output({"host": args.host, "oid": result.oid, "value": result.value}, args.export)
                else:
                    _write_output(f"{result.oid} = {result.value}", args.export)
                return 0
            results = _run_with_retries(
                lambda: client.walk(args.oid, limit=args.limit),
                attempts=args.retries,
            )
            if _is_json_output(args):
                _json_output(
                    {
                        "host": args.host,
                        "oid": args.oid,
                        "results": [{"oid": result.oid, "value": result.value} for result in results],
                    },
                    args.export,
                )
            else:
                _write_output("\n".join(f"{result.oid} = {result.value}" for result in results), args.export)
            return 0

        prompt_markers = tuple(args.prompt) if args.prompt else (">", "#")
        store = _host_store()
        inline_username, inline_host = _split_username_host(args.host)
        resolved_host = inline_host
        resolved_port = args.port
        resolved_username = args.username or inline_username
        resolved_password = getpass.getpass("Password: ") if args.ask_password else args.password
        try:
            saved_host = store.get(inline_host)
        except KeyError:
            saved_host = None
        else:
            if saved_host.protocol != args.protocol:
                raise ValueError(f"saved host {args.host} uses protocol {saved_host.protocol}")
            resolved_host = saved_host.host
            resolved_port = args.port if args.port is not None else saved_host.port
            resolved_username = args.username or inline_username or saved_host.username
            resolved_password = args.password or saved_host.password

        if not resolved_username:
            raise ValueError("--username is required unless the host alias has one saved")
        # `0 or default` would silently discard an explicitly-requested
        # port 0, since 0 is falsy in Python - resolved_port is already
        # None-checked above, so an explicit 0 must be preserved here too.
        effective_port = resolved_port if resolved_port is not None else (23 if args.protocol == "telnet" else 22)

        if args.save:
            password_to_save = resolved_password if args.save_password else None
            if password_to_save:
                print(
                    "Warning: password saved locally in plain text; password saved only because "
                    "--save-password was used.",
                    file=sys.stderr,
                )
            store.add(
                HostEntry(
                    name=args.save,
                    host=resolved_host,
                    port=effective_port,
                    protocol=args.protocol,
                    username=resolved_username,
                    profile=args.profile or (saved_host.profile if saved_host else None),
                    tags=parse_tags(args.tags) or (saved_host.tags if saved_host else []),
                    notes=args.notes or (saved_host.notes if saved_host else None),
                    password=password_to_save,
                )
            )
        store.record_seen(
            resolved_host,
            protocol=args.protocol,
            port=effective_port,
            username=resolved_username,
        )
        started = time.monotonic()
        with maxconn.connect(
            resolved_host,
            protocol=args.protocol,
            username=resolved_username,
            password=resolved_password,
            port=resolved_port,
            timeout=args.timeout,
        ) as conn:
            if args.command is None:
                return _run_interactive_connection(
                    conn,
                    label=args.host,
                    host=resolved_host,
                    protocol=args.protocol,
                    prompt_markers=prompt_markers,
                    timeout=args.timeout,
                )
            result = conn.run(args.command, prompt_markers=prompt_markers, timeout=args.timeout)
            print(result.text, end="" if result.text.endswith("\n") else "\n")
            _history_store().record(
                alias=args.host if saved_host else None,
                host=resolved_host,
                port=effective_port,
                protocol=args.protocol,
                username=resolved_username,
                command=args.command,
                ok=result.ok,
                exit_status=getattr(result, "exit_status", None),
                duration=time.monotonic() - started,
                origin="cli",
            )
            return 0 if result.ok else 1
    except (MaxConnError, OSError, TimeoutError, ValueError, KeyError, IndexError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
