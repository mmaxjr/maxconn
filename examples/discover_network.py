from __future__ import annotations

import argparse

import maxconn


def parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a subnet and print reachable hosts.")
    parser.add_argument("network", help="CIDR block, e.g. 192.168.0.0/24")
    parser.add_argument("--ports", help="comma-separated TCP ports (default: common network ports)")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required for networks above the host-count safety threshold",
    )
    args = parser.parse_args()

    ports = parse_ports(args.ports) if args.ports else None
    for host in maxconn.discover(args.network, ports=ports, confirm=args.confirm):
        if not host.reachable:
            continue
        banner = f" - {host.banner}" if host.banner else ""
        print(f"{host.host} open={host.open_ports}{banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
