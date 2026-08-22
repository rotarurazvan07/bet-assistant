# API Reference

## Overview

The Bet Assistant backend exposes a **REST API** (FastAPI) and a **WebSocket** endpoint for real-time updates. All endpoints are prefixed with `/api` except the WebSocket at `/ws`.

**Base URL**: `http://localhost:3002/api` (via Nginx) or `http://localhost:8000/api` (direct)

**Authentication**: None required (local deployment). For production, add API key middleware.

**Content-Type**: `application/json`

---

## WebSocket Real-time Events

### Connection

```javascript
const ws = new WebSocket('ws://localhost:3002/ws');

ws.onopen = () => {
  // Send ping every 25s to keep alive
  setInterval(() => ws.send('ping'), 25000);
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.event) {
    case 'matches_updated':
      // Refetch matches table
      break;
    case 'slips_updated':
      // Refetch slips + analytics
      if (data.live_data) updateLiveScores(data.live_data);
      break;
    case 'service_toggled':
      // Refetch services
      break;
    case 'pong':
      // Connection alive
      break;
  }
};
```

### Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `matches_updated` | `{timestamp: string}` | New match data available |
| `slips_updated` | `{timestamp: string, live_data?: Record<string, {score, minute}>}` | Slip data changed |
| `service_toggled` | `{name: string, enabled: boolean, timestamp: string}` | Crawler service toggled |
| `pong` | `{}` | Ping response |

---

## REST API Endpoints

### Matches

#### GET `/api/matches`

Get paginated, filtered, and sorted match list.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (≥1) |
| `page_size` | integer | 40 | Items per page (1-100) |
| `search` | string | - | Team name substring (case-insensitive) |
| `date_from` | string | - | ISO date (YYYY-MM-DD) |
| `date_to` | string | - | ISO date (YYYY-MM-DD) |
| `sort_by` | string | `datetime` | Column to sort by |
| `sort_dir` | string | `asc` | `asc` or `desc` |
| `min_consensus` | integer | - | Minimum consensus % (0-100) |
| `min_odds` | float | - | Minimum odds (≥1.0) |
| `only_significant_movement` | boolean | false | Only matches with significant odds movement |

**Response**

```json
{
  "total": 1247,
  "page": 1,
  "page_size": 40,
  "total_pages": 32,
  "matches": [
    {
      "match_id": "match_0_abc123",
      "datetime": "2026-08-23T20:00:00",
      "home": "Manchester City",
      "away": "Liverpool",
      "sources": 4,
      "cons_home": 65.0,
      "cons_draw": 20.0,
      "cons_away": 15.0,
      "cons_over_25": 70.0,
      "cons_under_25": 30.0,
      "cons_btts_yes": 55.0,
      "cons_btts_no": 45.0,
      "odds_home": 1.85,
      "odds_draw": 3.40,
      "odds_away": 4.20,
      "odds_over_25": 1.75,
      "odds_under_25": 2.10,
      "odds_btts_yes": 1.90,
      "odds_btts_no": 1.95,
      "result_url": "https://www.whoscored.com/matches/12345",
      "league": "Premier League"
    }
  ]
}
```

**Sortable Columns**: `datetime`, `home`, `away`, `sources`, and all consensus columns (`cons_home`, `cons_draw`, etc.)

**Filter Logic**: A row is returned if **at least one market cell** passes ALL active filters (consensus, odds, movement).

---

### Builder

#### POST `/api/builder/preview`

Generate a slip preview from a builder configuration.

**Request Body** (`BetSlipConfigIn`)

```json
{
  "target_odds": 3.0,
  "target_legs": 3,
  "max_legs_overflow": null,
  "consensus_floor": 50.0,
  "min_odds": 1.05,
  "included_markets": null,
  "included_leagues": null,
  "tolerance_factor": null,
  "stop_threshold": null,
  "min_legs_fill_ratio": 0.7,
  "quality_vs_balance": 0.5,
  "consensus_vs_sources": 0.5,
  "date_from": null,
  "date_to": null,
  "consensus_shrinkage_k": null,
  "min_source_edge": null,
  "max_single_leg_odds": null,
  "tol_lower": null,
  "tol_upper": null,
  "balance_decay": "gaussian",
  "min_pick_quality": null,
  "odds_movement_weight": null,
  "odds_movement_strength_min": null
}
```

**Response** (`PreviewResult`)

```json
{
  "total_odds": 3.24,
  "pending_urls": ["https://...", "https://..."],
  "legs": [
    {
      "match_name": "Manchester City vs Liverpool",
      "datetime": "2026-08-23T20:00:00",
      "market": "1",
      "market_type": "result",
      "consensus": 65.0,
      "odds": 1.85,
      "result_url": "https://www.whoscored.com/matches/12345",
      "league": "Premier League",
      "sources": 4,
      "tier": 1,
      "score": 0.8234,
      "odds_movement_direction": "down",
      "odds_movement_strength": 0.032
    }
  ]
}
```

