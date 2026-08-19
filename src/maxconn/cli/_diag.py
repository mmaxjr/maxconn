from __future__ import annotations

import argparse
from typing import Any

import maxconn
from maxconn import cli as _cli
from maxconn.hosts import HostEntry


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    diag_command = subparsers.add_parser("diag", help="run a quick diagnostic against a host")
    diag_command.add_argument("host")
    diag_command.add_argument(
        "--ports",
        default="22,23,80,443",
        help="comma-separated TCP ports to test",
    )
    diag_command.add_argument("--timeout", type=float, default=2.0)
    diag_command.add_argument("--concurrency", type=int, default=32)
    diag_command.add_argument("--no-traceroute", action="store_true", help="skip traceroute")
    diag_command.add_argument("--json", action="store_true", help="print JSON output")
    diag_command.add_argument("--output", choices=("text", "json"), default="text")
    diag_command.add_argument("--export", help="write the rendered output to a file")


def dispatch(args: argparse.Namespace) -> int:
    saved = _resolve_saved_host(args.host)
    resolved_host = saved.host if saved is not None else args.host
    ports = _cli._parse_ports(args.ports)

    ping_result = maxconn.ping(resolved_host, timeout=args.timeout)
    scan_results = maxconn.scan(
        resolved_host,
        ports=ports,
        timeout=args.timeout,
        concurrency=args.concurrency,
    )
    trace_result = None
    if not args.no_traceroute:
        trace_result = maxconn.traceroute(resolved_host, timeout=max(args.timeout, 1.0) * 10)

    payload = _diag_payload(args.host, resolved_host, saved, ping_result, scan_results, trace_result)
    if _cli._is_json_output(args):
        _cli._json_output(payload, args.export)
    else:
        _cli._write_output(_format_diag_text(payload), args.export)
    return 0 if payload["overall"] in {"ok", "warning"} else 1


def _resolve_saved_host(value: str) -> HostEntry | None:
    try:
        return _cli._host_store().get(value)
    except KeyError:
        return None


def _diag_payload(
    target: str,
    resolved_host: str,
    saved: HostEntry | None,
    ping_result: Any,
    scan_results: list[Any],
    trace_result: Any | None,
) -> dict[str, Any]:
    open_ports = [result.port for result in scan_results if result.open]
    trace_ok = trace_result is None or trace_result.returncode in {0, None}
    if not ping_result.reachable and not open_ports:
        overall = "fail"
    elif ping_result.reachable and open_ports and trace_ok:
        overall = "ok"
    else:
        overall = "warning"
    return {
        "target": target,
        "resolved_host": resolved_host,
        "saved_host": _saved_host_payload(saved),
        "ping": {
            "reachable": ping_result.reachable,
            "elapsed": ping_result.elapsed,
            "returncode": ping_result.returncode,
            "error": ping_result.error,
        },
        "ports": [
            {
                "port": result.port,
                "open": result.open,
                "elapsed": result.elapsed,
                "error": result.error,
            }
            for result in scan_results
        ],
        "trace": None if trace_result is None else _trace_payload(trace_result),
        "overall": overall,
    }


def _saved_host_payload(saved: HostEntry | None) -> dict[str, Any] | None:
    if saved is None:
        return None
    return {
        "name": saved.name,
        "host": saved.host,
        "port": saved.port,
        "protocol": saved.protocol,
        "username": saved.username,
        "profile": saved.profile,
        "tags": saved.tags,
        "has_password": bool(saved.password),
    }


def _trace_payload(result: Any) -> dict[str, Any]:
    return {
        "returncode": result.returncode,
        "error": result.error,
        "hops": [
            {"hop": hop.hop, "address": hop.address, "raw": hop.raw}
            for hop in result.hops
        ],
    }


def _format_diag_text(payload: dict[str, Any]) -> str:
    lines = [f"Target: {payload['target']} ({payload['resolved_host']})"]
    saved = payload["saved_host"]
    if saved is not None:
        tags = ",".join(saved["tags"]) or "-"
        lines.append(
            "Saved host: "
            f"protocol={saved['protocol']} "
            f"port={saved['port']} "
            f"user={saved['username'] or '-'} "
            f"profile={saved['profile'] or '-'} "
            f"tags={tags}"
        )

    ping = payload["ping"]
    ping_status = "reachable" if ping["reachable"] else "unreachable"
    lines.append(f"Ping: {ping_status} ({ping['elapsed']:.3f}s)")
    if ping["error"]:
        lines.append(f"Ping error: {ping['error']}")

    port_parts = []
    for result in payload["ports"]:
        status = "open" if result["open"] else "closed"
        port_parts.append(f"{result['port']} {status}")
    lines.append(f"Ports: {', '.join(port_parts) if port_parts else '-'}")

    trace = payload["trace"]
    if trace is not None:
        if trace["hops"]:
            hops = " -> ".join(f"{hop['hop']} {hop['address']}" for hop in trace["hops"])
            lines.append(f"Trace: {hops}")
        else:
            lines.append("Trace: no hops")
        if trace["error"]:
            lines.append(f"Trace error: {trace['error']}")
    lines.append(f"Overall: {payload['overall']}")
    return "\n".join(lines)
