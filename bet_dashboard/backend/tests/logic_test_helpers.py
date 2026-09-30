"""Shared helpers for AppLogic tests (issue #59, testing-suite plan cycle 3).

Architecture decisions (documented per plan):
- FakeTicker replaces core.logic.TickerService during AppLogic construction:
  it records (name, on_tick, interval, predicate) wiring but never spawns
  daemon threads. Interval/predicate wiring is verified by inspecting the
  constructed service objects — never by waiting on ticker ticks.
- AppLogic instances are REAL objects built against tmp_path SQLite DBs and
  a throwaway config directory; workspace DBs and real config paths are
  never touched.
- ws_manager.broadcast_sync is a no-op without a running event loop, so
  construction and ticker callbacks are safe by default; tests asserting on
  payloads use the conftest ``broadcast_capture`` fixture.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parents[1]
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bet_framework.core.Slip import CandidateLeg  # noqa: E402
from bet_framework.core.type_defs import MarketLabel, MarketType  # noqa: E402

from core.logic import AppLogic  # noqa: E402


# ── FakeTicker: thread-free test double for TickerService ────────────────────


class FakeTicker:
    """Records constructor wiring; deliberately spawns no daemon thread."""

    instances: list[FakeTicker] = []

    def __init__(self, name, on_tick, interval=60, predicate=None):
        self.name = name
        self.on_tick = on_tick
        self.interval = interval
        self.predicate = predicate
        self.enabled = True
        self._force_run = False
        FakeTicker.instances.append(self)

    def set_enabled(self, enabled):
        self.enabled = enabled

    def update_config(self, interval=None, trigger_now=False):
        if interval is not None:
            self.interval = interval


# ── Seed factories (data-factories pattern: overrides → complete object) ─────


def make_match_row_db(i=0, **overrides):
    """One raw matches-table row: 3 of 4 sources predict a home win."""
    row = {
        "home_team_name": f"Team Home {i}",
        "away_team_name": f"Team Away {i}",
        "datetime": "2030-01-01T20:00:00",
        "predictions_scores": json.dumps(
            [
                {"source": "forebet", "home": 2, "away": 1},
                {"source": "xgscore", "home": 2, "away": 0},
                {"source": "predictz", "home": 3, "away": 1},
                {"source": "windrawwin", "home": 0, "away": 2},
            ]
        ),
        "odds": json.dumps(
            {
                "home": 1.9,
                "draw": 3.4,
                "away": 4.2,
                "over_25": 1.85,
                "under_25": 1.95,
                "btts_yes": 1.75,
                "btts_no": 2.05,
                "history": [
                    {
                        "ts": "2030-01-01T10:00:00",
                        "home": 1.8,
                        "draw": 3.5,
                        "away": 4.4,
                        "over_25": 1.9,
                        "under_25": 1.9,
                        "btts_yes": 1.7,
                        "btts_no": 2.1,
                    }
                ],
            }
        ),
        "result_url": f"https://example.com/match/{i}",
        "league": "La Liga",
    }
    row.update(overrides)
    return row


def seed_matches_db(db_path, rows):
    """Insert raw rows into a matches SQLite DB before AppLogic construction."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_name TEXT NOT NULL,
            away_team_name TEXT NOT NULL,
            datetime TEXT NOT NULL,
            predictions_scores TEXT,
            odds TEXT,
            result_url TEXT,
            league TEXT
        )"""
    )
    for r in rows:
        conn.execute(
            "INSERT INTO matches (home_team_name, away_team_name, datetime,"
            " predictions_scores, odds, result_url, league) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                r["home_team_name"],
                r["away_team_name"],
                r["datetime"],
                r["predictions_scores"],
                r["odds"],
                r["result_url"],
                r["league"],
            ),
        )
    conn.commit()
    conn.close()


# ── Config scaffolding ───────────────────────────────────────────────────────


def _write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def write_config(config_dir, services=None, runtime_state=None, profiles=None):
    """Write a throwaway config dir consumed by SettingsManager (DFS lookup)."""
    config_dir = Path(config_dir)
    default_services = {"generate_hour": 8, "generate_minute": 0, "toggles": {}}
    _write_yaml(config_dir / "services.yaml", services if services is not None else default_services)
    if runtime_state is not None:
        _write_yaml(config_dir / "runtime_state.yaml", runtime_state)
    if profiles:
        for name, cfg in profiles.items():
            _write_yaml(config_dir / "profiles" / f"{name}.yaml", cfg)


def build_app(tmp_path, monkeypatch, *, rows=None, n_rows=3, services=None, runtime_state=None, profiles=None):
    """Construct a REAL AppLogic against isolated tmp DBs + config dir."""
    config_dir = Path(tmp_path) / "config"
    write_config(config_dir, services=services, runtime_state=runtime_state, profiles=profiles)
    matches_db = str(Path(tmp_path) / "matches.db")
    slips_db = str(Path(tmp_path) / "slips.db")
    if rows is None and n_rows:
        rows = [make_match_row_db(i) for i in range(n_rows)]
    if rows:
        seed_matches_db(matches_db, rows)
    FakeTicker.instances.clear()
    monkeypatch.setattr("core.logic.TickerService", FakeTicker)
    app = AppLogic(matches_db, slips_db, str(config_dir))
    return SimpleNamespace(
        app=app,
        matches_db=matches_db,
        slips_db=slips_db,
        config_dir=config_dir,
        tmp_path=Path(tmp_path),
    )


# ── Slip seeding + candidate factory ─────────────────────────────────────────


def seed_slip(app, *, date_generated, total_odds, units, legs, profile="p"):
    """Insert a slip + legs via AppLogic's own BetAssistant connection."""
    conn = app._assistant.conn
    with app._assistant.db_lock:
        cur = conn.execute(
            "INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)",
            (date_generated, profile, total_odds, units),
        )
        slip_id = cur.lastrowid
        for leg in legs:
            conn.execute(
                "INSERT INTO legs (slip_id, match_name, match_datetime, market, market_type,"
                " odds, result_url, status, league, predictions, final_score)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    slip_id,
                    leg.get("match_name", "Team Home 0 - Team Away 0"),
                    leg.get("match_datetime"),
                    leg.get("market", "1"),
                    leg.get("market_type", "result"),
                    leg.get("odds", 1.9),
                    leg.get("result_url"),
                    leg.get("status", "Pending"),
                    leg.get("league", "La Liga"),
                    leg.get("predictions"),
                    leg.get("final_score"),
                ),
            )
        conn.commit()
    return slip_id


def make_leg_row(**overrides):
    """One legs-table row as a plain dict for seed_slip."""
    leg = {
        "match_name": "Team Home 0 - Team Away 0",
        "match_datetime": "2030-01-01T20:00:00",
        "market": "1",
        "market_type": "result",
        "odds": 1.9,
        "result_url": "https://example.com/match/0",
        "status": "Pending",
        "league": "La Liga",
        "predictions": None,
        "final_score": None,
    }
    leg.update(overrides)
    return leg


def make_candidate(i=0, odds=1.9, **overrides):
    """A real CandidateLeg suitable for save_slip / generate_slips flows."""
    return CandidateLeg(
        match_name=f"Team Home {i} - Team Away {i}",
        datetime=datetime(2030, 1, 1, 20, 0),
        market=MarketLabel.HOME,
        market_type=MarketType.RESULT,
        consensus=75.0,
        odds=odds,
        result_url=f"https://example.com/match/{i}",
        sources=4,
        league="La Liga",
        **overrides,
    )


class FakeHTTPResponse:
    """Context-manager stand-in for urllib urlopen() responses."""

    def __init__(self, headers=None):
        self.headers = headers if headers is not None else {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
