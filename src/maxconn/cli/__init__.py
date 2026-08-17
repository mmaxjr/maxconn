from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import maxconn
from maxconn import doctor as doctor
from maxconn.config import (
    ALLOWED_KEYS as ALLOWED_CONFIG_KEYS,  # noqa: F401 - used via cli.ALLOWED_CONFIG_KEYS
)
from maxconn.config import ConfigStore
from maxconn.exceptions import MaxConnError
from maxconn.history import HistoryStore
from maxconn.hosts import DEFAULT_BASE_DIR as DEFAULT_BASE_DIR
from maxconn.hosts import HostStore as HostStore
from maxconn.net.mtr import run_mtr_table as run_mtr_table
from maxconn.protocol.snmp import SNMPClient as SNMPClient

HOSTS_TEST_MAX_WORKERS = 16
# Lower than HOSTS_TEST_MAX_WORKERS since a real SSH/Telnet connection is far
# heavier than a bare TCP port probe (handshake, auth, prompt negotiation).
HOSTS_RUN_MAX_WORKERS = 8


def _config_store() -> ConfigStore:
    return ConfigStore()


def _apply_config_defaults(parser: argparse.ArgumentParser, config: dict[str, str]) -> None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for subparser in action.choices.values():
                _apply_config_defaults(subparser, config)
            continue
        if action.dest in config:
            raw = config[action.dest]
            action.default = action.type(raw) if action.type else raw
            action.required = False


def _parse_ports(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _host_store() -> HostStore:
    return HostStore()


def _history_store() -> HistoryStore:
    return HistoryStore()


def _interactive_input(prompt: str) -> str:
    return input(prompt)


def _interactive_theme() -> tuple[Any, bool]:
    from maxconn.ui.caps import supports_color
    from maxconn.ui.config import load_theme
    from maxconn.ui.theme import get_theme

    return get_theme(load_theme() or "plain"), supports_color()


def _run_interactive_connection(
    conn: Any,
    *,
    label: str,
    host: str,
    protocol: str,
    prompt_markers: tuple[str, ...],
    timeout: float,
) -> int:
    theme, color_enabled = _interactive_theme()
    print(theme.ok.render(f"connected: {label} ({host}) {protocol}", enabled=color_enabled))
    print(theme.muted.render("type exit or quit to return", enabled=color_enabled))
    device_prompt = f"{label}>"
    try:
        initial_output = conn.read_until(prompt_markers[0], timeout=min(timeout, 3.0))
    except (MaxConnError, OSError, TimeoutError):
        initial_output = ""
    if initial_output:
        print(initial_output, end="" if initial_output.endswith("\n") else "\n")
        device_prompt = _extract_device_prompt(initial_output, fallback=device_prompt)
    while True:
        try:
            command = _interactive_input(theme.prompt.render(f"{device_prompt} ", enabled=color_enabled)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            return 0
        result = conn.run(command, prompt_markers=prompt_markers, timeout=timeout)
        print(result.text, end="" if result.text.endswith("\n") else "\n")
        device_prompt = _extract_device_prompt(result.text, fallback=device_prompt)


def _extract_device_prompt(text: str, *, fallback: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.endswith((">", "#")) and stripped not in {">", "#"}:
            return stripped
    return fallback


def _is_json_output(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "output", None) == "json")


def _write_output(text: str, export: str | None = None) -> None:
    if export:
        Path(export).write_text(text, encoding="utf-8")
    print(text)


def _json_output(payload: dict[str, Any], export: str | None = None) -> None:
    _write_output(json.dumps(payload, indent=2, default=str), export)


def _run_with_retries(operation: Callable[[], Any], *, attempts: int) -> Any:
    last_error: Exception | None = None
    for _ in range(max(attempts, 1)):
        try:
            return operation()
        except (OSError, TimeoutError, ValueError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _split_username_host(value: str) -> tuple[str | None, str]:
    username, separator, host = value.partition("@")
    if separator and username and host:
        return username, host
    return None, value


def _build_parser() -> argparse.ArgumentParser:
    from maxconn.cli import (
        _audit_cmd,
        _config_ops,
        _connect,
        _doctor_cmd,
        _history,
        _hosts,
        _inventory,
        _meta,
        _net,
        _sftp,
        _snmp,
    )

    parser = argparse.ArgumentParser(prog="maxconn", description="Network automation toolkit CLI.")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    subparsers = parser.add_subparsers(dest="protocol", required=True)

    _connect.add_subparser(subparsers)
    _hosts.add_subparser(subparsers)
    _net.add_subparser(subparsers)
    _history.add_subparser(subparsers)
    _doctor_cmd.add_subparser(subparsers)
    _meta.add_subparser(subparsers)
    _sftp.add_subparser(subparsers)
    _snmp.add_subparser(subparsers)
    _config_ops.add_subparser(subparsers)
    _inventory.add_subparser(subparsers)
    _audit_cmd.add_subparser(subparsers)

    config = _config_store().load()
    if config:
        _apply_config_defaults(parser, config)
    return parser


def _dispatch_table() -> dict[str, Callable[[argparse.Namespace], int]]:
    from maxconn.cli import (
        _audit_cmd,
        _config_ops,
        _connect,
        _doctor_cmd,
        _history,
        _hosts,
        _inventory,
        _meta,
        _net,
        _sftp,
        _snmp,
    )

    return {
        "ssh": _connect.dispatch,
        "telnet": _connect.dispatch,
        "hosts": _hosts.dispatch,
        "history": _history.dispatch,
        "ping": _net.dispatch_ping,
        "scan": _net.dispatch_scan,
        "discover": _net.dispatch_discover,
        "traceroute": _net.dispatch_traceroute,
        "mtr": _net.dispatch_mtr,
        "doctor": _doctor_cmd.dispatch,
        "selftest": _meta.dispatch_selftest,
        "start": _meta.dispatch_start,
        "completion": _meta.dispatch_completion,
        "config": _meta.dispatch_config,
        "sftp": _sftp.dispatch,
        "snmp": _snmp.dispatch,
        "backup": _config_ops.dispatch_backup,
        "diff": _config_ops.dispatch_diff,
        "inventory": _inventory.dispatch,
        "audit": _audit_cmd.dispatch,
    }


def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv[1:] if argv is None else argv
    if resolved_argv == ["--version"]:
        print(f"maxconn {maxconn.__version__}")
        return 0

    config = _config_store().load()
    if config.get("audit_log") == "on":
        from maxconn.audit import enable_persistent_audit_log

        enable_persistent_audit_log(DEFAULT_BASE_DIR / "audit.jsonl")

    parser = _build_parser()
    try:
        args = parser.parse_args(resolved_argv)
        handler = _dispatch_table()[args.protocol]
        return handler(args)
    except (MaxConnError, OSError, TimeoutError, ValueError, KeyError, IndexError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if config.get("update_notify") == "on":
            _print_update_notice_if_any()


def _print_update_notice_if_any() -> None:
    # A passive notice must never break or mask the real command's result.
    with contextlib.suppress(Exception):
        notice = doctor.check_for_update(DEFAULT_BASE_DIR, current_version=maxconn.__version__)
        if notice:
            print(notice, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
