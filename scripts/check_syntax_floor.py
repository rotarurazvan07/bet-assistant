"""AST syntax-floor gate: reject any source file that is not parseable on the
runtime floor (Python 3.11).

Why this exists: the CI auto-fix job previously ran
``pyupgrade --py314-plus`` which rewrote PEP 758 un-parenthesised
``except A, B:`` clauses into Python-3.14-only syntax. CI Test/Audit parse on
3.14 (green) while the E2E docker stack and wheel runtime still run
python:3.11-slim -> SyntaxError at import -> regressions that are invisible to
the 3.14 matrix. The postmortem of that exact incident (PR #93) is why the
floor gate is now wired into the auto-fix job *before* it commits: an
auto-fix sweep that breaks the floor must fail instead of pushing.

Usage:
    python scripts/check_syntax_floor.py [paths...]

With no arguments it checks every git-tracked .py file. Exits non-zero on the
first file that parses only above the floor.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

# Runtime floor for deployable surfaces (docker images, wheels, CI matrix glue).
FLOOR = (3, 11)

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache", ".hypothesis", "graphify-out"}


def tracked_python_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def check(path: Path) -> tuple[bool, str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - disk errors
        return False, f"unreadable: {exc}"
    try:
        ast.parse(source, filename=str(path), feature_version=FLOOR)
    except SyntaxError as exc:
        return False, f"line {exc.lineno}: {exc.msg}"
    return True, ""


def main(argv: list[str]) -> int:
    if argv:
        files = argv
    else:
        files = tracked_python_files()

    violations: list[str] = []
    checked = 0
    for name in files:
        path = Path(name)
        if not path.is_file() and not name.endswith(".py"):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        checked += 1
        ok, detail = check(path)
        if not ok:
            violations.append(f"{name}: {detail}")

    if violations:
        print(f"SYNTAX FLOOR VIOLATIONS ({len(violations)} of {checked} files exceed Python {FLOOR[0]}.{FLOOR[1]}):")
        for line in violations:
            print(f"  {line}")
        return 1

    print(f"syntax floor OK: {checked} files parse on Python {FLOOR[0]}.{FLOOR[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
