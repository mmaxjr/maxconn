from __future__ import annotations

import argparse

import maxconn


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one command over SSH.")
    parser.add_argument("host")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    parser.add_argument("--command", required=True)
    args = parser.parse_args()

    with maxconn.connect(
        args.host,
        protocol="ssh",
        username=args.username,
        password=args.password,
    ) as conn:
        result = conn.run(args.command, prompt_markers=(">", "#"))
        print(result.text, end="" if result.text.endswith("\n") else "\n")
        return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
