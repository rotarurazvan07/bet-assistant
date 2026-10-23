#!/usr/bin/env python3
"""One-time migration: rewrite pre-U1 slip leg market labels to canonical keys.

WHEN/WHY TO RUN (one-time, post-U1)
------------------------------------

Before PR #114's U1 key unification, ``slips.db``'s ``legs.market`` column
persisted the *display* label of the market. U1 made the canonical key (the
persisted Odds/DB field spelling - ``home``, ``btts_yes``, ``over_25`` ...)
the single market identity, and all writers now emit that spelling. Old rows
still carry the legacy label, which renders verbatim in the UI (frontend
``marketLabel()`` falls back to the raw string) and is rejected if such a
leg is ever re-saved by newer builds.

Run this script ONCE per pre-U1 ``slips.db`` copy, AFTER deploying a build
that contains it:

    python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --dry-run
    python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --yes

It is a standalone USER-RUN tool: nothing in the application calls it, and
it is never executed by app startup or the pipeline.

WHAT IT TOUCHES
---------------

Only ``legs.market`` (TEXT) in the given SQLite database. ``market_type``,
the ``slips`` table and every other column are left untouched. matches.db /
odds_history / profiles never carried market labels and need no migration.

SAFETY
------

- Dry-run is the DEFAULT: without ``--yes`` the script reports planned work
  and changes nothing.
- A byte-copy backup (``<db>.bak-<UTC timestamp>``, sha256 + size printed
  for source and backup) is written BEFORE any write; writes happen only
  after a successful backup.
- Values that are neither canonical keys nor known legacy labels abort the
  run (exit 3) before ANY write, so unknown data is never silently mangled.
- The update is a SINGLE transaction over the whole database.
- Idempotent: a second run finds zero legacy values and reports
  "nothing to do" (exit 0).
- After ``--yes`` a verification pass re-counts classifications and fails
  the run (exit 4) if any legacy value survives; the backup remains as the
  recovery path.

Exit codes: 0 ok / 1 db missing / 2 backup failed (argparse usage errors
also exit 2) / 3 unknown values / 4 verification failed after write /
5 unreadable database (locked, corrupt, or not a slips database).
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

# bet_framework lives at the repo root; bootstrap so the script runs from any cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bet_framework.markets.catalog import MARKET_BY_KEY, MARKET_CATALOG  # noqa: E402  (import follows the sys.path bootstrap above)

# Single source of naming is the catalog: pre-U1 rows stored MarketSpec.label
# ('1', 'BTTS Yes', ...); canonical rows store MarketSpec.key ('home', ...).
# Derived at runtime - this script deliberately declares no market literals.
_LABEL_TO_KEY: dict[str, str] = {spec.label: spec.key for spec in MARKET_CATALOG}


def _classify(value: str) -> str:
    """Classify one distinct legs.market value: canonical / legacy / unknown."""
    if value in MARKET_BY_KEY:
        return "canonical"
    if value in _LABEL_TO_KEY:
        return "legacy"
    return "unknown"


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT market, COUNT(*) FROM legs WHERE market IS NOT NULL GROUP BY market").fetchall()
    result = {"canonical": 0, "legacy": 0, "unknown": 0}
    for value, count in rows:
        result[_classify(str(value))] += int(count)
    return result


def _classification_table(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    rows = conn.execute("SELECT market, COUNT(*) FROM legs WHERE market IS NOT NULL GROUP BY market").fetchall()
    table = [(_classify(str(value)), str(value), int(count)) for value, count in rows]
    table.sort(key=lambda r: (r[0], r[1]))
    return table


def _print_table(table: list[tuple[str, str, int]]) -> None:
    print("  classification  value                 rows")
    for kind, value, count in table:
        print(f"  {kind:<13}  {value!r:<20}  {count}")


def make_backup(db_path: Path) -> Path | None:
    """Copy the DB next to itself via SQLite online backup; None on failure.

    The online backup API (not shutil.copy2) captures a consistent snapshot even
    when the source runs in WAL mode with un-checkpointed commits, so the backup
    can never be silently torn/stale.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    if backup.exists():
        print(f"BACKUP FAILED: {backup} already exists; refusing to overwrite it.", file=sys.stderr)
        return None
    try:
        src = sqlite3.connect(f"file:{urllib.parse.quote(str(db_path))}?mode=ro", uri=True, timeout=30)
        try:
            dst = sqlite3.connect(backup)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except (OSError, sqlite3.Error) as exc:
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        return None
    for path, label in ((db_path, "source"), (backup, "backup")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{label}: {path}  sha256={digest}  bytes={path.stat().st_size}")
    return backup


def _apply_updates(db_path: Path, planned: list[tuple[str, str, int]]) -> dict[str, int] | None:
    """Apply planned updates in ONE transaction; re-classify after (None on error)."""
    try:
        conn = sqlite3.connect(f"file:{urllib.parse.quote(str(db_path))}", uri=True, timeout=30)
    except sqlite3.Error as exc:
        print(f"cannot open database for write: {exc}", file=sys.stderr)
        return None
    try:
        with conn:  # single transaction: commits on success, rolls back on error
            for value, key, _count in planned:
                conn.execute("UPDATE legs SET market=? WHERE market=?", (key, value))
        return _counts(conn)
    except sqlite3.Error as exc:
        print(f"write failed: {exc}", file=sys.stderr)
        return None
    finally:
        conn.close()


def _scan(db_path: Path) -> tuple[int, dict[str, int], list[tuple[str, str, int]]] | tuple[int, None, None]:
    """Open read-only and classify; (exit_code, counts, table) or (5, None, None)."""
    try:
        conn = sqlite3.connect(f"file:{urllib.parse.quote(str(db_path))}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as exc:
        print(f"cannot open database: {exc}", file=sys.stderr)
        return 5, None, None
    try:
        return 0, _counts(conn), _classification_table(conn)
    except sqlite3.Error as exc:
        print(f"cannot read legs table (wrong database file?): {exc}", file=sys.stderr)
        return 5, None, None
    finally:
        conn.close()


def migrate(db_path: Path, apply: bool) -> int:
    """Scan, plan, and (with apply=True) back up + update legs.market keys."""
    if not db_path.exists():
        print(f"database not found: {db_path}", file=sys.stderr)
        return 1

    code, before, table = _scan(db_path)
    if code != 0:
        return code

    print(f"database: {db_path}")
    print(f"before: canonical={before['canonical']} legacy={before['legacy']} unknown={before['unknown']}")
    _print_table(table)

    if before["unknown"] != 0:
        print(
            "REFUSING TO WRITE: unknown market values present. Add them to the catalog or clean the data, then re-run.",
            file=sys.stderr,
        )
        return 3

    if before["legacy"] == 0:
        print("nothing to do: no legacy labels remain (idempotent no-op)")
        return 0

    planned = [(row[1], _LABEL_TO_KEY[row[1]], row[2]) for row in table if row[0] == "legacy"]
    if not apply:
        print("dry-run (no changes written). planned updates:")
        for value, key, count in planned:
            print(f"  UPDATE legs SET market={key!r} WHERE market={value!r}  ({count} rows)")
        print("re-run with --yes to apply.")
        return 0

    backup = make_backup(db_path)
    if backup is None:
        return 2

    after = _apply_updates(db_path, planned)
    if after is None:
        return 5
    print(f"after: canonical={after['canonical']} legacy={after['legacy']} unknown={after['unknown']}")
    if after["legacy"] != 0 or after["unknown"] != 0:
        print("VERIFICATION FAILED: legacy/unknown values remain; backup retained.", file=sys.stderr)
        return 4
    total = sum(count for _v, _k, count in planned)
    print(f"done: {backup.name} kept as backup; migrated {total} rows.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse arguments and run the migration."""
    parser = argparse.ArgumentParser(
        description=(
            "One-time post-U1 migration: rewrite pre-U1 slip leg market labels to "
            "canonical keys. Dry-run by default; --yes writes after a backup."
        ),
    )
    parser.add_argument(
        "--db",
        default="workspace/data/slips.db",
        help="path to slips.db (default: workspace/data/slips.db)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report planned changes only (default)")
    mode.add_argument("--yes", action="store_true", help="apply the migration after a backup")
    args = parser.parse_args(argv)
    return migrate(Path(args.db), apply=args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
