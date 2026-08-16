from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import maxconn
from maxconn import cli as _cli
from maxconn.hosts import HostEntry, parse_tags


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
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


def dispatch_ping(args: argparse.Namespace) -> int:
    count = args.retries if args.retries is not None else args.count
    result = maxconn.ping(args.host, timeout=args.timeout, count=count)
    if _cli._is_json_output(args):
        _cli._json_output(_ping_payload(result), args.export)
        return 0 if result.reachable else 1
    status = "reachable" if result.reachable else "unreachable"
    lines = [f"{result.host} {status} in {result.elapsed:.3f}s"]
    if result.error:
        lines.append(result.error)
    _cli._write_output("\n".join(lines), args.export)
    return 0 if result.reachable else 1


def dispatch_scan(args: argparse.Namespace) -> int:
    results = maxconn.scan(
        args.host,
        ports=_cli._parse_ports(args.ports),
        timeout=args.timeout,
        concurrency=args.concurrency,
    )
    if _cli._is_json_output(args):
        _cli._json_output(_scan_payload(args.host, results), args.export)
        return 0 if any(result.open for result in results) else 1
    lines = []
    for result in results:
        status = "open" if result.open else "closed"
        lines.append(f"{result.port} {status} ({result.elapsed:.3f}s)")
    _cli._write_output("\n".join(lines), args.export)
    return 0 if any(result.open for result in results) else 1


def dispatch_discover(args: argparse.Namespace) -> int:
    ports = _cli._parse_ports(args.ports)
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
        store = _cli._host_store()
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
    if _cli._is_json_output(args):
        _cli._json_output(_discover_payload(args.network, results), args.export)
        return 0 if any(result.reachable for result in results) else 1
    lines = ["HOST           STATUS      OPEN_PORTS       BANNER"]
    for result in results:
        status = "open" if result.reachable else "closed"
        open_ports = ",".join(str(port) for port in result.open_ports) or "-"
        banner = result.banner or ""
        lines.append(f"{result.host:<14} {status:<11} {open_ports:<16} {banner}")
    _cli._write_output("\n".join(lines), args.export)
    return 0 if any(result.reachable for result in results) else 1


def dispatch_traceroute(args: argparse.Namespace) -> int:
    result = maxconn.traceroute(args.host, timeout=args.timeout)
    if _cli._is_json_output(args):
        _cli._json_output(_traceroute_payload(result), args.export)
        return 0 if result.returncode == 0 else 1
    lines = [f"{hop.hop} {hop.address}" for hop in result.hops]
    if result.error:
        lines.append(result.error)
    _cli._write_output("\n".join(lines), args.export)
    return 0 if result.returncode == 0 else 1


def dispatch_mtr(args: argparse.Namespace) -> int:
    try:
        table = _cli.run_mtr_table(
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
