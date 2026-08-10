from __future__ import annotations

import argparse
import sys

import maxconn
from maxconn.net.mtr import run_mtr_table
from maxconn.protocol.snmp import SNMPClient


def _parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="maxconn")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="protocol", required=True)
    for protocol in ("ssh", "telnet"):
        command = subparsers.add_parser(protocol)
        command.add_argument("host")
        command.add_argument("--username", required=True)
        command.add_argument("--password")
        command.add_argument("--port", type=int)
        command.add_argument("--command", required=True)
        command.add_argument("--timeout", type=float, default=10.0)
        command.add_argument("--prompt", action="append", default=None)

    ping_command = subparsers.add_parser("ping")
    ping_command.add_argument("host")
    ping_command.add_argument("--timeout", type=float, default=2.0)
    ping_command.add_argument("--count", type=int, default=1)

    scan_command = subparsers.add_parser("scan")
    scan_command.add_argument("host")
    scan_command.add_argument("--ports", required=True)
    scan_command.add_argument("--timeout", type=float, default=1.0)
    scan_command.add_argument("--concurrency", type=int, default=100)

    traceroute_command = subparsers.add_parser("traceroute")
    traceroute_command.add_argument("host")
    traceroute_command.add_argument("--timeout", type=float, default=30.0)

    mtr_command = subparsers.add_parser("mtr")
    mtr_command.add_argument("host")
    mtr_command.add_argument("--count", type=int, default=None)
    mtr_command.add_argument("--timeout", type=float, default=1.0)
    mtr_command.add_argument("--interval", type=float, default=1.0)

    snmp_command = subparsers.add_parser("snmp")
    snmp_subcommands = snmp_command.add_subparsers(dest="snmp_action", required=True)
    for action in ("get", "walk"):
        snmp_action = snmp_subcommands.add_parser(action)
        snmp_action.add_argument("host")
        snmp_action.add_argument("oid")
        snmp_action.add_argument("--community", default="public")
        snmp_action.add_argument("--port", type=int, default=161)
        snmp_action.add_argument("--timeout", type=float, default=2.0)
        if action == "walk":
            snmp_action.add_argument("--limit", type=int, default=100)

    if resolved_argv == ["--version"]:
        print(f"maxconn {maxconn.__version__}")
        return 0

    args = parser.parse_args(resolved_argv)
    if args.protocol == "ping":
        result = maxconn.ping(args.host, timeout=args.timeout, count=args.count)
        status = "reachable" if result.reachable else "unreachable"
        print(f"{result.host} {status} in {result.elapsed:.3f}s")
        if result.error:
            print(result.error)
        return 0 if result.reachable else 1

    if args.protocol == "scan":
        results = maxconn.scan(
            args.host,
            ports=_parse_ports(args.ports),
            timeout=args.timeout,
            concurrency=args.concurrency,
        )
        for result in results:
            status = "open" if result.open else "closed"
            print(f"{result.port} {status} ({result.elapsed:.3f}s)")
        return 0 if any(result.open for result in results) else 1

    if args.protocol == "traceroute":
        result = maxconn.traceroute(args.host, timeout=args.timeout)
        for hop in result.hops:
            print(f"{hop.hop} {hop.address}")
        if result.error:
            print(result.error)
        return 0 if result.returncode == 0 else 1

    if args.protocol == "mtr":
        try:
            table = run_mtr_table(
                args.host,
                count=args.count,
                timeout=args.timeout,
                interval=args.interval,
            )
        except KeyboardInterrupt:
            print()
            return 0
        if args.count is not None:
            print(table)
        return 0

    if args.protocol == "snmp":
        client = SNMPClient(
            args.host,
            community=args.community,
            port=args.port,
            timeout=args.timeout,
        )
        if args.snmp_action == "get":
            result = client.get(args.oid)
            print(f"{result.oid} = {result.value}")
            return 0
        for result in client.walk(args.oid, limit=args.limit):
            print(f"{result.oid} = {result.value}")
        return 0

    prompt_markers = tuple(args.prompt) if args.prompt else (">", "#")
    with maxconn.connect(
        args.host,
        protocol=args.protocol,
        username=args.username,
        password=args.password,
        port=args.port,
        timeout=args.timeout,
    ) as conn:
        result = conn.run(args.command, prompt_markers=prompt_markers, timeout=args.timeout)
        print(result.text, end="" if result.text.endswith("\n") else "\n")
        return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
