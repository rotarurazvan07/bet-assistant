<!-- bmad:context -->
<!-- Verified 2026-09-05. Managed by an automated context refresher; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## bet-assistant

Automated betting intelligence platform: 18+ crawlers, consensus engine, slip builder, real-time React dashboard. Python 3.14 (FastAPI, scrape-kit), Node 22+ (React 19, TypeScript, Vite, MUI v9), Docker. Planning in `docs/`, specs in `/`.

## Policy

- Never push to `main`; PRs only, one approval required (CI enforces via branch protection).
- Never hand-edit `workspace/config/` — source of truth is `config/` (copied on first container start).
- Never hand-edit generated databases (`workspace/data/*.db`) — they are pipeline outputs.
- Secrets only via `.env` (GitHub secrets in CI); `.env` is gitignored.

## Where things are

- Crawler CLI (5 modes): `bet_crawler/crawl.py` — `prepare-scrape | scrape | merge | generate-slips | validate-slips`
- Finders (18+): `bet_crawler/finders/` — each source extends `BaseMatchFinder`
- Pipeline stages: `bet_crawler/crawl_core/` — `prepare_scrape.py`, `scrape.py`, `merge.py`, `generate_slips.py`, `validate_slips.py`
- Frontend (5 tabs): `bet_dashboard/frontend/src/pages/` — `BettingTips`, `SmartBuilder`, `Slips`, `Analytics`, `Services`
- Backend (8 routers): `bet_dashboard/backend/routers/` — `matches`, `builder`, `profiles`, `slips`, `analytics`, `services`, `odds_history`, `system`
- Core logic: `bet_dashboard/backend/core/logic.py` — `AppLogic` (unified business logic + TickerService daemons)
- Framework: `bet_framework/` — `BetAssistant` (slip build/validate), `MatchesManager` (buffered SQLite + fuzzy dedup), `consensus.py`, `scoring.py`
- Config (source of truth): `config/` — `scraper_config.yaml` (crawler keys, runner sets, skip patterns), `similarity_config.yaml` (team matching), `profiles/*.yaml` (risk profiles)
- Docker stack: `setup/compose.yaml` — 3 services (bet-assistant, runner, bet-updater)
- Tests: `bet_framework/tests/`, `bet_crawler/tests/`, `bet_dashboard/backend/tests/`, and frontend Vitest/Playwright suites

## Running and verifying

- **Docker (recommended)**: `docker compose -f setup/compose.yaml up -d` → http://localhost:3002
- **Frontend dev**: `cd bet_dashboard/frontend && npm run dev` → http://localhost:5173 (proxies `/api`, `/ws` to backend)
- **Backend dev**: `cd bet_dashboard/backend && export MATCHES_DB_PATH=../../workspace/data/matches.db SLIPS_DB_PATH=../../workspace/data/slips.db CONFIG_PATH=../../workspace/config && uvicorn main:app --reload --port 8000`
- **Crawler**: `python -m bet_crawler.crawl --mode <mode> --config_dir config` (runner sets: `actions` cloud, `local` self-hosted, `test`)
- **Python tests**: `cd bet_framework && python -m pytest`; `cd bet_crawler && python -m pytest tests/`; `cd bet_dashboard/backend && python -m pytest tests/ -v`
- **Frontend tests**: `cd bet_dashboard/frontend && npm test`
- **Lint/format**: `ruff check . --fix && ruff format .` (Python, line-length 127, py314); `cd bet_dashboard/frontend && npm run lint` (TypeScript strict, ESLint flat)
- **CI pipeline**: auto-fix → test (3.14 only) → audit (mypy, bandit, semgrep, pip-audit, radon, vulture, interrogate) → gate
- **Scrape workflow**: runs hourly on `self-hosted, linux, bet-runner` + `ubuntu-22.04`; merges chunks, releases `latest-db` tag on `main`

## Conventions that differ from defaults

- Python: line-length 127, target py314, isort `--profile black`, ruff `--select E,F,B,C,SIM,PERF --ignore UP`
- TypeScript: React 19, strict mode, MUI v9 + TailwindCSS + CSS variables (`--bg-base`, `--accent`, `--live`)
- Crawler timezone: `Europe/Bucharest` (from `scraper_config.yaml:local_timezone`)
- Skip patterns: youth (`U\d{2}`), women (`\bW\b`), reserve (`II`, `2`, `III`, `B`, `C`, `Am`, `Res`) — defined in `scraper_config.yaml:SKIP_PATTERNS`
- Runner sets: `actions` (cloud CI), `local` (self-hosted), `test` — never mix in one run
- Match fuzzy dedup: strong-token enforcement caps score at 35 when tokens disjoint (threshold 65) — `similarity_config.yaml:strong_mismatch_cap`
- Consensus: Bayesian shrinkage `adjusted = 50 + (sources/(sources+k)) × (raw - 50)` — `bet_framework/core/consensus.py`
- WebSocket: daemon threads use `ws_manager.broadcast_sync()` (thread-safe via `run_coroutine_threadsafe`)

## Known pitfalls

