---
stepsCompleted:
  - step-01-find-story
  - step-02-load-context
  - step-03-detect-continuation
  - step-04-mark-in-progress
startedAt: 2026-10-23T00:56:04+03:00
lastUpdatedAt: 2026-10-23T00:56:04+03:00
---

# Story 115.1: Post-U1 market-label cleanup (display fixes + migration script + shim removal)

Status: review

## Story

As an operator of the betting dashboard,
I want every market surface to render one human-readable presentation label, old pre-U1 slip rows to be migrated by a user-run script, and the one-cycle legacy translation shim to be gone,
so that the "3 different labels" deviation reported after PR #114 is eliminated with no runtime translation layer.

## Background

PR #114 (U1: canonical keys = persisted DB/Odds field spellings) was MERGED to main as `49fa2ec`. Analysis artifact (read first; file:line verified): `.a0proj/_bmad-output/planning-artifacts/research/post-u1-label-deviation-2026-10-22.md`. It proves exactly TWO deviation classes: ONE display bug (Builder chips) and PRE-U1 DATA (`legs.market` in slips.db persisted `MarketSpec.label`), plus the coupled shim removal (issue #116).

Key proven facts this story relies on:

- `marketLabel()` helper already exists at `bet_dashboard/frontend/src/config/marketConfig.ts:108-110` (`LABEL_BY_KEY[key] ?? key`) and is used correctly by Discover / Live Preview / BettingTips. NO new abstraction.
- `LEGACY_LABEL_TO_KEY` (`bet_framework/markets/views.py:32`) maps pre-U1 labels to canonical keys correctly.
- Analytics outcome math is INDEPENDENT of `legs.market` spelling: `_predict_outcome_from_score` (`bet_dashboard/backend/core/logic.py:202-238`) dispatches on `market_type` ONLY. Display wraps change zero math.
- Read path (`get_slips → _slip_to_dict → _leg_to_dict`) applies NO translation; the shim is WRITE-path only (`routers/slips.py:174-179`).
- matches.db / odds_history / profiles need NO migration (already canonical field spellings) — analysis §D.2 verified.
- Shim references on main (`git grep`): keys.py (def+2 uses+import), views.py (definition), slips.py (import L11, use L175, comment L178), tests/test_markets_contract.py (import L26, test L119-125). Plus prose mentions in `AGENTS.md:88` and `docs/backend.md:471` (update those too).

## Acceptance Criteria

