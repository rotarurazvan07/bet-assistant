#!/usr/bin/env python3
"""Syntax floor gate: every .py must parse on the oldest runtime (3.11).

Docker images run python:3.11 (setup/Dockerfile) while CI runs 3.14 — code
that parses only on 3.14 (e.g. PEP 758 ``except A, B:``) passes CI and
crashes the E2E stack at import. Run from the repo root:

    python scripts/check_syntax_floor.py

Exits 1 listing violations; prints OK otherwise.
"""

import ast
import pathlib
import sys

FLOOR = (3, 11)
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "workspace",
    "graphify-out",
    ".neuralmind",
    ".serena",
    ".a0proj",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
}


def main() -> int:
    """Scan the repo for files that violate the 3.11 syntax floor."""
    bad = []
    for p in pathlib.Path(".").rglob("*.py"):
        if SKIP_DIRS.intersection(p.parts):
            continue
        try:
            ast.parse(p.read_text(), filename=str(p), feature_version=FLOOR)
        except SyntaxError as e:
            bad.append(f"{p}:{e.lineno}: {e.msg}")
        except UnicodeDecodeError as e:
            bad.append(f"{p}: unicode: {e}")
    if bad:
        print("\n".join(bad))
        print(f"\n{len(bad)} file(s) violate the Python {FLOOR[0]}.{FLOOR[1]} syntax floor")
        return 1
    print(f"Syntax floor OK: all .py files parse on Python {FLOOR[0]}.{FLOOR[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
