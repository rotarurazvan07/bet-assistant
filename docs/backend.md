# Backend Documentation

## Overview

The Bet Assistant backend is a **FastAPI** application providing REST API endpoints, WebSocket real-time updates, and background daemon services for automated betting slip management.

**Tech Stack**:
- Python 3.11+
- FastAPI 0.111+
- Uvicorn (ASGI server)
- WebSockets (native + custom ConnectionManager)
- Pydantic v2 (validation & serialization)
- Pandas (data processing)
- SQLite (matches.db, slips.db)
- scrape-kit + BeautifulSoup4 (result validation)
- YAML configuration (scraper_config.yaml, similarity_config.yaml)

---

## Architecture

```mermaid
graph TD
    Main[main.py
    create_app() + lifespan]
    
    Routers[Routers/ 8 API Endpoints]
    MT[matches.py
    GET /api/matches
    Filtering, sorting, pagination]
    BL[builder.py
    POST /api/builder/preview
    GET /api/builder/excluded
    GET /api/builder/leagues]
    PR[profiles.py
    CRUD /api/profiles]
    SP[slips.py
    CRUD /api/slips
    POST /validate
    POST /generate]
    SV[services.py
    GET /api/services
    POST /settings
    POST /toggle]
    AN[analytics.py
    GET /api/analytics
    12+ chart datasets]
    OH[odds_history.py
    GET /api/odds-history
    Movements + history]
    SY[system.py
    POST /api/pull
    GET /api/status
    WS /ws]
    
    Core[Core Modules]
    LG[logic.py
    AppLogic - Unified Business Logic
    TickerService Orchestration]
    TS[ticker_service.py
    Daemon Thread Polling
    Predicate-based Execution]
    WS[ws.py
    ConnectionManager
    Thread-safe Broadcast]
    MC[market_config.py
    MarketDef + Constants]
    SC[schemas.py
    Pydantic Request/Response]
    AU[analytics_utils.py
    Statistics Calculations]
    CH[config_helpers.py
    Profile YAML Conversion]
    
    Framework[bet_framework/]
    BA[BetAssistant.py
    Slip Building + Validation + Storage]
    MM[MatchesManager.py
    Buffered SQLite + Fuzzy Dedup]
    CoreF[core/
    Match, Slip, Consensus, Scoring, Outcomes]
    
    Main --> Routers
    Routers --> MT
    Routers --> BL
    Routers --> PR
    Routers --> SP
    Routers --> SV
    Routers --> AN
    Routers --> OH
    Routers --> SY
    
    Main --> Core
    Core --> LG
    Core --> TS
    Core --> WS
    Core --> MC
    Core --> SC
    Core --> AU
    Core --> CH
    
    LG --> Framework
    LG --> BA
    LG --> MM
    BA --> CoreF
    MM --> CoreF
```

---

## Application Factory (`main.py`)

### `create_app()`

```python
def create_app() -> FastAPI:
    matches_db = os.getenv("MATCHES_DB_PATH", "bet_dashboard/workspace/data/matches.db")
    slips_db = os.getenv("SLIPS_DB_PATH", "bet_dashboard/workspace/data/slips.db")
    config_dir = os.getenv("CONFIG_PATH", "bet_dashboard/workspace/config")

    app = FastAPI(
        title="Bet Assistant API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Single shared logic instance
    app.state.app_logic = AppLogic(matches_db, slips_db, config_dir)

    # Register routers
    for router in [matches.router, builder.router, profiles.router,
                   slips.router, analytics.router, services.router,
                   system.router, odds_history.router]:
        app.include_router(router)

    return app
```

### Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hand event loop to ws_manager for thread-safe broadcasting
    ws_manager.set_loop(asyncio.get_event_loop())
    yield
    # TickerService threads are daemons - die with process
