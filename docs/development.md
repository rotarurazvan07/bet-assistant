# Development Guide

## Overview

This guide covers setting up a local development environment for all parts of Bet Assistant.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend, crawler, framework |
| Node.js | 22+ | Frontend build tooling |
| Docker | 24+ | Containerized services |
| Git | 2.40+ | Version control |
| SQLite3 | 3.40+ | Database inspection |

### Recommended IDE Setup

**VS Code Extensions**:
- Python (Microsoft)
- Pylance (Microsoft)
- TypeScript Vue Plugin (Vue)
- ESLint (Microsoft)
- Prettier (Prettier)
- Docker (Microsoft)
- GitHub Actions (GitHub)

---

## Quick Start (Docker)

```bash
# Clone and start
git clone https://github.com/rotarurazvan07/bet-assistant.git
cd bet-assistant
docker compose -f setup/compose.yaml up -d

# Access
# Frontend: http://localhost:3002
# API: http://localhost:3002/api
# API Docs: http://localhost:3002/docs
```

---

## Frontend Development

### Setup

```bash
cd bet_dashboard/frontend

# Install dependencies
npm ci

# Start dev server (with HMR)
npm run dev
# http://localhost:5173

# Type checking
npm run lint

# Build for production
npm run build
# Output: dist/
```

### Project Structure

```
frontend/
├── src/
│   ├── pages/           # 5 dashboard tabs
│   │   ├── BettingTips.tsx
│   │   ├── SmartBuilder.tsx
│   │   ├── Slips.tsx
│   │   ├── Analytics.tsx
│   │   └── Services.tsx
│   ├── components/      # Reusable UI components
│   │   ├── ui/          # Base components (Tooltip, Toggle, Badge, Card)
│   │   ├── MatchRow.tsx
│   │   ├── FloatingSlipBuilder.tsx
│   │   ├── BuilderPanel.tsx
│   │   ├── AnalyticsDashboard.tsx
│   │   └── ServiceCard.tsx
│   ├── hooks/           # Custom React hooks
│   │   ├── useSocket.ts
│   │   └── useProfileSelection.ts
│   ├── api/             # Backend API client
│   │   ├── client.ts    # Axios instance
│   │   ├── data.ts      # Builder, profiles, slips, analytics
│   │   ├── matches.ts   # Match fetching
│   │   └── oddsHistory.ts
│   ├── config/          # Market configuration
│   │   └── marketConfig.ts
│   ├── types/           # TypeScript interfaces
│   │   └── index.ts
│   ├── utils/           # Helper functions
│   │   ├── betUtils.ts
│   │   ├── calculationUtils.ts
│   │   ├── colorUtils.ts
│   │   └── teamUtils.ts
│   ├── App.tsx          # Root + Router + WS Provider
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles + CSS variables
├── public/              # Static assets
├── vite.config.ts       # Vite config
├── tsconfig.json        # TypeScript config
├── tailwind.config.js   # Tailwind config
└── eslint.config.js     # ESLint config
```

### Key Development Patterns

#### Adding a New Page

1. Create `src/pages/NewPage.tsx`
2. Add route in `App.tsx`
3. Add tab in `Layout.tsx`
4. Add navigation in global filters

#### Adding a New API Endpoint

1. Add types in `src/types/index.ts`
2. Add API function in `src/api/data.ts` (or new file)
3. Use in component with `useEffect` + state

#### State Management

- **Global filters**: `Layout.tsx` context (date range)
- **Page state**: Local `useState` + `localStorage` persistence
- **WebSocket**: `useSocket` hook → event handlers
- **Profiles**: `useProfileSelection` hook

#### Styling

- **MUI v9**: Component library (`@mui/material`, `@mui/x-date-pickers`)
- **TailwindCSS**: Utility classes for layout/custom styles
- **CSS Variables**: Design tokens in `index.css` (`--bg-base`, `--accent`, `--live`, etc.)
- **Glassmorphism**: `backdrop-filter: blur(16px)` + semi-transparent backgrounds

### Debugging

```bash
# React DevTools browser extension
# Vite HMR console for fast refresh
# Network tab for API calls
# WebSocket tab for WS messages
```

---

## Backend Development

### Setup

