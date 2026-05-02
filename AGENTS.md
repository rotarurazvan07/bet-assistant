# AGENTS.md

This file provides guidance to agents when working with code in this repository.

# Project Coding Rules (Non-Obvious Only)
- Always use the core logic in bet_dashboard/backend/core/logic.py for all backend operations
- All database operations use context managers for thread safety
- Ticker services use daemon threads that must be handled carefully to prevent race conditions
- Environment variables are loaded via os.getenv with defaults in all cases
- Profile configurations are loaded from YAML files

# Project Build/Lint/Test Commands

## Build/Lint/Test Commands

- Backend tests: `python -m pytest tests/`
- Frontend tests: `npm test` (from bet_dashboard/frontend/)
- Linting: `ruff check .` for Python, `npm run lint` for frontend
- Backend run: `uvicorn main:app --reload --port 8000` (from bet_dashboard/backend/)
- Frontend build: `npm run build` (from bet_dashboard/frontend/)
- Frontend dev: `npm run dev` (from bet_dashboard/frontend/)

# Crawler Modes

## Standard Workflow
1. `prepare-scrape` - Collect URLs and create chunk tasks
2. `scrape` - Scrape matches into chunk DBs
3. `merge` - Merge chunk DBs into final DB

## Odds Enrichment Workflow
1. `prepare-odds-scrape` - Generate mapping files for odds scraping workers
2. `odds-scrape` - Scrape odds for a worker using its mapping file into a worker DB
3. `merge-odds` - Merge all worker odds DBs into a single final odds DB

## Mode Details

### prepare-odds-scrape
```bash
python -m bet_crawler.crawl --mode prepare-odds-scrape \
  --matches_db_path final.db \
  --config_dir ./config \
  --workers 4
```
Generates `odds_mapping_worker_1.json`, `odds_mapping_worker_2.json`, etc.

### odds-scrape
```bash
python -m bet_crawler.crawl --mode odds-scrape \
  --matches_db_path final.db \
  --mapping_file odds_mapping_worker_1.json \
  --worker_db_path worker-1.db \
  --config_dir ./config
```
Creates a worker DB with matches from rowids, then scrapes odds into it.

### merge-odds
```bash
python -m bet_crawler.crawl --mode merge-odds \
  --odds_db_path final-odds.db \
  --workers_dir ./workers \
  --config_dir ./config
```
Merges all `worker-*.db` files from workers_dir into final odds DB.

## Database Structure

Each worker DB contains:
- Full match data (home_team, away_team, datetime, predictions)
- Serialized odds objects (JSON) in the `odds` column
- Rowids preserved from source DB for mapping

The final odds DB is created by merging all worker DBs using fuzzy deduplication.