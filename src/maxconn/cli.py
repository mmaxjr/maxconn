from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import maxconn
from maxconn.net.mtr import run_mtr_table
from maxconn.protocol.snmp import SNMPClient


def _parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _is_json_output(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "output", None) == "json")


def _write_output(text: str, export: str | None = None) -> None:
    if export:
        Path(export).write_text(text)
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


def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="maxconn", description="Network automation toolkit CLI.")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="protocol", required=True)
    for protocol in ("ssh", "telnet"):
        command = subparsers.add_parser(protocol, help=f"run a command over {protocol.upper()}")
        command.add_argument("host")
        command.add_argument("--username", required=True)
        command.add_argument("--password")
        command.add_argument("--port", type=int)
        command.add_argument("--command", required=True)
        command.add_argument("--timeout", type=float, default=10.0)
        command.add_argument("--prompt", action="append", default=None)

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

    subparsers.add_parser("doctor", help="print local environment diagnostics")
    subparsers.add_parser("selftest", help="run quick local CLI checks")
    subparsers.add_parser("start", help="launch the interactive maxconn shell")

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

    if resolved_argv == ["--version"]:
        print(f"maxconn {maxconn.__version__}")
        return 0

    try:
        args = parser.parse_args(resolved_argv)
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
            return 0

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
                Path(args.export).write_text(table)
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
    except (OSError, TimeoutError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
