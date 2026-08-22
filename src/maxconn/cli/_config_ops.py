from __future__ import annotations

import argparse
import difflib
import getpass
import re
from datetime import datetime, timezone
from pathlib import Path

import maxconn
from maxconn import cli as _cli

DEFAULT_BACKUP_COMMANDS = {
    "cisco": "show running-config",
    "huawei": "display current-configuration",
    "mikrotik": "export",
}


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    backup_command = subparsers.add_parser("backup", help="save a device's running configuration locally")
    backup_command.add_argument("host")
    backup_command.add_argument("--command", help="command to fetch the config (default depends on saved profile)")
    backup_command.add_argument("--protocol", choices=("ssh", "telnet"), dest="backup_protocol")
    backup_command.add_argument("--username")
    backup_command.add_argument("--password")
    backup_command.add_argument("--ask-password", action="store_true")
    backup_command.add_argument("--port", type=int)
    backup_command.add_argument("--timeout", type=float, default=15.0)
    backup_command.add_argument(
        "--to", dest="to_path", help="file to save to (default: ~/.maxconn/backups/<host>/<timestamp>.cfg)"
    )

    diff_command = subparsers.add_parser("diff", help="show differences between two config backups")
    diff_command.add_argument("old_file")
    diff_command.add_argument("new_file")
    diff_command.add_argument("--json", action="store_true", help="print JSON output")
    diff_command.add_argument("--export", help="write the rendered output to a file")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def dispatch_backup(args: argparse.Namespace) -> int:
    store = _cli._host_store()
    try:
        saved_host = store.get(args.host)
    except KeyError:
        saved_host = None

    protocol = args.backup_protocol or (saved_host.protocol if saved_host else "ssh")
    host = saved_host.host if saved_host else args.host
    port = args.port if args.port is not None else (saved_host.port if saved_host else None)
    username = args.username or (saved_host.username if saved_host else None)
    password: str | None
    if args.ask_password:
        password = getpass.getpass("Password: ")
    elif args.password is not None:
        password = args.password
    else:
        password = saved_host.password if saved_host else None

    command = args.command
    if not command and saved_host and saved_host.profile:
        command = DEFAULT_BACKUP_COMMANDS.get(saved_host.profile)
    if not command:
        raise ValueError(
            "--command is required (no default backup command for this host's profile); "
            f"known profiles: {', '.join(sorted(DEFAULT_BACKUP_COMMANDS))}"
        )
    if not username:
        raise ValueError("--username is required unless the host alias has one saved")

    with maxconn.connect(
        host,
        protocol=protocol,
        username=username,
        password=password,
        port=port,
        timeout=args.timeout,
    ) as conn:
        result = conn.run(command, timeout=args.timeout)

    if args.to_path:
        destination = Path(args.to_path)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = _cli.DEFAULT_BASE_DIR / "backups" / _safe_name(args.host) / f"{timestamp}.cfg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.text, encoding="utf-8")
    print(f"saved backup to {destination}")
    return 0 if result.ok else 1


def dispatch_diff(args: argparse.Namespace) -> int:
    old_lines = Path(args.old_file).read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = Path(args.new_file).read_text(encoding="utf-8").splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(old_lines, new_lines, fromfile=args.old_file, tofile=args.new_file)
    )
    changed = bool(diff_lines)
    if _cli._is_json_output(args):
        _cli._json_output(
            {
                "old_file": args.old_file,
                "new_file": args.new_file,
                "changed": changed,
                "diff": diff_lines,
            },
            args.export,
        )
    else:
        _cli._write_output("".join(diff_lines) if diff_lines else "no differences", args.export)
    return 1 if changed else 0