```

---

## Routers

### 1. Matches Router (`routers/matches.py`)

**Endpoint**: `GET /api/matches`

**Features**:
- Pagination (page, page_size up to 100)
- Search (team name substring, case-insensitive)
- Date range filtering (date_from, date_to)
- Multi-column sorting (datetime, home, away, sources, all consensus columns)
- Per-cell filtering: consensus floor, min odds, significant movement
- Row kept if ANY market cell passes ALL active filters

**Filter Logic**:
```python
# Combined per-cell filter: each market cell must pass ALL active checks
# A row is kept if at least one cell passes every active filter
has_cons = min_consensus is not None and min_consensus > 0
has_odds = min_odds is not None and min_odds > 1.0
has_sig = only_significant_movement

if has_cons or has_odds or has_sig:
    mask = pd.Series(False, index=df.index)
    for md in MARKET_DEFINITIONS:
        if md.cons_key not in df.columns:
            continue
        cell_ok = pd.Series(True, index=df.index)
        if has_cons:
            cell_ok &= df[md.cons_key].ge(min_consensus)
        if has_odds and md.odds_key in df.columns:
            cell_ok &= df[md.odds_key].ge(min_odds)
        if has_sig:
            # Check odds movement significance
            sig_mask = pd.Series(False, index=df.index)
            for idx in df.index:
                s = sig_data.get(idx)
                if s and isinstance(s.get(market_key), dict) and s[market_key].get("significant"):
                    sig_mask.at[idx] = True
            cell_ok &= sig_mask
        mask |= cell_ok
    df = df[mask]
```

### 2. Builder Router (`routers/builder.py`)

**Endpoints**:
- `POST /api/builder/preview` - Generate slip preview from config
- `GET /api/builder/excluded` - Get manually excluded URLs
- `GET /api/builder/excluded/details` - Detailed excluded match info
- `POST /api/builder/excluded` - Add URL to exclusions
- `POST /api/builder/excluded/remove` - Remove URL from exclusions
- `DELETE /api/builder/excluded` - Clear all exclusions
- `GET /api/builder/leagues` - Get all available leagues

**Preview Logic**:
```python
@router.post("/preview")
def preview(request: Request, body: BetSlipConfigIn):
    app = _get(request)
    cfg = _to_config(body)
    legs = app.build_preview(cfg)
    total_odds = math.prod(leg.odds for leg in legs) if legs else 1.0
    pending_urls = list(app.logic.get_pending_urls())
    
    return sanitize_floats({
        "total_odds": round(total_odds, 4),
        "pending_urls": pending_urls,
        "legs": [leg_to_dict(leg) for leg in legs]
    })
```

### 3. Profiles Router (`routers/profiles.py`)

**Endpoints**:
- `GET /api/profiles` - List all profiles
- `POST /api/profiles` - Save new profile (sanitized name)
- `DELETE /api/profiles/{name}` - Delete profile

**Profile Conversion**:
```python
# ProfileIn (Pydantic) -> BetSlipConfig -> YAML dict
data = _config_to_yaml_dict(
    BetSlipConfig(...),
    units=body.units,
    target_payout=body.target_payout,
    run_daily_count=body.run_daily_count,
)
app.settings.write(name, data, subpath="profiles")
```

### 4. Slips Router (`routers/slips.py`)

**Endpoints**:
- `GET /api/slips` - Paginated slips with filters
- `POST /api/slips` - Create manual slip (with validation)
- `POST /api/slips/validate_manual` - Validate legs without creating
- `DELETE /api/slips/{slip_id}` - Delete pending slip
- `POST /api/slips/validate` - Trigger validation of all pending/live
- `POST /api/slips/generate` - Generate slips for daily profiles

**Manual Leg Validation**:
```python
def validate_manual_leg(leg: dict, logic) -> dict:
    # 1. Match existence (fuzzy search on home/away)
    # 2. Market allow-list (ALLOWED_MARKETS)
    # 3. Odds sanity (> 0)
    # 4. URL format validation
    return {"valid": True} or {"valid": False, "error": "..."}