#### GET `/api/builder/excluded`

Get manually excluded URLs.

**Response**
```json
{ "excluded": ["https://...", "https://..."] }
```

#### GET `/api/builder/excluded/details`

Get detailed info about manually excluded matches.

**Response**
```json
{
  "excluded": [
    {
      "url": "https://...",
      "match_name": "Team A vs Team B",
      "datetime": "2026-08-23T20:00:00",
      "reason": "Manually excluded"
    }
  ]
}
```

#### POST `/api/builder/excluded`

Add a URL to manual exclusions.

**Request**: `{ "url": "https://..." }`
**Response**: `{ "excluded": [...] }`

#### POST `/api/builder/excluded/remove`

Remove a URL from manual exclusions.

**Request**: `{ "url": "https://..." }`
**Response**: `{ "excluded": [...] }`

#### DELETE `/api/builder/excluded`

Clear all manual exclusions.

**Response**: `{ "excluded": [] }`

#### GET `/api/builder/leagues`

Get all available leagues (framework + database).

**Response**: `["Premier League", "La Liga", "Serie A", ...]`

---

### Profiles

#### GET `/api/profiles`

List all saved profiles.

**Response**
```json
{
  "profiles": {
    "low_risk": {
      "target_odds": 2.0,
      "target_legs": 2,
      "consensus_floor": 75.0,
      "units": 1.0,
      "run_daily_count": 1
    }
  }
}
```

#### POST `/api/profiles`

Save a new profile.

**Request Body** (`ProfileIn`)
```json
{
  "name": "my_profile",
  "target_odds": 3.0,
  "target_legs": 3,
  "consensus_floor": 50.0,
  "units": 1.0,
  "run_daily_count": 0
}
```

**Response**: `{ "name": "my_profile", "data": {...} }`

#### DELETE `/api/profiles/{name}`

Delete a profile.

**Response**: `{ "deleted": "my_profile" }`

---

### Slips

#### GET `/api/slips`

Get paginated slip list with statistics.

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `profiles` | string[] | Filter by profile names (repeat param) |
| `date_from` | string | ISO date |
| `date_to` | string | ISO date |
| `hide_settled` | boolean | Hide Won/Lost slips |
| `live_only` | boolean | Only slips with live legs |

**Response**
```json
{
  "slips": [
    {
      "slip_id": 42,
      "date_generated": "2026-08-22T08:00:00",
      "profile": "low_risk",
      "total_odds": 2.15,
      "units": 1.0,
      "slip_status": "Pending",
      "legs": [
        {
          "match_name": "Team A vs Team B",
          "datetime": "2026-08-23T20:00:00",
          "market": "1",
          "market_type": "result",
          "odds": 1.45,
          "status": "Pending",
          "result_url": "https://...",
          "league": "Premier League"
        }
      ]
    }
  ],
  "stats": {
    "total_settled": 150,
    "total_won_count": 87,
    "win_rate": 58.0,
    "implied_win_rate": 52.3,
    "edge": 5.7,
    "total_units_bet": 150.0,
    "gross_return": 178.5,
    "net_profit": 28.5,
    "roi_percentage": 19.0,
    "avg_odds": 2.34,
    "avg_units": 1.0,
    "units_std": 0.0,
    "pending_count": 12,
    "sharpe_ratio": 1.23,
    "kelly_suggested_units": 0.15,
    "edge_trend": "growing",
    "recent_edge_value": 6.2,
    "biggest_win_units": 4.5,
    "biggest_loss_units": -2.0,
    "best_day_pnl": 12.3,
    "worst_day_pnl": -8.7,
    "current_streak": 3,
    "longest_win_streak": 7,
    "longest_loss_streak": 4,
    "profit_factor": 1.45
  },
  "profiles": ["low_risk", "medium_risk", "manual"]
}
```

#### POST `/api/slips`

Create a manual slip.

**Request Body** (`SlipIn`)
```json
{
  "profile": "manual",
  "legs": [
    {
      "match_name": "Team A vs Team B",
      "market": "1",
      "market_type": "result",
      "odds": 1.85,
      "result_url": "https://...",
      "datetime": "2026-08-23T20:00:00",
      "consensus": 65.0,
      "sources": 4,
      "league": "Premier League"
    }
  ],
  "units": 1.0
}
```

**Validation**: Each leg is validated against the match database (fuzzy match on team names), market allow-list, odds > 0, and valid URL format.

