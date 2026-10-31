## Why a NEW PR (not the same PR as #114)

User approved the fix plan as 'the same PR', but **#114 was already MERGED to main** (squash-merged as 49fa2ec) before implementation started. A merged PR cannot receive new commits, so this work lands as a fresh branch off main: `fix/market-label-cleanup`. Same single coherent change-set, same review-first policy — **DO NOT MERGE without user approval**.

## What (all 4 post-merge items)

| # | Item | Change |
|---|---|---|
| 1 | **Builder Markets filter showed raw keys** (HOME / OVER_25 / BTTS_YES) | `BuilderPanel.tsx` renders `marketLabel(m)` (the existing helper Discover/Live Preview already use) instead of the raw canonical key. `included_markets` identity untouched. Regression test pins labels and rejects raw keys. |
| 2 | **Analytics breakdown + Best/Avoid cards showed raw strings** | `Analytics.tsx` wraps breakdown rows and both cards in `marketLabel()`. Outcome math untouched — `_predict_outcome_from_score` dispatches on `market_type` only (proven in the analysis artifact). Test asserts labels render, raw keys never. |
| 3 | **Old slips still showed pre-U1 labels** (Track table) | DATA issue: `legs.market` persisted `MarketSpec.label` pre-U1. New **user-run, standalone** migrator `scripts/migrate_slip_leg_keys.py`: dry-run default; classification report; sha256+size backup before any write; refuses to write on unknown values; single transaction; idempotent; post-write verification. Label map derived at runtime from `MARKET_CATALOG` — no hardcoded literals. Guide: `docs/migration.md`. |
| 4 | **One-cycle legacy shim removal** (#116) | Deleted `keys.legacy_market_key`, `views.LEGACY_LABEL_TO_KEY`, the `slips.py` fallback (canonical `MarketKey()` only — re-saving an unmigrated leg now fails loudly, matching U1's fail-loud policy), contract test + prose. Kept `stripped_key`/`ODDS_PREFIX` (movement payloads). Zero references remain over tracked files (the grep gate stays empty: the migrator derives its map into a private `_LABEL_TO_KEY` constant and docs avoid the deleted symbol names). |

## ⚠️ RUN ORDER (migration ↔ shim removal coupling)

1. **Run the migrator on your slips.db BEFORE (or immediately after) upgrading to this build:**
   ```bash
   python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --dry-run
   python scripts/migrate_slip_leg_keys.py --db workspace/data/slips.db --yes
   ```
2. Until migrated, old legs still DISPLAY fine (read path is passthrough), but re-saving an unmigrated leg fails loudly (`Invalid market`) instead of auto-translating — the removed shim's job is done.
3. Frontend `betting_tips_state` localStorage key is bumped to `betting_tips_state_v2` in this PR so stale pre-U1 pending legs drop cleanly instead of failing validation.

Only `slips.db` needs this. matches.db / odds_history / profiles already carry canonical spellings (verified in the analysis).

## Root-cause analysis

.a0proj/_bmad-output/planning-artifacts/research/post-u1-label-deviation-2026-10-22.md (file:line verified @ b521f5e)

## Local gates

- pytest: framework **499 passed** (86.90%) / crawler **235 passed** (88.26%) / backend **520 passed** (98.18%)
- ruff CI-style (`--select E,F,B,C,SIM,PERF`) + `ruff format --target-version py313`: clean on all changed files
- mypy (py3.14, CI-style): no new codes vs main — the single pre-existing `slips.py:81 arg-type` error reproduces on pristine main (baseline)
- frontend: `tsc --noEmit` 0 errors, `eslint` 0 issues, `codegen:markets:check` in sync
- vitest: targeted files green (BuilderPanel 27, Analytics 9, BettingTips 22); full suite + Playwright CI-verified (local container worker-pool START_TIMEOUT is a known env limitation)
- migrator smoke-tested against scratch COPIES under `tmp/` (help / dry-run no-write / --yes + backup / idempotent re-run / unknown-value exit 3 / missing-db exit 1). **NOT run against any real workspace DB.**

Closes #117 · Closes #116
## Post-CR hardening (follow-up commit 5406c23)

- Migrator: sqlite **online backup API** instead of `shutil.copy2` (consistent snapshot under WAL; no torn/stale backup), refuses to overwrite an existing backup, wraps open/scan/write in `sqlite3.Error` -> **exit 5** with a clear message (wrong `--db` / locked / corrupt) instead of a traceback, URI-encoded paths, busy timeout 30s, complexity split (`_scan`/`_apply_updates`) under ruff C901.
- `slips.py`: `except ValueError` only (dead `KeyError` clause removed); comment corrected - validation rejects unknown/legacy labels with a 400 (validate_manual_leg allow-list) BEFORE this point.
- Docs: `docs/frontend.md` gains the market display convention note (`marketLabel()` single label source); `docs/migration.md` documents the argparse exit-2 collision + exit 5.