```

### 5. Services Router (`routers/services.py`)

**Endpoints**:
- `GET /api/services` - All service status + schedule
- `POST /api/services/settings` - Update generation hour/minute
- `POST /api/services/{name}/toggle` - Toggle service enabled

**Service Status Calculation**:
```python
# Hour-based (generator) -> next run at scheduled time
# Interval-based (puller, verifier) -> "Every X min"
# Alive check: TickerService.is_alive()
```

### 6. Analytics Router (`routers/analytics.py`)

**Endpoint**: `GET /api/analytics`

**Returns 12+ datasets**:
- `history` - Daily P&L tracking
- `market_accuracy` - Won/Lost per market
- `pnl_by_market` - Net profit per market
- `correlation` - Legs vs odds vs profit
- `profile_scatter` - Profile performance
- `stats` - Comprehensive statistics (ROI, Sharpe, Kelly, etc.)
- `market_breakdown` - Detailed market stats with edge
- `league_breakdown` - Detailed league stats
- `rolling_edge` - 14-day rolling edge
- `drawdown` - Peak-to-trough tracking
- `correlation_matrix` - League × Market heatmap

### 7. Odds History Router (`routers/odds_history.py`)

**Endpoints**:
- `GET /api/odds-history/movements/all` - All future match movements
- `GET /api/odds-history/movements/significant` - Significant only
- `GET /api/odds-history/{match_id}` - Full history + snapshots
- `GET /api/odds-history/{match_id}/movement` - Movement summary

### 8. System Router (`routers/system.py`)

**Endpoints**:
- `POST /api/pull` - Manual database pull from GitHub Releases
- `GET /api/status` - Health check (last pull, matches loaded)
- `WS /ws` - WebSocket endpoint

**WebSocket Handler**:
```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"event":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

---

## Core Modules

### AppLogic (`core/logic.py`)

**Unified business logic combining DashboardLogic and service orchestration.**

**Key Responsibilities**:
1. Match data management (loading, filtering, refresh)
2. Slip building (preview, auto-exclude, generation)
3. Slip persistence (save, retrieve, delete)
4. Validation (scrape results, settle legs)
5. Service orchestration (3 TickerServices)
6. WebSocket broadcasting
7. Analytics calculations

**Services**:
```python
self._services = {
    "puller": TickerService(
        "puller", self._do_pull,
        interval=300,  # 5 min
        predicate=self._check_for_changes,  # ETag check
    ),
    "generator": TickerService(
        "generator", self._do_generate,
        interval=300,
        predicate=self._is_generator_hour_met,  # Daily at hour
    ),
    "verifier": TickerService(
        "verifier", self._do_verify,
        interval=60,  # 1 min
    ),
}
```

**Key Methods**:
- `build_preview(cfg)` - Score candidates, return preview
- `build_slip(cfg)` - Build slip with auto-exclude
- `save_slip(profile, legs, units)` - Persist to SQLite
- `validate_slips()` - Scrape results, update statuses
- `generate_slips(profiles)` - Run daily profiles
- `pull_matches_db(path)` - Download + merge with history preservation
- `stats(profile, date_from, date_to)` - Comprehensive statistics

### TickerService (`core/ticker_service.py`)

**Generic polling service with predicate-based execution.**

```python
class TickerService:
    def __init__(self, name, on_tick, interval=60, predicate=None):
        self.name = name
        self.on_tick = on_tick
        self.interval = interval
        self.predicate = predicate
        self.enabled = True
        self._thread = _daemon(self._run, name.lower())
    
    def _run(self):
        while True:
            if not self.enabled:
                self._wake_event.wait()
                continue
            interrupted = self._wake_event.wait(self.interval)
            if interrupted and not self._force_run:
                continue
            if not self.enabled: continue
            if self.predicate and not self._force_run:
                if not self.predicate(): continue
            try:
                self.on_tick()
            finally:
                self._force_run = False
```

**Features**:
- Daemon thread (dies with process)
- Configurable interval
- Optional predicate (skip ticks)
- Force-run capability (manual trigger)
- Enable/disable toggle
- Thread-safe wake events

### WebSocket Manager (`core/ws.py`)

**Thread-safe connection manager for real-time updates.**

```python
class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
    
    def set_loop(self, loop):
        self._loop = loop
    
    async def broadcast(self, payload):
        # Async broadcast, prune dead connections
    
    def broadcast_sync(self, payload):
        # Thread-safe: run_coroutine_threadsafe
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)
```