- Database locked: stale processes hold SQLite files → `lsof workspace/data/matches.db` / `slips.db`, kill and restart
- WebSocket fails in production: nginx must proxy `/ws` with `upgrade` headers (see `setup/nginx.conf`)
- Frontend can't reach backend: verify CORS `allow_origins` in `main.py` includes dev origin; check Vite proxy config
- Finder returns no URLs: test in isolation (`python -c "from bet_crawler.finders.X import X; f=X(print); print(f.get_matches_urls())"`), check Cloudflare blocks, verify key in `crawl.py:_CRAWLER_KEYS` and enabled in Services tab
- Validation doesn't update legs: confirm `result_url` stored in legs table, test URL manually, check `_parse_match_result_html()` in `BetAssistant.py` for source's HTML structure
- Smart Builder "no matches": lower Consensus Floor (40-50%), lower Min Odds (1.01), check Excluded Matches, verify date filters
- Docker containers restart: check `docker compose -f setup/compose.yaml logs` — common: port 3002/8000 conflict, `./workspace/` permissions

## Frontend visual / E2E demo data (binding)

Any frontend test that needs **populated** data must grow **both tracks together** and commit both. Local mocks and the CI e2e DB are one mocked database, two delivery paths — not two independent fixtures.

| Track | When | How |
|---|---|---|
| **Local** (Vite, no backend) | `E2E_BASE_URL` unset | `installDemoApi(page)` from `bet_dashboard/frontend/e2e/fixtures/mock-api.ts` |
| **CI e2e** (docker stack) | `E2E_BASE_URL` set | `setup/seed_e2e.py` via compose `e2e-seed` one-shot — same rows in the isolated volume |

**When you add a new surface** (slips, profiles, odds-history, …):

1. Add the row/shape to `bet_dashboard/frontend/e2e/fixtures/demo-data.ts` (reuse Vitest factories — no second type system).
2. Teach `installDemoApi` to serve it (pathname-only `page.route` — never `**/api/matches*` globs).
3. Teach `setup/seed_e2e.py` to insert the **same** rows into the CI e2e DB (vote-math / schema as the real read path). Keep default `GET /api/slips` empty unless the spec opts in.
4. Commit fixtures, seed, and baselines in the **same change**. Do not land one track without the other.

**Exceptions / never:**

- Empty-state specs stay empty — no `installDemoApi`, no seed rows for that surface.
- Skip `installDemoApi` when `E2E_BASE_URL` is set (CI already has the seeded stack).
- Do **not** seed `npm run dev` or `workspace/data/*.db` (pipeline outputs).
- `e2e-seed` touches only the throwaway compose volume.

<!-- /bmad:context -->

## Published content — no internal bookkeeping

Everything in this repository is published: source, docs, CI config and the
generated OpenAPI contract are all read by people outside the team. Keep them
free of internal-only bookkeeping.

- Do not write acceptance-criteria labels, issue/PR/ticket numbers, internal
  decision or task labels, cycle/wave markers, story/epic/sprint trackers,
  review notes, CI run identifiers or context-anchored commit hashes into
  comments, docstrings, docs or CI step names.
- Write what the code actually does — name the symbol, file or behaviour — and
  drop the bookkeeping label.
- The rule that defines "internal reference" is `.semgrep/no-internal-references.yml`.
  It is enforced by the `Internal-reference hygiene gate` step in the `audit`
  job of `.github/workflows/cicd.yml`; a finding there fails the build.
- The only allowed planning-tool mentions are the two managed-block anchor
  comments above, which the refresher uses to replace this block.
- When a comment is needed, explain the *why* in one line. A comment that only
  records where the work came from belongs in the tracker, not in the repo.

## Canonical market keys (single source of truth)

- Market identity lives ONLY in `bet_framework/markets/`: `catalog.py` (18 `MarketSpec` rows, order-free, values frozen — renaming a persisted key is a data migration), `enums.py` (`MarketKey`/`MarketType` StrEnums — values ARE the persisted DB/Odds field spellings, U1), `keys.py` (`stripped_key`/`ODDS_PREFIX` movement-payload helpers), `views.py` (key-indexed dicts + derived views), `contract.py` (JSON snapshot). No facades, no compat layer: market identity is one spelling everywhere.
- Wire contract: backend response schemas type `market`/`market_type` with the canonical enums (serialized by `.value` — payloads are byte-identical to the old hand-built strings; inputs stay validated strings in routers).
- Frontend: `npm run codegen:markets` (in `bet_dashboard/frontend`) regenerates `src/types/api.generated.ts` + the contract snapshot fixture from the backend; `config/marketConfig.ts` is presentation order + labels ONLY. CI fails on drift (`codegen:markets:check`).
- Adding a market = 1 row in `markets/catalog.py` + 1 frontend order entry + parity tests cover the rest (`tests/test_markets_contract.py`, `src/test/marketsContract.test.ts`).
- Burn-down gate: semgrep `no-raw-market-literals` with `.semgrep/baseline.json` — the baseline may only shrink (ratchet), new raw literals block CI.
