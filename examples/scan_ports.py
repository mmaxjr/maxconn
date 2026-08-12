from __future__ import annotations

import argparse

import maxconn


def parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan TCP ports.")
    parser.add_argument("host")
    parser.add_argument("--ports", default="22,23,80,443")
    args = parser.parse_args()

    for result in maxconn.scan(args.host, ports=parse_ports(args.ports)):
        state = "open" if result.open else "closed"
        print(f"{result.port} {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
