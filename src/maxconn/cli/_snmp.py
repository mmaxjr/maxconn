from __future__ import annotations

import argparse

from maxconn import cli as _cli


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
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


def dispatch(args: argparse.Namespace) -> int:
    client = _cli.SNMPClient(
        args.host,
        community=args.community,
        port=args.port,
        timeout=args.timeout,
    )
    if args.snmp_action == "get":
        result = _cli._run_with_retries(lambda: client.get(args.oid), attempts=args.retries)
        if _cli._is_json_output(args):
            _cli._json_output({"host": args.host, "oid": result.oid, "value": result.value}, args.export)
        else:
            _cli._write_output(f"{result.oid} = {result.value}", args.export)
        return 0
    results = _cli._run_with_retries(
        lambda: client.walk(args.oid, limit=args.limit),
        attempts=args.retries,
    )
    if _cli._is_json_output(args):
        _cli._json_output(
            {
                "host": args.host,
                "oid": args.oid,
                "results": [{"oid": result.oid, "value": result.value} for result in results],
            },
            args.export,
        )
    else:
        _cli._write_output("\n".join(f"{result.oid} = {result.value}" for result in results), args.export)
    return 0