**Usage from Daemon Threads**:
```python
# In TickerService callbacks
ws_manager.broadcast_sync({
    "event": "slips_updated",
    "timestamp": datetime.now().isoformat(),
    "live_data": {...}
})
```

### Market Config (`core/market_config.py`)

**Centralized market definitions** (shared with frontend).

```python
MARKET_DEFINITIONS = [
    MarketDef("1", "cons_home", "odds_home", "result"),
    MarketDef("X", "cons_draw", "odds_draw", "result"),
    MarketDef("2", "cons_away", "odds_away", "result"),
    MarketDef("Over 2.5", "cons_over_25", "odds_over_25", "over_under_25"),
    # ... 18 total markets
]
```

### Schemas (`core/schemas.py`)

**Pydantic models for request/response validation.**

Key models:
- `BetSlipConfigIn` - Builder configuration input
- `ProfileIn` - Profile save input
- `ManualLegIn` - Manual slip leg input
- `SlipIn` - Slip creation input
- `ServicesSettingsIn` - Schedule settings
- `OddsHistoryOut` - Odds history response
- `OddsMovementSummary` - Movement directions
- `CandidateLegOut` - Preview leg output
- `PreviewOut` - Preview response
- `BetSlipOut` - Slip response
- `BetLegOut` - Leg response

### Analytics Utils (`core/analytics_utils.py`)

**Pure functions for statistics calculations.**

Key functions:
- `calculate_overall_edge(slips)` - Actual vs implied win rate
- `calculate_rolling_edge(slips, window_days)` - Rolling edge over time
- `calculate_kelly_recommendation(...)` - Kelly criterion units
- `get_rolling_edge_trend(settled_slips)` - 14-day trend
- `calculate_daily_summary(...)` - Daily P&L aggregation
- `calculate_market_accuracy(slips)` - Per-market accuracy
- `calculate_correlation_data(slips)` - Legs/odds/profit correlation
- `calculate_streak_metrics(slips)` - Win/loss streaks
- `calculate_profit_factor(settled_slips)` - Wins/Losses ratio
- `calculate_biggest_win_loss(settled_slips)` - Max win/loss

### Config Helpers (`core/config_helpers.py`)

**Profile YAML ↔ BetSlipConfig conversion.**

```python
def _yaml_to_config(data: dict) -> BetSlipConfig:
    kwargs = {k: v for k, v in data.items() 
              if k in _BETSLIP_FIELDS and k not in _RUNTIME_ONLY}
    return BetSlipConfig(**kwargs)

def _config_to_yaml_dict(cfg, units=1.0, target_payout=None, run_daily_count=0):
    d = asdict(cfg)
    for k in _RUNTIME_ONLY: d[k] = None
    d["units"] = units
    d["target_payout"] = target_payout
    d["run_daily_count"] = run_daily_count
    return d
```

---

## bet_framework Integration

### BetAssistant (`bet_framework/BetAssistant.py`)

**All-in-one: slip building, validation, storage.**

**Scoring Model**:
```python
# Three normalized axes (0.0 → 1.0)
consensus_score = (consensus - floor) / (100 - floor)
sources_score = sources / max_sources_in_pool
balance_score = proximity to ideal per-leg odds

quality = consensus_vs_sources * consensus_score + (1 - consensus_vs_sources) * sources_score
final = quality_vs_balance * quality + (1 - quality_vs_balance) * balance_score
```

**Tier System**:
- Tier 1: Within tolerance band (always ranked above Tier 2)
- Tier 2: Outside tolerance (used only if insufficient Tier 1)

**Advanced Features**:
- Bayesian consensus shrinkage: `adjusted = 50 + (sources/(sources+k)) * (raw - 50)`
- Asymmetric tolerance (lower/upper bands)
- Odds movement adjustment (confirm/stable/infirm)
- Gaussian/linear balance decay

### MatchesManager (`bet_framework/MatchesManager.py`)

