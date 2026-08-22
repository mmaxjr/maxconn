from __future__ import annotations

import argparse

from maxconn.hosts import HostEntry, HostStore, format_hosts_table


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a host to the local store, then list everything saved.")
    parser.add_argument("name")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--protocol", choices=("ssh", "telnet"), default="ssh")
    parser.add_argument("--username")
    parser.add_argument("--profile", help="e.g. cisco, huawei, mikrotik")
    args = parser.parse_args()

    # HostStore() with no base_dir uses the same ~/.maxconn/hosts.json the
    # CLI reads and writes - pass base_dir=some_path to keep a script's
    # hosts separate from the CLI's.
    store = HostStore()
    store.add(
        HostEntry(
            name=args.name,
            host=args.host,
            port=args.port,
            protocol=args.protocol,
            username=args.username,
            profile=args.profile,
        )
    )
    print(format_hosts_table(store.list()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
