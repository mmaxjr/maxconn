from __future__ import annotations

import os
import sys

STD_OUTPUT_HANDLE = -11
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def configure_stdio() -> None:
    """Force UTF-8 on stdout/stderr so box-drawing characters never crash.

    Some Windows consoles default to a legacy codepage (cp1252, cp850, ...)
    where the box characters used by the "classic"/"solid"/"matrix" themes
    have no representation, raising UnicodeEncodeError on print(). Errors
    are replaced instead of raised; worst case the border looks odd, it
    never takes the whole command down.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def enable_windows_vt() -> None:
    """Turn on ANSI escape processing in the current Windows console.

    Windows 10 (build 14393+) and Windows 11 consoles support ANSI codes,
    but the flag is off by default for classic conhost windows. Windows
    Terminal already turns it on, so this is a harmless no-op there.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (AttributeError, OSError, ValueError):
        pass


def supports_color() -> bool:
    """Decide whether ANSI styling should be emitted at all."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("MAXCONN_FORCE_COLOR"):
        return True
    try:
        return sys.stdout.isatty()
    except (AttributeError, OSError, ValueError):
        return False
