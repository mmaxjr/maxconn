from __future__ import annotations

import shlex
import subprocess
import sys

from maxconn.exceptions import MaxConnError
from maxconn.hosts import HostStore

from .caps import configure_stdio, enable_windows_vt, supports_color
from .commands import ARGUMENT_OPTIONS, COMMANDS
from .config import load_theme, save_theme
from .input import Completer, read_line
from .theme import THEMES, get_theme

BANNER_NAME = "MAXCONN"


def choose_theme_interactively() -> str:
    print("Primeira vez por aqui. Escolha um design:")
    names = list(THEMES.keys())
    for index, name in enumerate(names, start=1):
        print(f"  {index}) {name}")
    while True:
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return names[int(choice) - 1]
        print("Opção inválida, tente de novo.")


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def render_banner(theme, color_enabled: bool) -> None:
    box = theme.box
    width = 42
    top = box.top_left + box.top * (width - 2) + box.top_right
    bottom = box.bottom_left + box.bottom * (width - 2) + box.bottom_right
    title = f"{BANNER_NAME} — tema: {theme.name}".center(width - 2)
    middle = box.mid_left + title + box.mid_right
    print(theme.header.render(top, enabled=color_enabled))
    print(theme.header.render(middle, enabled=color_enabled))
    print(theme.header.render(bottom, enabled=color_enabled))


# Sinais que run_command pode devolver pro loop principal.
CONTINUE = "continue"
RESTART = "restart"
EXIT = "exit"


def _host_store() -> HostStore:
    return HostStore()


def _run_maxconn_cli(argv: list[str]) -> int:
    from maxconn.cli import main as cli_main

    return cli_main(argv)


def _run_maxconn_cli_safe(argv: list[str], theme, color_enabled: bool) -> int:
    try:
        return _run_maxconn_cli(argv)
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int) else 1
    except (MaxConnError, OSError, TimeoutError, ValueError) as exc:
        print(theme.error.render(f"Error: {exc}", enabled=color_enabled), file=sys.stderr)
        return 1


def run_system_command(line: str, theme, color_enabled: bool) -> None:
    """Fall back to the OS shell (cmd/PowerShell on Windows, /bin/sh
    elsewhere) for anything that isn't a maxconn command. Inherits stdio
    directly so native output/coloring/interactivity works unmodified.
    """
    try:
        subprocess.run(line, shell=True, check=False)
    except OSError as exc:
        print(theme.error.render(f"falha ao executar: {exc}", enabled=color_enabled))


def run_command(name: str, args: list[str], theme, color_enabled: bool, line: str) -> str:
    """Handle one parsed command. Returns CONTINUE, RESTART or EXIT."""
    if name in ("exit", "quit"):
        return EXIT

    if name in ("reboot", "restart"):
        print(theme.ok.render("reiniciando...", enabled=color_enabled))
        return RESTART

    if name == "help":
        for command_name, description in sorted(COMMANDS.items()):
            label = theme.header.render(command_name.ljust(12), enabled=color_enabled)
            print(f"  {label} {description}")
        return CONTINUE

    if name == "theme":
        if not args:
            print(theme.warn.render("uso: theme <plain|classic|solid>", enabled=color_enabled))
            return CONTINUE
        new_name = args[0]
        if new_name not in THEMES:
            print(theme.error.render(f"tema desconhecido: {new_name}", enabled=color_enabled))
            return CONTINUE
        save_theme(new_name)
        print(theme.ok.render(f"tema alterado para {new_name}, reiniciando...", enabled=color_enabled))
        return RESTART

    if name in {"ssh", "telnet"}:
        if not args:
            print(theme.warn.render(f"uso: {name} <host-salvo|host> [opções]", enabled=color_enabled))
            return CONTINUE
        _run_maxconn_cli_safe([name, *args], theme, color_enabled)
        return CONTINUE

    if name in {"open", "connect"}:
        if not args:
            print(theme.warn.render("uso: open <host-salvo>", enabled=color_enabled))
            return CONTINUE
        try:
            saved = _host_store().get(args[0])
        except KeyError as exc:
            print(theme.error.render(str(exc), enabled=color_enabled))
            return CONTINUE
        _run_maxconn_cli_safe([saved.protocol, args[0], *args[1:]], theme, color_enabled)
        return CONTINUE

    if name in COMMANDS:
        print(theme.muted.render(f"[preview] executaria: {name} {' '.join(args)}", enabled=color_enabled))
        return CONTINUE

    run_system_command(line, theme, color_enabled)
    return CONTINUE


def run_session(theme, color_enabled: bool) -> str:
    """Read/dispatch loop for one "boot" of the shell. Returns RESTART or EXIT."""
    completer = Completer(COMMANDS, ARGUMENT_OPTIONS)
    prompt = theme.prompt.render("maxconn> ", enabled=color_enabled)
    history: list[str] = []

    while True:
        try:
            line = read_line(prompt, completer, theme, color_enabled, history)
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            return EXIT

        line = line.strip()
        if not line:
            continue

        if not history or history[-1] != line:
            history.append(line)

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(theme.error.render(f"erro de sintaxe: {exc}", enabled=color_enabled))
            continue

        command_name, command_args = parts[0], parts[1:]
        signal = run_command(command_name, command_args, theme, color_enabled, line)
        if signal in (RESTART, EXIT):
            return signal


def main() -> int:
    configure_stdio()
    enable_windows_vt()
    color_enabled = supports_color()

    theme_name = load_theme()
    if theme_name is None:
        theme_name = choose_theme_interactively()
        save_theme(theme_name)

    signal = RESTART
    while signal == RESTART:
        theme_name = load_theme() or theme_name
        theme = get_theme(theme_name)

        clear_screen()
        render_banner(theme, color_enabled)
        print(theme.muted.render("Tab: completar | Tab Tab: listar | ?: ajuda | exit: sair", enabled=color_enabled))

        signal = run_session(theme, color_enabled)

    print("até mais.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