**Response**: `{ "slip_id": 43 }`

#### POST `/api/slips/validate_manual`

Validate manual legs without creating a slip.

**Request**: `[ManualLegIn, ...]`
**Response**: `{ "legs": [{"valid": true}, ...], "all_valid": true }`

#### DELETE `/api/slips/{slip_id}`

Delete a slip (only if all legs are Pending).

**Response**: `{ "deleted": 43 }`

#### POST `/api/slips/validate`

Trigger immediate validation of all pending/live slips.

**Response**
```json
{
  "checked": 47,
  "settled": 12,
  "live": 8,
  "errors": 0,
  "live_data": [
    {"match_name": "Team A vs Team B", "score": "2:1", "minute": "75'"}
  ]
}
```

#### POST `/api/slips/generate`

Trigger slip generation for all profiles with `run_daily_count > 0`.

**Response**
```json
{
  "generated": 3,
  "by_profile": {"low_risk": 1, "medium_risk": 2}
}
```

---

### Analytics

#### GET `/api/analytics`

Get comprehensive analytics data.

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `profiles` | string[] | Filter by profiles |
| `date_from` | string | ISO date |
| `date_to` | string | ISO date |

**Response**
```json
{
  "history": [
    {
      "date": "2026-08-22",
      "slips_count": 3,
      "units_bet": 3.0,
      "net_profit": 1.5,
      "cumulative_profit": 45.2,
      "cumulative_bet": 150.0,
      "roi_percentage": 30.1,
      "win_rate": 66.7
    }
  ],
  "market_accuracy": [
    {"market": "1", "won": 45, "lost": 30, "total": 75, "accuracy": 60.0}
  ],
  "pnl_by_market": [
    {"market": "Over 2.5", "won": 20, "lost": 15, "net_profit": 12.5}
  ],
  "correlation": [
    {"legs_count": 3, "total_odds": 3.2, "units": 1.0, "status": "Won", "profit": 2.2}
  ],
  "profile_scatter": [
    {"profile": "low_risk", "avg_odds": 2.1, "win_rate": 65.0, "net_profit": 15.0, "volume": 50, "break_even_win_rate": 47.6}
  ],
  "stats": { ... },
  "profiles": ["low_risk", "medium_risk"],
  "market_breakdown": [
    {"market": "1", "legs": 100, "won": 60, "lost": 40, "win_rate": 60.0, "implied_win_rate": 55.0, "edge": 5.0, "avg_odds": 1.82, "net_profit": 8.5}
  ],
  "league_breakdown": [
    {"league": "Premier League", "legs": 80, "won": 48, "lost": 32, "win_rate": 60.0, "edge": 4.5, "avg_odds": 1.85, "net_profit": 6.2}
  ],
  "rolling_edge": [
    {"date": "2026-08-22", "rolling_edge": 5.2, "rolling_win_rate": 58.0, "rolling_implied": 52.8, "sample_size": 25}
  ],
  "drawdown": [
    {"date": "2026-08-22", "drawdown": -2.5, "peak": 45.2, "cumulative_profit": 42.7}
  ],
  "correlation_matrix": {
    "leagues": ["Premier League", "La Liga"],
    "markets": ["1", "Over 2.5"],
    "matrix": {
      "Premier League": {
        "1": {"win_rate": 62.0, "edge": 4.2, "total": 40},
        "Over 2.5": {"win_rate": 58.0, "edge": 3.1, "total": 35}
      }
    }
  }
}
```

---

### Services

#### GET `/api/services`

Get service status and configuration.

**Response**
```json
{
  "services": {
    "puller": {
      "name": "puller",
      "description": "Checks every 5 minutes if a new database exists on GitHub...",
      "enabled": true,
      "alive": true,
      "hour": null,
      "minute": null,
      "interval_seconds": 300,
      "next_run": "Every 5 min"
    },
    "generator": {
      "name": "generator",
      "description": "Checks every 5 minutes if the scheduled generation hour has arrived...",
      "enabled": true,
      "alive": true,
      "hour": 8,
      "minute": 0,
      "interval_seconds": 300,
      "next_run": "Today 08:00 (in 2h 30m)",
      "last_time_generated": "2026-08-22T08:00:00"
    },
    "verifier": {
      "name": "verifier",
      "description": "Polls every 60 seconds to fetch live scores...",
      "enabled": true,
      "alive": true,
      "hour": null,
      "minute": null,
      "interval_seconds": 60,
      "next_run": "Every 1 min"
    }
  },
  "generate_hour": 8,
  "generate_minute": 0,
  "server_time": "2026-08-22T05:30:00"
}
```

#### POST `/api/services/settings`

Update scheduled generation time.

