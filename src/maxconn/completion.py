from __future__ import annotations

import argparse
from typing import Any


def build_command_tree(parser: argparse.ArgumentParser) -> dict[str, Any]:
    flags: list[str] = []
    subcommands: dict[str, Any] = {}
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                subcommands[name] = build_command_tree(subparser)
            continue
        flags.extend(action.option_strings)
    return {"flags": sorted(flags), "subcommands": subcommands}


def render_bash(tree: dict[str, Any], *, prog: str = "maxconn") -> str:
    return f"""\
_{prog}_complete() {{
    local cur
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    COMPREPLY=()

    local -a path=()
    local i
    for ((i = 1; i < COMP_CWORD; i++)); do
        path+=("${{COMP_WORDS[$i]}}")
    done

    local candidates
    candidates="$({prog} completion --_list "${{path[@]}}")"
    COMPREPLY=($(compgen -W "$candidates" -- "$cur"))
}}
complete -F _{prog}_complete {prog}
"""


def render_zsh(tree: dict[str, Any], *, prog: str = "maxconn") -> str:
    return f"""\
autoload -U +X bashcompinit && bashcompinit
{render_bash(tree, prog=prog)}"""


def render_powershell(tree: dict[str, Any], *, prog: str = "maxconn") -> str:
    return f"""\
Register-ArgumentCompleter -Native -CommandName {prog} -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $tokens = $commandAst.CommandElements | Select-Object -Skip 1 | ForEach-Object {{ $_.ToString() }}
    if ($tokens -and $tokens[-1] -eq $wordToComplete) {{
        $tokens = $tokens[0..($tokens.Length - 2)]
    }}
    $candidates = & {prog} completion --_list @tokens
    $candidates | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }}
}}
"""


def candidates_for_path(tree: dict[str, Any], path: list[str]) -> list[str]:
    node = tree
    for segment in path:
        subcommands = node.get("subcommands", {})
        if segment not in subcommands:
            return []
        node = subcommands[segment]
    return sorted(node.get("subcommands", {}).keys()) + node.get("flags", [])
