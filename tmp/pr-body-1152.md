## Problem (user report)

A slip leg under_25 (rendered `U2.5`) with live score 1-0 shows **RED** (lost) although under 2.5 with 1 goal is WINNING.

## Root cause (audited, file:line)

Backend outcome math is U1-clean (`bet_framework/core/outcomes.py` dispatches on `MarketType` and compares against `MarketKey` enum members; `analytics._predict_outcome_from_score` dispatches on the canonical `market_type`). The defect is the **frontend live badge**: `bet_dashboard/frontend/src/utils/colorUtils.ts::getPotentialStatusColor` still matched PRE-U1 spellings (`'1'`,`'X'`,`'2'`,`'BTTS No'`,`^Over ([\d.]+)$`,`^Under ([\d.]+)$`,`'1X'`,`'12'`,`'X2'`) with one stray canonical check (`'btts_yes'`). After U1 renamed market keys to DB field spellings (`home/draw/away/btts_yes/btts_no/over_25/under_25/dc_1x/dc_12/dc_x2`) nothing matched, so every over/under/DC leg fell through to the odds heuristic (`odds > 2.0 ? win : loss`): a U2.5 leg (odds <= 2) at 1-0 rendered `var(--potential-loss)` = RED.

## Fix (no translation layer)

`getPotentialStatusColor` now resolves the market through `MARKET_COLUMNS` (canonical identity) and derives semantics from the KEY itself: goals line from the key suffix (`over_25` -> 2.5), yes/no for BTTS, `_1x`/`_12`/`_x2` for double chance, exact `home`/`draw`/`away` for 1X2. Pre-U1 labels intentionally do NOT match (no compat shim) and keep the historical odds fallback. The file spells no market-key literals (semgrep `no-raw-market-literals` stays clean).

## Proof (before/after)

- **RED, unfixed code** (same suite, `git checkout` of the pre-fix file): `Tests 7 failed | 1 passed (8)`; first failure: `user case: under_25 @ live 1-0 is WINNING` -> `AssertionError: expected 'var(--potential-loss)' to be 'var(--potential-win)'` (the reported RED).
- **GREEN, fixed code**: direct call on the same module returns `var(--potential-win)` for `under_25` @ `1 - 0` (and `over_25` @ `1 - 0` -> loss; 2-goal boundary: over LOST / under WON, pinned).
- **Backend proof matrix** (new, `bet_framework/tests/test_outcomes.py::test_u1_all_markets_outcome_matrix`): all 19 canonical keys x representative scores incl. the user case and boundaries -> `141 passed` in file; **full framework suite 537 passed** (was 499 before this change; +38 matrix cases, no unexplained drops).

## Gates

| Gate | Result |
|---|---|
| pytest framework (full) | **537 passed** (86.90%, gate 80%) |
| pytest crawler / backend | unchanged suites, no drops (no backend code touched) |
| ruff CI-style (`--select E,F,B,C,SIM,PERF`, len 127) | clean on changed files |
| mypy CI-style | clean |
| tsc / eslint | 0 / 0 |
| semgrep burn-down | no new literals (baseline untouched) |
| vitest full suite + E2E | CI-verified (container worker-start START_TIMEOUT limits local full runs) |

## Notes

- `scripts/migrate_slip_leg_keys.py` (PR #118) was NOT run against any real database; `workspace/` untouched (this checkout has no `workspace/data`).
- Branch `fix/outcome-validation-u1-keys` off `origin/main` (`0f9d681`, post-#118) - independent from the merged #118.
- Not merged: awaits review.
