# One-time data migrations

User-run maintenance scripts for persisted data. These scripts are **standalone tools**: nothing in the application calls them, and they never run at app startup or in the scrape pipeline. Run them by hand, from the repository root, when the accompanying note says the data needs them.

`workspace/data/*.db` files are pipeline outputs — application code never edits them outside these explicit, user-approved runs.

## slips.db: pre-U1 market labels → canonical keys

**When:** once, after deploying a build that contains `scripts/migrate_slip_leg_keys.py`, for any `slips.db` created before U1 key unification.

**Why:** pre-U1 writers persisted the market *display label* in `legs.market` (`'1'`, `'X'`, `'BTTS Yes'`, `'Over 2.5'`, `'X2'`). U1 made the canonical key — the persisted Odds/DB field spelling (`home`, `draw`, `btts_yes`, `over_25`, `dc_x2`) — the single market identity, and new writes emit that spelling. Old rows still display fine (the frontend `marketLabel()` helper falls back to the raw string), but they are rejected if such a leg is ever re-saved.

**Run:**

```bash
# 1. Report-only dry run (default; changes nothing)
python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --dry-run

# 2. Apply (backs up first, then migrates in a single transaction)
python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --yes
```

**Behaviour:**

- Backs up to `slips.db.bak-<UTC timestamp>` next to the database before any write; prints sha256 + size for source and backup. No backup, no write.
- Classifies every distinct `legs.market` value (canonical / legacy / unknown) and prints counts.
- Unknown values abort the run (exit 3) before any write — add them to the catalog or clean the data, then re-run.
- Applies one parameterized `UPDATE` per legacy label in a single transaction; re-verifies afterwards (exit 4 if any legacy value survived; the backup is the recovery path).
- Idempotent: a second run reports `nothing to do` (exit 0).
- Touches only `legs.market`. `market_type`, the `slips` table and all other columns are untouched.

**Other databases:** `matches.db`, `odds_history` and risk profiles carry canonical field spellings already and need no migration.

**Order note:** run this migration before (or right after) upgrading to a build without the one-cycle legacy read shim (removed in the same release). Until it runs, old legs still display — but re-saving an unmigrated leg fails loudly (`Invalid market`) instead of being auto-translated. The frontend `betting_tips_state` localStorage key was bumped in the same change so stale pending legs drop cleanly instead of failing validation.

## Exit codes

`scripts/migrate_slip_leg_keys.py`: `0` ok / `1` database missing / `2` backup failed (argparse usage errors, e.g. `--yes --dry-run` together, also exit `2`) / `3` unknown values present / `4` verification failed after write / `5` unreadable database (locked, corrupt, or not a slips database - e.g. pointing `--db` at `matches.db`).

