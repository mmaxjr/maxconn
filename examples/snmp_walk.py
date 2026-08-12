from __future__ import annotations

import argparse

from maxconn.protocol.snmp import SNMPClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk an SNMP subtree.")
    parser.add_argument("host")
    parser.add_argument("oid")
    parser.add_argument("--community", default="public")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    client = SNMPClient(args.host, community=args.community)
    for result in client.walk(args.oid, limit=args.limit):
        print(f"{result.oid} = {result.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
