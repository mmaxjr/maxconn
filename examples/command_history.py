from __future__ import annotations

import argparse
from datetime import datetime

from maxconn.history import HistoryStore, format_history_table, parse_since


def main() -> int:
    parser = argparse.ArgumentParser(description="Show local command history, optionally filtered by time.")
    parser.add_argument(
        "--since",
        help="today, yesterday, a relative offset like 24h/7d, or an ISO date",
    )
    parser.add_argument("--limit", type=int, help="only show the N most recent entries")
    args = parser.parse_args()

    store = HistoryStore()
    entries = store.list()
    if args.since:
        since_at = parse_since(args.since)
        entries = [entry for entry in entries if datetime.fromisoformat(entry.timestamp) >= since_at]
    if args.limit:
        entries = entries[-args.limit :]

    print(format_history_table(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
