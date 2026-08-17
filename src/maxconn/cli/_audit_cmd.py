from __future__ import annotations

import argparse
import json

from maxconn import cli as _cli


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    audit_command = subparsers.add_parser("audit", help="view the local audit log")
    audit_subcommands = audit_command.add_subparsers(dest="audit_action", required=True)
    audit_tail = audit_subcommands.add_parser("tail", help="show the most recent audit log entries")
    audit_tail.add_argument("-n", "--limit", type=int, default=20)
    audit_tail.add_argument("--json", action="store_true", help="print JSON output")


def dispatch(args: argparse.Namespace) -> int:
    if args.audit_action == "tail":
        path = _cli.DEFAULT_BASE_DIR / "audit.jsonl"
        if not path.exists():
            print("no audit log entries (enable with: maxconn config set audit_log on)")
            return 0
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        recent = lines[-args.limit :] if args.limit > 0 else lines
        if args.json:
            _cli._json_output({"entries": [json.loads(line) for line in recent]})
            return 0
        for line in recent:
            print(line)
        return 0
    raise AssertionError(f"unhandled audit action: {args.audit_action}")
