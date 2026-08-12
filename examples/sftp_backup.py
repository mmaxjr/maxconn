from __future__ import annotations

import argparse
from pathlib import Path

import maxconn


def main() -> int:
    parser = argparse.ArgumentParser(description="Download one file over SFTP.")
    parser.add_argument("host")
    parser.add_argument("remote_path")
    parser.add_argument("local_path", type=Path)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    args = parser.parse_args()

    client = maxconn.connect_sftp(args.host, username=args.username, password=args.password)
    try:
        client.download(args.remote_path, args.local_path)
    finally:
        client.close()
    print(args.local_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
