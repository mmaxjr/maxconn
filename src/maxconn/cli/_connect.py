from __future__ import annotations

import argparse
import getpass
import sys
import time

import maxconn
from maxconn import cli as _cli
from maxconn.hosts import HostEntry, parse_tags


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    for protocol in ("ssh", "telnet"):
        command = subparsers.add_parser(protocol, help=f"run a command over {protocol.upper()}")
        command.add_argument("host")
        command.add_argument("--username")
        command.add_argument("--password")
        command.add_argument("--port", type=int)
        command.add_argument("--command")
        command.add_argument("--timeout", type=float, default=10.0)
        command.add_argument("--prompt", action="append", default=None)
        command.add_argument("--profile")
        command.add_argument("--tags")
        command.add_argument("--notes")
        command.add_argument("--save", metavar="NAME", help="save this connection as a local host")
        command.add_argument("--save-password", action="store_true")
        command.add_argument("--ask-password", action="store_true")


def dispatch(args: argparse.Namespace) -> int:
    prompt_markers = tuple(args.prompt) if args.prompt else (">", "#")
    store = _cli._host_store()
    inline_username, inline_host = _cli._split_username_host(args.host)
    resolved_host = inline_host
    resolved_port = args.port
    resolved_username = args.username or inline_username
    resolved_password = getpass.getpass("Password: ") if args.ask_password else args.password
    try:
        saved_host = store.get(inline_host)
    except KeyError:
        saved_host = None
    # Deliberately checked here instead of in a `try ... else:` clause -
    # mypy doesn't narrow `saved_host` to exclude None inside `else:` for
    # this shape, even though it's the same guarantee (else only runs when
    # the try block didn't raise, so the assignment above always ran).
    if saved_host is not None:
        if saved_host.protocol != args.protocol:
            raise ValueError(f"saved host {args.host} uses protocol {saved_host.protocol}")
        resolved_host = saved_host.host
        resolved_port = args.port if args.port is not None else saved_host.port
        resolved_username = args.username or inline_username or saved_host.username
        resolved_password = args.password or saved_host.password

    if not resolved_username:
        raise ValueError("--username is required unless the host alias has one saved")
    # `0 or default` would silently discard an explicitly-requested
    # port 0, since 0 is falsy in Python - resolved_port is already
    # None-checked above, so an explicit 0 must be preserved here too.
    effective_port = resolved_port if resolved_port is not None else (23 if args.protocol == "telnet" else 22)

    if args.save:
        password_to_save = resolved_password if args.save_password else None
        if password_to_save:
            print(
                "Warning: password saved locally in plain text; password saved only because "
                "--save-password was used.",
                file=sys.stderr,
            )
        store.add(
            HostEntry(
                name=args.save,
                host=resolved_host,
                port=effective_port,
                protocol=args.protocol,
                username=resolved_username,
                profile=args.profile or (saved_host.profile if saved_host else None),
                tags=parse_tags(args.tags) or (saved_host.tags if saved_host else []),
                notes=args.notes or (saved_host.notes if saved_host else None),
                password=password_to_save,
            )
        )
    store.record_seen(
        resolved_host,
        protocol=args.protocol,
        port=effective_port,
        username=resolved_username,
    )
    started = time.monotonic()
    with maxconn.connect(
        resolved_host,
        protocol=args.protocol,
        username=resolved_username,
        password=resolved_password,
        port=resolved_port,
        timeout=args.timeout,
    ) as conn:
        if args.command is None:
            return _cli._run_interactive_connection(
                conn,
                label=args.host,
                host=resolved_host,
                protocol=args.protocol,
                prompt_markers=prompt_markers,
                timeout=args.timeout,
            )
        result = conn.run(args.command, prompt_markers=prompt_markers, timeout=args.timeout)
        print(result.text, end="" if result.text.endswith("\n") else "\n")
        _cli._history_store().record(
            alias=args.host if saved_host else None,
            host=resolved_host,
            port=effective_port,
            protocol=args.protocol,
            username=resolved_username,
            command=args.command,
            ok=result.ok,
            exit_status=getattr(result, "exit_status", None),
            duration=time.monotonic() - started,
            origin="cli",
        )
        return 0 if result.ok else 1