```bash
cd bet_dashboard/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ../../bet_framework
pip install -e ../../bet_crawler

# Set environment variables
export MATCHES_DB_PATH=../../workspace/data/matches.db
export SLIPS_DB_PATH=../../workspace/data/slips.db
export CONFIG_PATH=../../workspace/config

# Start with hot reload
uvicorn main:app --reload --port 8000
# http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Project Structure

```
backend/
├── main.py              # App factory + lifespan
├── routers/             # 8 API routers
│   ├── matches.py       # GET /api/matches
│   ├── builder.py       # POST /api/builder/preview, excluded, leagues
│   ├── profiles.py      # CRUD /api/profiles
│   ├── slips.py         # CRUD /api/slips, validate, generate
│   ├── services.py      # GET /api/services, toggle, settings
│   ├── analytics.py     # GET /api/analytics
│   ├── odds_history.py  # GET /api/odds-history
│   └── system.py        # POST /api/pull, GET /api/status, WS /ws
├── core/                # Core modules
│   ├── logic.py         # AppLogic - unified business logic
│   ├── ticker_service.py # Daemon thread polling
│   ├── ws.py            # WebSocket connection manager
│   ├── market_config.py # MarketDef + constants
│   ├── schemas.py       # Pydantic request/response models
│   ├── analytics_utils.py # Statistics calculations
│   └── config_helpers.py # Profile YAML conversion
├── utils/               # Helpers
│   ├── profile_utils.py
│   └── json_utils.py
└── requirements.txt
```

### Key Development Patterns

#### Adding a New Endpoint

1. Define Pydantic models in `core/schemas.py`
2. Add router function in appropriate `routers/*.py`
3. Register router in `main.py`
4. Access `AppLogic` via `request.app.state.app_logic`

#### Working with AppLogic

```python
# In router
def _get(request: Request):
    return request.app.state.app_logic

@router.get("/my-endpoint")
def my_endpoint(request: Request):
    logic = _get(request).logic
    # Use logic methods
    return logic.some_method()
```

#### Background Services (TickerService)

```python
# In logic.py __init__
self._services = {
    "myservice": TickerService(
        "myservice",
        self._do_my_task,
        interval=60,  # seconds
        predicate=self._should_run,  # optional
    ),
}

# Predicate for scheduled tasks
def _should_run(self) -> bool:
    # Return True when task should execute
    pass

# Task implementation
def _do_my_task(self) -> None:
    # Do work
    self._broadcast_something()
```

#### WebSocket Broadcasting

```python
# From daemon threads (thread-safe)
ws_manager.broadcast_sync({
    "event": "my_event",
    "timestamp": datetime.now().isoformat(),
    "data": {...}
})
```

### Testing

```bash
# Run tests
cd bet_dashboard/backend
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Linting & Formatting

```bash
# Ruff (fast Python linter)
ruff check .
ruff check . --fix
ruff format .

# MyPy (type checking)
mypy . --strict --ignore-missing-imports
```

---

## Crawler Development

### Setup

```bash
cd bet_crawler

# Install dependencies
pip install -e ../bet_framework
pip install -e .

# Test a finder
python -c "
from bet_crawler.finders.WhoScoredFinder import WhoScoredFinder
f = WhoScoredFinder(print)
urls = f.get_matches_urls()
print(f'Found {len(urls)} URLs')
"
```

### Project Structure

```
bet_crawler/
├── crawl.py             # CLI entry + CrawlerFactory
├── finders/             # 18+ source-specific finders
│   ├── BaseMatchFinder.py
│   ├── WhoScoredFinder.py
│   ├── ForebetFinder.py
│   └── ...
└── crawl_core/          # Pipeline stages
    ├── prepare_scrape.py
    ├── scrape.py
    ├── merge.py
    ├── generate_slips.py
    └── validate_slips.py
```

### Adding a New Finder

See [README.md#-how-to-add-a-new-finder](../README.md#-how-to-add-a-new-finder) for complete guide.

### Running Pipeline Modes

```bash
# 1. Prepare scrape (collect URLs)
python -m bet_crawler.crawl --mode prepare-scrape --runners actions --config_dir ../config

# 2. Scrape chunk
python -m bet_crawler.crawl --mode scrape --matches_db_path chunk.db --urls "url1,url2" --config_dir ../config

# 3. Merge
python -m bet_crawler.crawl --mode merge --matches_db_path final.db --chunks_dir ./chunks --config_dir ../config

# 4. Generate slips
python -m bet_crawler.crawl --mode generate-slips --matches_db_path final.db --slips_db_path slips.db --profile_path ../config/profiles/medium_risk.yaml

# 5. Validate
python -m bet_crawler.crawl --mode validate-slips --slips_db_path slips.db
```

### Configuration

Key config files in `config/`:

- `scraper_config.yaml`: Crawler keys, runner sets, skip patterns, chunk sizes
- `similarity_config.yaml`: Team name fuzzy matching rules
- `profiles/*.yaml`: Smart Builder risk profiles

---

## Framework Development (bet_framework)

### Core Modules

```
bet_framework/
├── BetAssistant.py      # Slip building, validation, storage
├── MatchesManager.py    # Buffered SQLite + fuzzy dedup
└── core/
    ├── Match.py         # Match, Score, Odds dataclasses
    ├── Slip.py          # Slip, Leg, Config, Profiles, enums
    ├── consensus.py     # Consensus calculation engine
    ├── scoring.py       # Pick scoring & ranking algorithm
    ├── outcomes.py      # Result evaluation (Won/Lost/Live)
    ├── types.py         # Enums: MarketType, Outcome, MarketLabel
    ├── utils.py         # URL validation, datetime coercion
    └── leagues.py       # League name constants
```

### Key Classes

#### BetAssistant

```python
assistant = BetAssistant("slips.db")
assistant.load_matches(dataframe)
legs = assistant.build_slip("medium_risk")
slip_id = assistant.save_slip("medium_risk", legs)
assistant.validate_slips()
```

#### MatchesManager

```python
manager = MatchesManager("matches.db", similarity_config)
manager.add_match(match)  # Buffered, auto-dedup
manager.flush()           # Write to disk
manager.merge_databases("chunks_dir")  # Merge with history preservation
```

### Running Tests

```bash
cd bet_framework
python -m pytest ../tests/ -v -k "bet_framework"
```

---

## Full Stack Development Workflow

### 1. Start All Services

```bash
# Terminal 1: Frontend dev server
cd bet_dashboard/frontend && npm run dev

# Terminal 2: Backend dev server
cd bet_dashboard/backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 3: (Optional) Crawler test
cd bet_crawler && python -m bet_crawler.crawl --mode prepare-scrape --runners test --config_dir ../config
```

### 2. Development URLs

| Service | URL |
|---------|-----|
| Frontend (Vite) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| WebSocket | ws://localhost:8000/ws |

### 3. Proxy Configuration

Vite proxies `/api` and `/ws` to backend:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
```

### 4. Hot Reload

- **Frontend**: Vite HMR (instant)
- **Backend**: Uvicorn `--reload` (restarts on Python changes)
- **Crawler**: Manual re-run

---

## Testing Strategy

### Unit Tests

```bash
# All tests
python -m pytest tests/

# Specific module
python -m pytest tests/test_bet_assistant.py -v
python -m pytest tests/test_matches_manager.py -v
```

### Integration Tests

```bash
# Test full pipeline
python -m pytest tests/ -k "integration" -v
```

### Test Coverage

```bash
python -m pytest tests/ --cov=bet_framework --cov=bet_dashboard.backend --cov=bet_crawler --cov-report=html
```

---

## Code Quality

### Pre-commit Hooks

```bash
# Install
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### CI Pipeline (`.github/workflows/cicd.yml`)

1. **Auto-fix**: autoflake, pyupgrade, autotyping, isort, ruff
2. **Test**: pytest on Python 3.10/3.11/3.12
3. **Audit**: mypy, bandit, semgrep, pip-audit, radon, vulture, interrogate
4. **Gate**: Consolidated report

### Local Quality Checks

```bash
# Python
ruff check . --fix
ruff format .
mypy . --strict
bandit -r .
pip-audit
radon cc . --min C
vulture . --min-confidence 80
interrogate . -v

# Frontend
cd bet_dashboard/frontend
npm run lint
npm run build  # TypeScript compilation check
```

---

## Debugging Common Issues

### Frontend Not Connecting to Backend

1. Check Vite proxy config
2. Verify backend running on port 8000
3. Check CORS origins in `main.py`
4. Check browser console for errors

### WebSocket Not Working

1. Verify `/ws` endpoint in `system.py`
2. Check `useSocket` hook reconnection logic
3. Ensure Nginx not blocking WS in production

### Database Locked

```bash
# Check for stale processes
lsof workspace/data/matches.db
lsof workspace/data/slips.db

# Kill and restart
kill -9 <PID>
```

### Finder Not Collecting URLs

```bash
# Test in isolation
python -c "
from bet_crawler.finders.MyFinder import MyFinder
f = MyFinder(print)
urls = f.get_matches_urls()
print(f'Found {len(urls)} URLs')
for u in urls[:3]: print(u)
"
```

---

## Contributing

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code improvements
- `test/description` - Test additions

### Commit Messages

Follow Conventional Commits:

```
feat: add new market type for double chance
fix: resolve WebSocket reconnection issue
docs: update API reference for odds history
refactor: extract scoring logic to separate module
test: add unit tests for consensus calculation
```

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Run quality checks locally
5. Submit PR with description
6. CI must pass (auto-fix, test, audit, gate)
7. Code review
8. Merge

---

## Useful Commands Reference

```bash
# Database inspection
sqlite3 workspace/data/matches.db ".schema"
sqlite3 workspace/data/matches.db "SELECT COUNT(*) FROM matches;"
sqlite3 workspace/data/slips.db "SELECT * FROM slips ORDER BY slip_id DESC LIMIT 5;"

# Logs
docker compose -f setup/compose.yaml logs -f --tail=100

# Container shell
docker compose -f setup/compose.yaml exec bet-assistant bash

# Rebuild frontend
docker compose -f setup/compose.yaml build --no-cache bet-assistant

# Reset everything
docker compose -f setup/compose.yaml down -v
rm -rf workspace/
docker compose -f setup/compose.yaml up -d
```