**Buffered SQLite with fuzzy deduplication.**

**Key Features**:
- In-memory buffer (BufferedStorageManager)
- Fuzzy matching on home/away/datetime (±1 day)
- SimilarityEngine for team name normalization
- Source collision guard (prevent duplicate sources)
- Odds validation (implied probability 95-120%)
- Embedded odds history (snapshots with timestamps)
- History preservation on merge (transfer odds history)
- Near-miss logging (40-65 similarity score)

**Merge with History Preservation**:
```python
def merge_with_history_preservation(self, fresh_db_path, max_history=3, local_tz="UTC"):
    # 1. Load current future matches
    # 2. Load fresh database
    # 3. Fuzzy-match current → fresh
    # 4. Transfer odds history + append current snapshot
    # 5. Replace buffer with merged fresh data
```

### Core Data Models (`bet_framework/core/`)

| Module | Exports |
|--------|---------|
| `Match.py` | `Match`, `Score`, `Odds`, `ensure_decimal_odds` |
| `Slip.py` | `CandidateLeg`, `BetLeg`, `BetSlip`, `BetSlipConfig`, `PROFILES`, `get_profile` |
| `consensus.py` | `calc_consensus(scores)`, `to_pct(n, total)` |
| `scoring.py` | `score_pick()`, `resolve_tolerance()`, `resolve_stop_threshold()`, `apply_odds_movement_adjustment()` |
| `outcomes.py` | `determine_outcome(home, away, market, type)`, `parse_score()` |
| `types.py` | `MarketType`, `Outcome`, `MatchStatus`, `MarketLabel` enums |
| `utils.py` | `is_valid_url()`, `coerce_datetime_str()` |
| `leagues.py` | League name constants |

---

## Database Schema

### matches.db

```sql
CREATE TABLE matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    datetime TEXT NOT NULL,
    predictions_scores TEXT,  -- JSON: [{source, home, away}, ...]
    odds TEXT,                -- JSON: {home, draw, away, over_25, ..., history: [...]}
    result_url TEXT,
    league TEXT
);
CREATE INDEX idx_datetime ON matches(datetime);
CREATE INDEX idx_home_team ON matches(home_team_name);
CREATE INDEX idx_away_team ON matches(away_team_name);
```

**Odds JSON Structure**:
```json
{
  "home": 1.85,
  "draw": 3.40,
  "away": 4.20,
  "over_25": 1.75,
  "under_25": 2.10,
  "history": [
    {"ts": "2026-08-22T10:00:00", "home": 1.90, "draw": 3.30, "away": 4.00},
    {"ts": "2026-08-22T15:00:00", "home": 1.85, "draw": 3.40, "away": 4.20}
  ]
}
```

### slips.db

```sql
CREATE TABLE slips (
    slip_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_generated TEXT,
    profile TEXT,
    total_odds REAL,
    units REAL DEFAULT 1.0
);

CREATE TABLE legs (
    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    slip_id INTEGER,
    match_name TEXT,
    match_datetime TEXT,
    market TEXT,
    market_type TEXT,
    odds REAL,
    result_url TEXT,
    status TEXT DEFAULT 'Pending',
    league TEXT,
    FOREIGN KEY(slip_id) REFERENCES slips(slip_id)
);
```

---

## Configuration

### scraper_config.yaml

```yaml
CRAWLER_KEYS:
  whoscored:
    class: "WhoScoredFinder"
    contributes_odds: false
  forebet:
    class: "ForebetFinder"
    contributes_odds: true
  # ... 18+ finders

RUNNER_SETS:
  actions: [vitibet, scorepredictor, predictz, soccervista, ...]
  local: [whoscored, forebet, footballbettingtips]
  all: [all keys]
  test: [legitpredict]

MAX_CHUNK_SIZE:
  actions: 100
  local: 1
  all: 1
  test: 1

SKIP_PATTERNS:
  - pattern: "\\bU\\d{2}s?\\b"
    description: "Youth team"
  - pattern: "\\bW\\b"
    description: "Women's team"
  # ...

num_days_ahead: 3
local_timezone: "Europe/Bucharest"
```

