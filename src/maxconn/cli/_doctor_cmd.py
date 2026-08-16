from __future__ import annotations

import argparse
import platform
import shutil

import maxconn
from maxconn import cli as _cli


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    doctor_command = subparsers.add_parser("doctor", help="print local environment diagnostics")
    doctor_command.add_argument("--network", action="store_true", help="also run DNS/gateway/internet checks")


def dispatch(args: argparse.Namespace) -> int:
    tools = {
        "ping": shutil.which("ping"),
        "tracert": shutil.which("tracert"),
        "traceroute": shutil.which("traceroute"),
    }
    print(f"maxconn={maxconn.__version__}")
    print(f"python={platform.python_version()}")
    print(f"platform={platform.platform()}")
    for name, path in tools.items():
        print(f"{name}={path or 'not found'}")
    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("ssh_extra=not installed")
    else:
        print("ssh_extra=installed")
    print(f"maxconn_dir_writable={'yes' if _cli.doctor.check_dir_writable(_cli.DEFAULT_BASE_DIR) else 'no'}")
    terminal = _cli.doctor.check_terminal()
    print(f"terminal_tty={'yes' if terminal['isatty'] else 'no'}")
    print(f"terminal_color={'yes' if terminal['color'] else 'no'}")
    if not args.network:
        return 0
    dns_ok = _cli.doctor.check_dns()
    print(f"dns={'ok' if dns_ok else 'fail'}")
    internet_ok = _cli.doctor.check_internet()
    print(f"internet={'ok' if internet_ok else 'fail'}")
    gateway = _cli.doctor.default_gateway()
    print(f"gateway={gateway or 'unknown'}")
    latest = _cli.doctor.fetch_latest_pypi_version()
    print(f"pypi_latest={latest or 'unknown'}")
    print(f"version_status={_cli.doctor.compare_versions(maxconn.__version__, latest)}")
    return 0 if dns_ok and internet_ok else 1