**Request**: `{ "generate_hour": 8, "generate_minute": 0 }`
**Response**: `{ "generate_hour": 8, "generate_minute": 0 }`

#### POST `/api/services/{name}/toggle`

Toggle a service on/off.

**Response**: `{ "name": "puller", "enabled": false }`

---

### Odds History

#### GET `/api/odds-history/movements/all`

Get movement summary for all future matches.

**Response**
```json
{
  "match_0_abc123": {
    "home": "down",
    "draw": "stable",
    "away": "up",
    "over_25": "down",
    "under_25": "up"
  }
}
```

#### GET `/api/odds-history/movements/significant`

Get movements with strength metrics, filtered to significant only.

**Response**
```json
{
  "match_0_abc123": {
    "home": {"direction": "down", "change_pct": -5.2, "significant": true},
    "over_25": {"direction": "down", "change_pct": -3.8, "significant": false}
  }
}
```

#### GET `/api/odds-history/{match_id}`

Get full odds history for a specific match.

**Response** (`OddsHistoryOut`)
```json
{
  "match_id": 0,
  "match_name": "Team A vs Team B",
  "datetime": "2026-08-23T20:00:00",
  "snapshots": [
    {"timestamp": "2026-08-22T10:00:00", "odds": {"home": 1.90, "draw": 3.30, "away": 4.00}},
    {"timestamp": "2026-08-22T15:00:00", "odds": {"home": 1.85, "draw": 3.40, "away": 4.20}}
  ],
  "movement": {"home": "down", "draw": "up", "away": "up"}
}
```

#### GET `/api/odds-history/{match_id}/movement`

Get just the movement summary for a match.

**Response**: `OddsMovementSummary`

---

### System

#### POST `/api/pull`

Manually trigger database pull from GitHub Releases.

**Response**
```json
{
  "status": "ok",
  "message": "Pull successful",
  "timestamp": "2026-08-22T05:30:00"
}
```

#### GET `/api/status`

Get backend health status.

**Response**
```json
{
  "last_pull": "2026-08-22T05:30:00",
  "matches_loaded": 1247
}
```

#### WebSocket `/ws`

Real-time event stream (see WebSocket section above).

---

## Data Models

### Match Object

| Field | Type | Description |
|-------|------|-------------|
| `match_id` | string | Unique identifier |
| `datetime` | string/null | ISO datetime |
| `home` | string | Home team name |
| `away` | string | Away team name |
| `sources` | integer | Number of data providers |
| `cons_*` | float | Consensus percentages (0-100) |
| `odds_*` | float | Bookmaker odds |
| `result_url` | string/null | Source URL for validation |
| `league` | string/null | Competition name |

### CandidateLeg Object

| Field | Type | Description |
|-------|------|-------------|
| `match_name` | string | "Home vs Away" |
| `datetime` | string/null | Match datetime |
| `market` | string | Market label ("1", "Over 2.5", etc.) |
| `market_type` | string | Category ("result", "over_under_25", etc.) |
| `consensus` | float | Consensus % |
| `odds` | float | Bookmaker odds |
| `result_url` | string/null | Validation URL |
| `league` | string/null | Competition |
| `sources` | integer | Provider count |
| `tier` | integer | 1 (balanced) or 2 (drift) |
| `score` | float | Quality score (0-1) |
| `odds_movement_direction` | string/null | "up", "down", "stable" |
| `odds_movement_strength` | float | Absolute change % |

### BetSlip Object

| Field | Type | Description |
|-------|------|-------------|
| `slip_id` | integer | Auto-increment ID |
| `date_generated` | string | ISO datetime |
| `profile` | string | Profile name |
| `total_odds` | float | Product of leg odds |
| `units` | float | Stake size |
| `slip_status` | string | Won/Lost/Live/Pending |
| `legs` | BetLeg[] | Array of legs |

### BetLeg Object

| Field | Type | Description |
|-------|------|-------------|
| `match_name` | string | |
| `datetime` | string/null | |
| `market` | string | |
| `market_type` | string/null | |
| `odds` | float | |
| `status` | string | Won/Lost/Live/Pending |
| `result_url` | string/null | |
| `league` | string/null | |

---

## Error Responses

All endpoints return standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 500 | Internal Server Error |

**Error Format**
```json
{
  "detail": "Error description"
}
```

**Validation Error Format** (422)
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Rate Limits

No explicit rate limiting in development. For production, configure Nginx rate limiting:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://backend:8000;
}
```

---

## OpenAPI Documentation

Interactive API docs available at:

- **Swagger UI**: `http://localhost:3002/docs`
- **ReDoc**: `http://localhost:3002/redoc`

Generated automatically from FastAPI route definitions and Pydantic models.
