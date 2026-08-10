from __future__ import annotations

import argparse

import maxconn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maxconn")
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

    args = parser.parse_args(argv)
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
