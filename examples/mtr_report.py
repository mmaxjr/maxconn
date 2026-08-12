from __future__ import annotations

import argparse

from maxconn.net.mtr import run_mtr_table


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a bounded MTR report.")
    parser.add_argument("host")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    output = "json" if args.json else "table"
    print(run_mtr_table(args.host, count=args.count, interval=0, output=output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