### similarity_config.yaml

```yaml
# Team name fuzzy matching rules
threshold: 65
synonyms:
  "Man City": "Manchester City"
  "Man Utd": "Manchester United"
  # ...
```

### profiles/*.yaml

```yaml
# low_risk.yaml
target_odds: 2.0
target_legs: 2
max_legs_overflow: 0
consensus_floor: 75.0
min_odds: 1.10
tolerance_factor: 0.20
stop_threshold: 0.92
min_legs_fill_ratio: 1.00
quality_vs_balance: 0.70
consensus_vs_sources: 0.70
consensus_shrinkage_k: 4.0
min_source_edge: 0.05
max_single_leg_odds: 2.00
balance_decay: "gaussian"
min_pick_quality: 0.30
units: 1.0
run_daily_count: 1
```

---

## Error Handling

### Validation Errors

- Pydantic validation (422) for request bodies
- Custom validation in routers (400 with detail)
- Database constraints (unique, foreign key)

### Exception Handling

```python
# In routers
try:
    result = logic.some_operation()
except Exception as exc:
    logger.error(f"Operation failed: {exc}")
    raise HTTPException(500, str(exc))
```

### WebSocket Errors

- Connection errors → disconnect cleanup
- Malformed frames → ignored
- Broadcast failures → prune dead connections

---

## Performance Considerations

### Database
- SQLite WAL mode for concurrent reads
- Indexes on datetime, home_team, away_team
- Buffered writes (flush every 5000 rows)
- Connection pooling via context managers

### Caching
- In-memory match DataFrame (refreshed on pull)
- ETag-based change detection for DB pulls
- Pending URLs cached for slip building

### Concurrency
- Daemon threads for background services
- Thread-safe WebSocket broadcasting
- Database locks for concurrent access

### Memory
- Pandas DataFrames for match data
- Chunked processing for large merges
- Generator patterns for streaming

---

## Testing

```bash
# Unit tests
cd bet_dashboard/backend
python -m pytest tests/ -v

# Specific test files
python -m pytest tests/test_bet_assistant.py -v
python -m pytest tests/test_matches_manager.py -v
python -m pytest tests/test_odds_history.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Key Test Areas

- API endpoint validation
- Slip building logic
- Consensus calculation
- Odds movement detection
- Validation result parsing
- Profile YAML round-trip
- Database merge deduplication

---

## Deployment

### Docker

Multi-stage build:
```dockerfile
# Stage 1: Frontend builder (Node 22)
# Stage 2: Python deps (Python 3.11)
# Stage 3: Runtime (Python 3.11 + nginx)
```

### Environment Variables

```bash
MATCHES_DB_PATH=/app/workspace/data/matches.db
SLIPS_DB_PATH=/app/workspace/data/slips.db
CONFIG_PATH=/app/workspace/config
PYTHONPATH=/app
TZ=Europe/Bucharest
HOST=127.0.0.1  # Security: bind to localhost only
```

### Health Check

```bash
curl http://localhost:8000/api/status
# {"last_pull": "2026-08-22T05:30:00", "matches_loaded": 1247}
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| WebSocket not connecting | Check `ws_manager.set_loop()` called in lifespan |
| Database locked | Check for stale processes, ensure single writer |
| Validation not working | Verify `result_url` stored, check parser logic |
| Services not running | Check TickerService predicates, enable flags |
| Pull fails | Check GitHub Release exists, network access |
| High memory | Reduce DataFrame size, enable chunked processing |

### Debug Commands

```bash
# Check database
sqlite3 workspace/data/matches.db "SELECT COUNT(*) FROM matches;"
sqlite3 workspace/data/slips.db "SELECT * FROM slips ORDER BY slip_id DESC LIMIT 5;"

# Check logs
docker compose -f setup/compose.yaml logs -f bet-assistant

# Manual API test
curl -X POST http://localhost:8000/api/builder/preview \
  -H "Content-Type: application/json" \
  -d '{"target_odds": 3.0, "target_legs": 3, "consensus_floor": 50}'
```
