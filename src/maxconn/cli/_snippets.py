from __future__ import annotations

import argparse
from pathlib import Path

from maxconn import cli as _cli
from maxconn.hosts import parse_tags
from maxconn.snippets import format_snippets_table


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    snippet_command = subparsers.add_parser("snippet", help="save and reuse command/config snippets")
    snippet_subcommands = snippet_command.add_subparsers(dest="snippet_action", required=True)

    snippet_add = snippet_subcommands.add_parser("add", help="save a new snippet")
    snippet_add.add_argument("name")
    content_group = snippet_add.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--command", help="snippet content, given inline")
    content_group.add_argument("--file", dest="content_file", help="read snippet content from this file")
    snippet_add.add_argument("--tags", help="comma-separated tags, e.g. huawei,cgnat")

    snippet_list = snippet_subcommands.add_parser("list", help="list saved snippets")
    snippet_list.add_argument("--tag", help="only list snippets with this tag")

    snippet_show = snippet_subcommands.add_parser("show", help="print a saved snippet's content")
    snippet_show.add_argument("name")

    snippet_edit = snippet_subcommands.add_parser("edit", help="overwrite a saved snippet's content and/or tags")
    snippet_edit.add_argument("name")
    edit_content_group = snippet_edit.add_mutually_exclusive_group(required=True)
    edit_content_group.add_argument("--command", help="new snippet content, given inline")
    edit_content_group.add_argument("--file", dest="content_file", help="read new snippet content from this file")
    snippet_edit.add_argument("--tags", help="comma-separated tags; replaces the existing tags")

    snippet_remove = snippet_subcommands.add_parser("remove", help="remove a saved snippet")
    snippet_remove.add_argument("name")


def _resolve_content(args: argparse.Namespace) -> str:
    if args.content_file:
        return Path(args.content_file).read_text(encoding="utf-8")
    return args.command


def dispatch(args: argparse.Namespace) -> int:
    store = _cli._snippet_store()
    if args.snippet_action == "add":
        store.add(args.name, _resolve_content(args), tags=parse_tags(args.tags))
        print(f"saved snippet: {args.name}")
        return 0
    if args.snippet_action == "list":
        print(format_snippets_table(store.list(tag=args.tag)))
        return 0
    if args.snippet_action == "show":
        _, content = store.get(args.name)
        print(content, end="" if content.endswith("\n") else "\n")
        return 0
    if args.snippet_action == "edit":
        store.edit(args.name, _resolve_content(args), tags=parse_tags(args.tags) if args.tags else None)
        print(f"updated snippet: {args.name}")
        return 0
    if args.snippet_action == "remove":
        store.remove(args.name)
        print(f"removed snippet: {args.name}")
        return 0
    raise AssertionError(f"unhandled snippet action: {args.snippet_action}")
