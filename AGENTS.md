<!-- bmad:context -->
<!-- Verified 2026-09-05 against 9dbb473. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## bet-assistant

Automated betting intelligence platform: 18+ crawlers, consensus engine, slip builder, real-time React dashboard. Python 3.11+ (FastAPI, scrape-kit), Node 22+ (React 19, TypeScript, Vite, MUI v9), Docker. Planning in `docs/`, specs in `_bmad-output/`.

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
- Tests: `tests/` — pytest for Python, Vitest for frontend

## Running and verifying

- **Docker (recommended)**: `docker compose -f setup/compose.yaml up -d` → http://localhost:3002
- **Frontend dev**: `cd bet_dashboard/frontend && npm run dev` → http://localhost:5173 (proxies `/api`, `/ws` to backend)
- **Backend dev**: `cd bet_dashboard/backend && export MATCHES_DB_PATH=../../workspace/data/matches.db SLIPS_DB_PATH=../../workspace/data/slips.db CONFIG_PATH=../../workspace/config && uvicorn main:app --reload --port 8000`
- **Crawler**: `python -m bet_crawler.crawl --mode <mode> --config_dir config` (runner sets: `actions` cloud, `local` self-hosted, `test`)
- **Python tests**: `cd bet_dashboard/backend && python -m pytest tests/ -v`
- **Frontend tests**: `cd bet_dashboard/frontend && npm test`
- **Lint/format**: `ruff check . --fix && ruff format .` (Python, line-length 127, py310+); `cd bet_dashboard/frontend && npm run lint` (TypeScript strict, ESLint flat)
- **CI pipeline**: auto-fix → test (3.10/3.11/3.12) → audit (mypy, bandit, semgrep, pip-audit, radon, vulture, interrogate) → gate
- **Scrape workflow**: runs hourly on `self-hosted, linux, bet-runner` + `ubuntu-22.04`; merges chunks, releases `latest-db` tag on `main`

## Conventions that differ from defaults

- Python: line-length 127, target py310+, isort `--profile black`, ruff `--select E,F,B,C,SIM,PERF --ignore UP`
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

<!-- /bmad:context -->