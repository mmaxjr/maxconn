from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass

from maxconn import cli as _cli


@dataclass(frozen=True)
class ReconcileResult:
    matched: set[str]
    missing: set[str]
    undocumented: set[str]

    @property
    def is_clean(self) -> bool:
        return not self.missing and not self.undocumented


def reconcile(*, planned_hosts, discovered) -> ReconcileResult:
    planned = set(planned_hosts)
    reachable = {result.host for result in discovered if result.reachable}
    return ReconcileResult(
        matched=planned & reachable,
        missing=planned - reachable,
        undocumented=reachable - planned,
    )


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    inventory_command = subparsers.add_parser(
        "inventory", help="list saved hosts as a structured inventory, optionally reconciled against a live scan"
    )
    inventory_command.add_argument("--json", action="store_true", help="print JSON output")
    inventory_command.add_argument("--output", choices=("text", "json", "csv"), default="text")
    inventory_command.add_argument("--export", help="write the rendered output to a file")
    inventory_command.add_argument(
        "--reconcile", metavar="NETWORK", help="compare saved hosts against a live discover scan of NETWORK"
    )
    inventory_command.add_argument("--confirm", action="store_true", help="see `discover --confirm`")
    inventory_command.add_argument("--timeout", type=float, default=1.0)


def _inventory_csv(entries) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "host", "port", "protocol", "profile", "tags", "notes"])
    for entry in entries:
        writer.writerow(
            [
                entry.name,
                entry.host,
                entry.port,
                entry.protocol,
                entry.profile or "",
                ",".join(entry.tags or []),
                entry.notes or "",
            ]
        )
    return output.getvalue()


def dispatch(args: argparse.Namespace) -> int:
    from maxconn.cli._hosts import _host_payload
    from maxconn.hosts import format_hosts_table

    store = _cli._host_store()
    entries = store.list()

    if args.reconcile:
        import maxconn

        discovered = maxconn.discover(args.reconcile, timeout=args.timeout, confirm=args.confirm)
        result = reconcile(planned_hosts=[entry.host for entry in entries], discovered=discovered)
        by_host = {entry.host: entry for entry in entries}
        if _cli._is_json_output(args):
            _cli._json_output(
                {
                    "network": args.reconcile,
                    "matched": sorted(result.matched),
                    "missing": sorted(result.missing),
                    "undocumented": sorted(result.undocumented),
                },
                args.export,
            )
            return 0 if result.is_clean else 1
        lines = [f"=== Inventory reconciliation for {args.reconcile} ==="]
        lines.append(f"Documented & reachable: {len(result.matched)}")
        lines.append(f"Documented but unreachable: {len(result.missing)}")
        for host in sorted(result.missing):
            entry = by_host.get(host)
            label = f"{entry.name} ({host})" if entry else host
            lines.append(f"  - {label}")
        lines.append(f"Reachable but undocumented: {len(result.undocumented)}")
        for host in sorted(result.undocumented):
            lines.append(f"  - {host}")
        _cli._write_output("\n".join(lines), args.export)
        return 0 if result.is_clean else 1

    if _cli._is_json_output(args):
        _cli._json_output({"hosts": [_host_payload(entry) for entry in entries]}, args.export)
        return 0
    if args.output == "csv":
        _cli._write_output(_inventory_csv(entries), args.export)
        return 0
    _cli._write_output(format_hosts_table(entries), args.export)
    return 0
