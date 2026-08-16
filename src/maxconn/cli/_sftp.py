from __future__ import annotations

import argparse
from typing import Any

import maxconn
from maxconn import cli as _cli


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    sftp_command = subparsers.add_parser("sftp", help="copy and manage files over SFTP")
    sftp_subcommands = sftp_command.add_subparsers(dest="sftp_action", required=True)
    sftp_ls = sftp_subcommands.add_parser("ls", help="list a remote directory")
    sftp_ls.add_argument("host")
    sftp_ls.add_argument("remote_path")
    sftp_get = sftp_subcommands.add_parser("get", help="download a remote file")
    sftp_get.add_argument("host")
    sftp_get.add_argument("remote_path")
    sftp_get.add_argument("local_path")
    sftp_put = sftp_subcommands.add_parser("put", help="upload a local file")
    sftp_put.add_argument("host")
    sftp_put.add_argument("local_path")
    sftp_put.add_argument("remote_path")
    sftp_stat = sftp_subcommands.add_parser("stat", help="show remote file attributes")
    sftp_stat.add_argument("host")
    sftp_stat.add_argument("remote_path")
    sftp_stat.add_argument("--json", action="store_true", help="print JSON output")
    sftp_stat.add_argument("--output", choices=("text", "json"), default="text")
    sftp_stat.add_argument("--export", help="write the rendered output to a file")
    sftp_mkdir = sftp_subcommands.add_parser("mkdir", help="create a remote directory")
    sftp_mkdir.add_argument("host")
    sftp_mkdir.add_argument("remote_path")
    sftp_rm = sftp_subcommands.add_parser("rm", help="remove a remote file")
    sftp_rm.add_argument("host")
    sftp_rm.add_argument("remote_path")
    sftp_rename = sftp_subcommands.add_parser("rename", help="rename a remote path")
    sftp_rename.add_argument("host")
    sftp_rename.add_argument("old_path")
    sftp_rename.add_argument("new_path")
    for sftp_action in (sftp_ls, sftp_get, sftp_put, sftp_stat, sftp_mkdir, sftp_rm, sftp_rename):
        sftp_action.add_argument("--username", required=True)
        sftp_action.add_argument("--password")
        sftp_action.add_argument("--port", type=int, default=22)
        sftp_action.add_argument("--timeout", type=float, default=10.0)


def _sftp_attrs_payload(host: str, path: str, attrs: Any) -> dict[str, Any]:
    permissions = None if attrs.permissions is None else oct(attrs.permissions)
    return {
        "host": host,
        "path": path,
        "size": attrs.size,
        "uid": getattr(attrs, "uid", None),
        "gid": getattr(attrs, "gid", None),
        "permissions": permissions,
        "atime": getattr(attrs, "atime", None),
        "mtime": getattr(attrs, "mtime", None),
    }


def dispatch(args: argparse.Namespace) -> int:
    client = maxconn.connect_sftp(
        args.host,
        username=args.username,
        password=args.password,
        port=args.port,
        timeout=args.timeout,
    )
    try:
        if args.sftp_action == "ls":
            for name in client.listdir(args.remote_path):
                print(name)
        elif args.sftp_action == "get":
            client.download(args.remote_path, args.local_path)
        elif args.sftp_action == "put":
            client.upload(args.local_path, args.remote_path)
        elif args.sftp_action == "stat":
            attrs = client.stat(args.remote_path)
            if _cli._is_json_output(args):
                _cli._json_output(_sftp_attrs_payload(args.host, args.remote_path, attrs), args.export)
            else:
                permissions = "None" if attrs.permissions is None else oct(attrs.permissions)
                _cli._write_output(f"size={attrs.size} permissions={permissions}", args.export)
        elif args.sftp_action == "mkdir":
            client.mkdir(args.remote_path)
        elif args.sftp_action == "rm":
            client.remove(args.remote_path)
        elif args.sftp_action == "rename":
            client.rename(args.old_path, args.new_path)
    finally:
        client.close()
    return 0
