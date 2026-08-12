from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

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

    subparsers.add_parser("doctor")

    traceroute_command = subparsers.add_parser("traceroute")
    traceroute_command.add_argument("host")
    traceroute_command.add_argument("--timeout", type=float, default=30.0)

    mtr_command = subparsers.add_parser("mtr")
    mtr_command.add_argument("host")
    mtr_command.add_argument("--count", type=int, default=None)
    mtr_command.add_argument("--timeout", type=float, default=1.0)
    mtr_command.add_argument("--trace-timeout", type=float, default=30.0)
    mtr_command.add_argument("--rediscover-every", type=int, default=None)
    mtr_command.add_argument("--interval", type=float, default=1.0)
    mtr_command.add_argument("--json", action="store_true")
    mtr_command.add_argument("--export")
    mtr_command.add_argument("--no-clear", action="store_true")

    sftp_command = subparsers.add_parser("sftp")
    sftp_subcommands = sftp_command.add_subparsers(dest="sftp_action", required=True)
    sftp_ls = sftp_subcommands.add_parser("ls")
    sftp_ls.add_argument("host")
    sftp_ls.add_argument("remote_path")
    sftp_get = sftp_subcommands.add_parser("get")
    sftp_get.add_argument("host")
    sftp_get.add_argument("remote_path")
    sftp_get.add_argument("local_path")
    sftp_put = sftp_subcommands.add_parser("put")
    sftp_put.add_argument("host")
    sftp_put.add_argument("local_path")
    sftp_put.add_argument("remote_path")
    sftp_stat = sftp_subcommands.add_parser("stat")
    sftp_stat.add_argument("host")
    sftp_stat.add_argument("remote_path")
    sftp_mkdir = sftp_subcommands.add_parser("mkdir")
    sftp_mkdir.add_argument("host")
    sftp_mkdir.add_argument("remote_path")
    sftp_rm = sftp_subcommands.add_parser("rm")
    sftp_rm.add_argument("host")
    sftp_rm.add_argument("remote_path")
    sftp_rename = sftp_subcommands.add_parser("rename")
    sftp_rename.add_argument("host")
    sftp_rename.add_argument("old_path")
    sftp_rename.add_argument("new_path")
    for sftp_action in (sftp_ls, sftp_get, sftp_put, sftp_stat, sftp_mkdir, sftp_rm, sftp_rename):
        sftp_action.add_argument("--username", required=True)
        sftp_action.add_argument("--password")
        sftp_action.add_argument("--port", type=int, default=22)
        sftp_action.add_argument("--timeout", type=float, default=10.0)

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
                trace_timeout=args.trace_timeout,
                rediscover_every=args.rediscover_every,
                interval=args.interval,
                output="json" if args.json else "table",
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
                permissions = "None" if attrs.permissions is None else oct(attrs.permissions)
                print(f"size={attrs.size} permissions={permissions}")
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
