from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    dist = ROOT / "dist"
    if dist.exists():
        for artifact in dist.glob("*"):
            artifact.unlink()

    checks = [
        ["ruff", "check", "src", "tests"],
        ["pytest", "-v"],
        [sys.executable, "-m", "build"],
    ]
    for check in checks:
        run(check)

    twine = shutil.which("twine")
    if twine is None:
        print("twine not found; install maxconn[dev] before running release checks")
        return 1
    run([twine, "check", "dist/*"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