1. **AC-1 Builder filter chips render presentation labels.** `bet_dashboard/frontend/src/components/BuilderPanel.tsx` imports `marketLabel` from `../config/marketConfig` (ALL_MARKETS import path follows; keep `ALL_MARKETS`/`included_markets` identity semantics untouched) and renders `{marketLabel(m)}` at the chip button (main: line 330). Regression test in `components/__tests__/BuilderPanel.test.tsx` asserts the chip text equals `marketLabel(ALL_MARKETS[0])` (e.g. `1` for `home`), NOT the raw key, and that no chip exposes raw key text.
2. **AC-2 Analytics market breakdown + best/worst cards render presentation labels.** `pages/Analytics.tsx` imports `marketLabel` and wraps: breakdown row (main: line 571 `{row.market}`), Best Market card (line 415 `{best ? best.market : '—'}`), Avoid card (line 428 `{worst && worst.edge < 0 ? worst.market : '—'}`). Tests in `pages/__tests__/Analytics.test.tsx` assert labels render (not raw keys) for breakdown rows and the two cards.
3. **AC-3 User-run migration script exists and behaves per spec.** New file `scripts/migrate_slip_leg_keys.py` (NOT code-embedded, NOT run by app startup): CLI `--db <path>` (default `workspace/data/slips.db`) `[--dry-run]` `[--yes]`; dry-run DEFAULT; classifies every distinct `legs.market` value as canonical / legacy-mappable / unknown; unknown values → loud report + exit non-zero WITHOUT touching data; backup (copy DB to `<db>.bak-<UTC timestamp>` in the DB's directory, sha256+size printed for source and backup) BEFORE any write, and write only after a successful backup (backup failure → exit non-zero, no write); `--yes` applies one parameterized `UPDATE legs SET market=? WHERE market=?` per legacy label inside a SINGLE transaction; idempotent (second run: canonical-only, "nothing to do", exit 0); post-check confirms no legacy values remain; report lists per-label before/after counts and residual unknowns. The label→key map is DERIVED at runtime from `bet_framework.markets.catalog.MARKET_CATALOG` (`{spec.label: spec.key}`) — NO hardcoded market literals in the script (semgrep `no-raw-market-key-literals` scans scripts/; also this same PR DELETES `LEGACY_LABEL_TO_KEY`, see AC-4, so the script must not depend on it). Docstring header explains: when/why to run (one-time post-U1, after deploying this build, for slips.db files created before U1), that it touches ONLY `legs.market`, and that `workspace/data/*.db` are pipeline outputs never edited by code.
4. **AC-4 Legacy shim fully removed (issue #116) with zero references.** Delete: `bet_framework/markets/keys.py::legacy_market_key` (main lines 20-42), `import warnings` (L7), `from bet_framework.markets.views import LEGACY_LABEL_TO_KEY` (L10) — KEEP `stripped_key()` and `ODDS_PREFIX` (used by movement payloads); `LEGACY_LABEL_TO_KEY` definition in `views.py` (L30-32 comment + L32); `bet_dashboard/backend/routers/slips.py` import (L11) and try/except fallback — collapse to direct `market = MarketKey(market_str)` inside the existing try (unknown values keep raising ValueError as before; the router's downstream validation surfaces the error — re-saving an unmigrated leg now fails loudly instead of auto-translating; documented in PR body); `bet_framework/tests/test_markets_contract.py` import (L26) + `test_legacy_label_map_covers_pre_u1_spellings` (L119-125); prose mentions in `AGENTS.md:88` and `docs/backend.md:471`. `git grep -E 'legacy_market_key|LEGACY_LABEL_TO_KEY'` over tracked files returns ZERO hits afterwards. `marketLabel()` legacy-fallback behavior NOTE: its `?? key` fallback intentionally makes old labels render verbatim (Track slips still display pre-migration) — no change needed there.
5. **AC-5 localStorage pending-legs cache invalidated.** `bet_dashboard/frontend/src/pages/BettingTips.tsx:22` storage key bumped `betting_tips_state` → `betting_tips_state_v2` so stale pre-U1 pending legs (with legacy labels that the removed shim used to translate) are dropped cleanly on upgrade instead of failing add-to-slip validation. No other storage keys change (`col-visibility`, `slip-minimized`, `betting_tips_excluded_sources` untouched).
6. **AC-6 All gates green, no unexplained drops.** Framework ~500 / crawler ~235 / backend ~520 pytest (per-suite commands from venv-rule); mypy CI-style vs pristine main worktree — no NEW error codes vs the 165 ceiling; ruff check+format clean (len 127, py313 tooling target); frontend `tsc` 0; eslint 0 (2 pre-existing warnings OK); vitest — targeted BuilderPanel/Analytics/BettingTips files green locally (if container worker-pool START_TIMEOUT recurs — known env issue — document and rely on CI for full suite); `npm run codegen:markets:check` in sync (no wire changes expected). Semgrep burn-down gate must still pass (new files must introduce no raw market literals; baseline ratchet shrink-only).
7. **AC-7 Migration script smoke-tested against a COPY only.** Script verified with `--help`, dry-run, and a `--yes` run against a scratch SQLite copy created under `tmp/` (schema + seeded pre-U1 rows, plus a canonical row and an unknown row case). NEVER run against `workspace/data/*.db`. Real workspace DBs are pipeline outputs — untouched (verify `git status` clean for `workspace/`).
8. **AC-8 PR + docs.** One new PR off main (user said "same PR" but #114 is already merged — this is a new branch/PR `fix/market-label-cleanup`, explained in the report and PR body). Docs updated: `docs/backend.md` or new `docs/migration.md` documents when/why to run the migration script (one-time, post-deploy, backup-first); `docs/frontend.md` notes Builder Markets filter renders presentation labels via `marketLabel()`; AGENTS.md/docs shim prose updated per AC-4. PR body documents the ORDER: (1) run migration script on slips.db (before or right after merge — until then old legs still DISPLAY via passthrough but re-saving them fails loudly), (2) then the shim removal is safe. PR opened via gh CLI, NOT merged (user review).

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — BuilderPanel display fix
  - [x] 1.1 `bet_dashboard/frontend/src/components/BuilderPanel.tsx`: change import line 7 to `import { ALL_MARKETS, marketLabel } from '../config/marketConfig';` and line 330 `{m}` → `{marketLabel(m)}`. No other changes (chip styling/uppercase/key semantics unchanged).
  - [x] 1.2 `components/__tests__/BuilderPanel.test.tsx`: add regression test — render, assert `screen.getByRole('button', { name: marketLabel(ALL_MARKETS[0]) })` exists and `screen.queryByText(ALL_MARKETS[0])` is null (raw key not rendered); assert ALL_MARKETS chip count == rendered buttons with those labels. NOTE existing test L152 clicks `screen.getByText(ALL_MARKETS[0])` — must update to the new rendered label (click by role/name) since the DOM text changes from key to label.
- [x] Task 2 (AC: 2) — Analytics display fix
  - [x] 2.1 `pages/Analytics.tsx`: add `import { marketLabel } from '../config/marketConfig';`; wrap breakdown `{row.market}` (L571) → `{marketLabel(row.market)}`; L415 `{best ? marketLabel(best.market) : '—'}`; L428 `{worst && worst.edge < 0 ? marketLabel(worst.market) : '—'}`.
  - [x] 2.2 `pages/__tests__/Analytics.test.tsx`: extend/add tests — breakdown rows render `marketLabel(row.market)` values (e.g. analytics fixture with `market: 'home'` renders `1`, not `home`); Best/Avoid cards render labels not raw keys.
- [x] Task 3 (AC: 3, 7) — migration script
  - [x] 3.1 Write `scripts/migrate_slip_leg_keys.py` per AC-3 (stdlib only: argparse, sqlite3, shutil, hashlib, datetime, pathlib, sys; import MARKET_CATALOG from `bet_framework.markets.catalog` via sys.path bootstrap from repo root so it runs from anywhere).
  - [x] 3.2 Smoke test: create scratch DB in `tmp/` reproducing the legs schema (`bet_framework/BetAssistant.py:236-250`), seed pre-U1 labels + canonical rows; run `--help`, dry-run (verify counts + planned updates + no writes), then `--yes` on the copy (verify updates + backup exists + idempotent second run); seed an unknown value and verify exit non-zero + no writes.
- [x] Task 4 (AC: 8) — docs for the script
  - [x] 4.1 `docs/backend.md` (or new `docs/migration.md` linked from backend.md): when/why to run, exact command, backup semantics, dry-run default, idempotency, failure modes.
- [x] Task 5 (AC: 4) — shim removal
  - [x] 5.1 `bet_framework/markets/keys.py`: remove `import warnings`, remove `LEGACY_LABEL_TO_KEY` import, remove `legacy_market_key` function; keep `ODDS_PREFIX`/`stripped_key`; refresh module docstring (drop one-cycle-shim sentence).
  - [x] 5.2 `bet_framework/markets/views.py`: remove `LEGACY_LABEL_TO_KEY` (+ L30-31 comment).
  - [x] 5.3 `bet_dashboard/backend/routers/slips.py`: remove import L11; L174-179 try/except → `market = MarketKey(market_str)` (ValueError propagates as before the shim existed; the same except class was already the pre-shim behavior — verify against git history that only the shim call is removed, not the error handling contract).
  - [x] 5.4 `bet_framework/tests/test_markets_contract.py`: remove `LEGACY_LABEL_TO_KEY` import (L26) and `test_legacy_label_map_covers_pre_u1_spellings` (L119-125).
  - [x] 5.5 Prose: `AGENTS.md:88` and `docs/backend.md:471` — drop shim mentions.
  - [x] 5.6 Verify: `git grep -E 'legacy_market_key|LEGACY_LABEL_TO_KEY'` → zero tracked hits.
- [x] Task 6 (AC: 5) — localStorage key bump
  - [x] 6.1 `pages/BettingTips.tsx:22`: `betting_tips_state` → `betting_tips_state_v2`.
- [x] Task 7 (AC: 8) — frontend doc note
  - [x] 7.1 `docs/frontend.md`: note Builder Markets filter renders presentation labels via `marketLabel()` (single display convention).
- [x] Task 8 (AC: 6) — full verification
  - [x] 8.1 `.venv/bin/python -m pytest tests/ -v` (framework, repo root); `cd bet_crawler && ../.venv/bin/python -m pytest tests/ -v`; `cd bet_dashboard/backend && ../../.venv/bin/python -m pytest tests/ -v`.
  - [x] 8.2 `.venv/bin/ruff check . --fix && .venv/bin/ruff format .`; mypy CI-style vs pristine main worktree (compare vs `.github/mypy-baseline` ceiling 165; report delta).
  - [x] 8.3 Frontend: `cd bet_dashboard/frontend && npx tsc --noEmit`, `npm run lint`, targeted vitest (BuilderPanel, Analytics, BettingTips) — full suite if worker pool allows; document honestly otherwise.
  - [x] 8.4 `npm run codegen:markets:check`; `.semgrep/check_burn_down.py` (if semgrep available locally; otherwise rely on CI and state so).
- [x] Task 9 (AC: 8) — commit, push, PR
  - [x] 9.1 Explicit-path commits only (NEVER `git add -A`; NEVER stage: `Markdown 2026-09-13.md`, `config/similarity_config.yaml.backup`, `scripts/fetch_near_miss_reports.py`, `graphify-out/`, `.a0proj/`, `tmp/`, `tests/`, caches, `.neuralmind/`, `.serena/`).
  - [x] 9.2 Push `fix/market-label-cleanup`, open PR via `gh` with the migration-order documentation; monitor CI to green; DO NOT merge.

## Dev Notes

### Exact sites (verified on main @ 49fa2ec)

- `bet_dashboard/frontend/src/components/BuilderPanel.tsx`: import L7 `import { ALL_MARKETS } from '../types';`, chip render L330 `{m}` (map at L308, button L311-331, key L312, onClick L314).
- `bet_dashboard/frontend/src/pages/Analytics.tsx`: L415 `{best ? best.market : '—'}`, L428 `{worst && worst.edge < 0 ? worst.market : '—'}`, L571 `{row.market}` (font-mono span in breakdown table row).
- `bet_framework/markets/keys.py`: L7 `import warnings`, L10 `from bet_framework.markets.views import LEGACY_LABEL_TO_KEY`, L20-42 `legacy_market_key`; KEEP L12 `ODDS_PREFIX`, L15-17 `stripped_key`.
- `bet_framework/markets/views.py`: L32 `LEGACY_LABEL_TO_KEY` (+comment L30-31).
- `bet_dashboard/backend/routers/slips.py`: L11 import; L173-179 try/except with `market = MarketKey(legacy_market_key(market_str))` L175, fallback L178-179 comment + `market = market_str`.
- `bet_framework/tests/test_markets_contract.py`: L26 import inside `from bet_framework.markets.views import (...)` group (keep `CONSENSUS_COLUMN_NAMES`, `ODDS_COLUMN_NAMES`), L119-125 the legacy-map test.
- `bet_dashboard/frontend/src/pages/BettingTips.tsx`: L22 `const STORAGE_KEY = 'betting_tips_state';`; write at L174-184, read at L33-35 (filter state reads L72-98 use OTHER keys — do not touch).
- `scripts/` currently has ZERO tracked files (only untracked `fetch_near_miss_reports.py`) — the new script is the first tracked file there; stage it explicitly by path.

### Decisions taken at CS time (inherited from analysis D1-D5 + user tasking)

- D-A: Migration script derives the map from `MARKET_CATALOG` (catalog.py is the single source of naming) — NOT from `LEGACY_LABEL_TO_KEY`, because AC-4 deletes it in the same PR. Rationale: no duplicated literal map, no self-broken script, semgrep-clean.
- D-B: `betting_tips_state` → `_v2` (AC-5) in the SAME PR per analysis §E (shim removal + storage bump together); other storage keys untouched.
- D-C: Analytics wrap proven safe (`_predict_outcome_from_score` dispatches on market_type only); math fields (`row.legs`, `row.win_rate`, `row.edge`, best/worst ordering) untouched — display-only change.
- D-D: No new tracking issue is required to exist for fixes 1-3, but create one (`gh issue create`) referencing analysis + issue #116 so the PR links a concrete issue; story ID `115-1` follows house convention (114-1/114-2).
- D-E: Script UX decisions: ASCII-only output (CI-safe); backup file written NEXT TO the DB (`<db name>.bak-<UTC>`), timestamp format `YYYYMMDDTHHMMSSZ`; dry-run is default and makes zero writes; `--yes` required for writes; if backup fails → exit 2 with message and NO write; unknown values → print classification table + exit 3, NO write (even with `--yes`); post-write verification query re-counts classifications and fails the run if any legacy value remains (exit 4) leaving the backup as recovery path; idempotent no-op run prints counts + exit 0.
- D-F: Script is stdlib-only; `bet_framework` import via `sys.path.insert(0, repo_root)` computed from `__file__` so it runs from any cwd. No new dependencies (audit gate runs pip-audit/vulture — unused-import risk).
- D-G: Local verification of the script uses a scratch DB under `tmp/` ONLY (atomic case-migration test: insert canonical-only copy, run, assert zero updated rows). `workspace/data/` never touched.

### Testing standards (project)

- Vitest per-file with `@testing-library/react`; existing BuilderPanel test file already imports `ALL_MARKETS` from `../../config/marketConfig` — extend, don't duplicate.
- pytest suites each have coverage gates (framework/crawler/backend pytest.ini).
- Known env issues to document honestly: container vitest worker-pool START_TIMEOUT (use targeted files); full semgrep scans are slow.

### References

- [Source: .a0proj/_bmad-output/planning-artifacts/research/post-u1-label-deviation-2026-10-22.md] (root causes A.1-A.4, fix plan C, migration spec D, shim safety E, decisions F, handoff H)
- [Source: bet_framework/markets/catalog.py] (single naming source; MarketSpec fields)
- [Source: bet_dashboard/frontend/src/config/marketConfig.ts:99-110] (ALL_MARKETS, LABEL_BY_KEY, marketLabel)
- [Source: bet_dashboard/backend/core/logic.py:202-238] (_predict_outcome_from_score dispatches on market_type only)
- [Source: .semgrep/no-raw-market-literals.yml + .semgrep/check_burn_down.py] (raw-literal gate; baseline ratchet 95)
- GitHub issue #116 (shim removal checklist)

## Dev Agent Record

### Agent Model Used

pending

### Debug Log References

pending

### Completion Notes List

- AC-1: BuilderPanel.tsx renders marketLabel(m) at chip button; import from ../config/marketConfig. existing ALL_MARKETS/included_markets identity semantics preserved. BuilderPanel.test.tsx: 27/27 green (regression test asserts labels render + raw keys absent; toggle test clicks by label).
- AC-2: Analytics.tsx wraps breakdown row (L572), Best (L416) + Avoid (L429) cards in marketLabel(); outcome math untouched (_predict_outcome_from_score dispatches on market_type only). Analytics.test.tsx: 9/9 green; test derives keys from ALL_MARKETS (no market literals - semgrep ratchet safe).
- AC-3: scripts/migrate_slip_leg_keys.py. Label map derived at runtime from MARKET_CATALOG (NOT from LEGACY_LABEL_TO_KEY - deleted in same PR). Smoke-tested on scratch COPY under tmp/mig-smoke/: --help ok; dry-run default (classification table + planned updates, zero writes); --yes (sha256+size backup, single-transaction update, migrated 5 rows); idempotent re-run exit 0; unknown value -> exit 3 with zero writes; missing db -> exit 1. NEVER run against workspace/data/*.db (untouched; only workspace/config exists locally).
- AC-4: shim deleted (keys.py slimmed to helpers; views.py; slips.py try/except collapses to direct MarketKey with documented fail-loud comment; contract test; prose). git grep legacy_market_key|LEGACY_LABEL_TO_KEY -> zero tracked hits.
- AC-5: betting_tips_state -> betting_tips_state_v2 (other storage keys untouched); test updated; 22/22 green.
- AC-6 gates (local): framework 499 (86.90%) / crawler 235 (88.26%) / backend 520 (98.18%); ruff CI-style + format py313 clean on changed files; mypy py3.14 CI-style: only the pre-existing slips.py:81 arg-type error (reproduces on pristine main); tsc 0; eslint 0; codegen:markets:check in sync; vitest targeted files green (full suite + Playwright CI-verified - local worker-pool START_TIMEOUT known env limitation); semgrep binary unavailable locally -> mirror literal scan clean (no new raw literals after literal-free test rewrite), baseline untouched.
- AC-7/AC-8: PR #118 opened (base main, branch fix/market-label-cleanup, head 82fe3d1) documenting run order (migration before/right after upgrade) + why this is a NEW PR (#114 already merged); closes #117 + #116. CI monitored next.

### File List

Modified:
- bet_dashboard/frontend/src/components/BuilderPanel.tsx (AC-1: marketLabel import + chip render)
- bet_dashboard/frontend/src/components/__tests__/BuilderPanel.test.tsx (AC-1 regression tests; toggle test updated to label)
- bet_dashboard/frontend/src/pages/Analytics.tsx (AC-2: marketLabel import + 3 wraps)
- bet_dashboard/frontend/src/pages/__tests__/Analytics.test.tsx (AC-2 tests, literal-free via ALL_MARKETS)
- bet_dashboard/frontend/src/pages/BettingTips.tsx (AC-5: STORAGE_KEY -> betting_tips_state_v2)
- bet_dashboard/frontend/src/pages/__tests__/BettingTips.test.tsx (test follows v2 key)
- bet_framework/markets/keys.py (AC-4: shim + warnings/LEGACY_LABEL_TO_KEY imports removed; stripped_key/ODDS_PREFIX kept)
- bet_framework/markets/views.py (AC-4: LEGACY_LABEL_TO_KEY removed)
- bet_dashboard/backend/routers/slips.py (AC-4: shim import + fallback -> direct MarketKey)
- bet_framework/tests/test_markets_contract.py (AC-4: legacy-map import + test removed)
- AGENTS.md (AC-4: shim prose updated)
- docs/backend.md (AC-4: shim prose updated)

Added:
- scripts/migrate_slip_leg_keys.py (AC-3: user-run migrator; executable; stdlib-only)
- docs/migration.md (AC-3/AC-8: when/why/run/backup/order documentation)
