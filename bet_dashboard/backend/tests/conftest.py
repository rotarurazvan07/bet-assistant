"""Fixtures for backend router tests (issue #58, cycle 2).

Architecture decision:
- Routers read state via ``request.app.state.app_logic``.
- We build a fresh FastAPI app per test WITHOUT importing ``main.py`` —
  its module-level ``app = create_app()`` spawns real AppLogic (3 TickerService
  daemon threads + live SQLite), unacceptable in unit tests.
- ``FakeDashboardLogic`` implements the AppLogic/DashboardLogic subset the
  routers use, backed by a REAL pandas DataFrame so router-internal pandas
  logic (market-cell masking, sorting, pagination, iloc indexing) runs for real.
- ``app.state.app_logic`` is a MagicMock(spec=AppLogic): unknown-attribute
  access fails loudly; ``.logic`` delegates to the real-pandas fake.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parents[1]
for _p in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.logic import AppLogic  # noqa: E402


# ── Factories (data-factories pattern: overrides → complete object) ──────────


def make_match_row(**overrides) -> dict:
    """One match row matching the frontend Match interface."""
    row = {
        "match_id": "m1",
        "datetime": datetime(2030, 1, 1, 20, 0) + timedelta(hours=24),
        "home": "Real Madrid",
        "away": "Barcelona",
        "sources": 4,
        "league": "La Liga",
        "result_url": "https://example.com/match/1",
        "cons_home": 55.0,
        "cons_draw": 25.0,
        "cons_away": 20.0,
        "cons_over_25": 60.0,
        "cons_under_25": 40.0,
        "cons_btts_yes": 50.0,
        "cons_btts_no": 50.0,
        "cons_over_05": 80.0,
        "cons_under_05": 20.0,
        "cons_over_15": 70.0,
        "cons_under_15": 30.0,
        "cons_over_35": 30.0,
        "cons_under_35": 70.0,
        "cons_over_45": 15.0,
        "cons_under_45": 85.0,
        "cons_dc_1x": 75.0,
        "cons_dc_12": 60.0,
        "cons_dc_x2": 45.0,
        "odds_home": 1.9,
        "odds_draw": 3.4,
        "odds_away": 4.2,
        "odds_over_25": 1.85,
        "odds_under_25": 1.95,
        "odds_btts_yes": 1.75,
        "odds_btts_no": 2.05,
        "odds_over_05": 1.10,
        "odds_under_05": 8.5,
        "odds_over_15": 1.35,
        "odds_under_15": 3.1,
        "odds_over_35": 2.9,
        "odds_under_35": 1.42,
        "odds_over_45": 4.5,
        "odds_under_45": 1.22,
        "odds_dc_1x": 1.25,
        "odds_dc_12": 1.40,
        "odds_dc_x2": 1.80,
        "scores": [],
    }
    row.update(overrides)
    return row


def make_matches_df(rows=None, empty=False) -> pd.DataFrame:
    if empty:
        return pd.DataFrame()
    return pd.DataFrame(rows if rows is not None else [make_match_row()])


def make_leg(**overrides) -> dict:
    leg = {
        "match_name": "Real Madrid - Barcelona",
        "datetime": None,
        "market": "1",
        "market_type": "result",
        "odds": 1.9,
        "status": "Won",
        "result_url": "https://example.com/match/1",
        "league": "La Liga",
        "predictions": [],
        "final_score": "2:1",
    }
    leg.update(overrides)
    return leg


def make_slip(**overrides):
    """Slip object factory (attributes mirror BetAssistant slip objects)."""
    legs = overrides.pop("legs", None)
    if legs is None:
        legs = [make_leg()]
    slip = SimpleNamespace(
        slip_id=overrides.pop("slip_id", 1),
        profile=overrides.pop("profile", "manual"),
        slip_status=overrides.pop("slip_status", "Won"),
        units=overrides.pop("units", 1.0),
        total_odds=overrides.pop("total_odds", 3.0),
        date_generated=overrides.pop("date_generated", "2030-01-01T10:00:00"),
        legs=[SimpleNamespace(**leg) if isinstance(leg, dict) else leg for leg in legs],
    )
    for k, v in overrides.items():
        setattr(slip, k, v)
    return slip


def make_stats() -> dict:
    return {
        "slips_count": 1,
        "settled_count": 1,
        "won_count": 1,
        "pending_count": 0,
        "win_rate": 100.0,
        "net_profit": 2.0,
        "avg_odds": 3.0,
        "implied_win_rate": 33.33,
        "edge": 66.67,
        "bankroll": 3.0,
    }


def make_candidate_leg(**overrides):
    """CandidateLeg-like object returned by ``build_preview``."""
    leg = {
        "match_name": "Real Madrid vs Barcelona",
        "datetime": datetime(2030, 1, 1, 20, 0),
        "market": "1",
        "market_type": "result",
        "consensus": 55.0,
        "odds": 1.9,
        "result_url": "https://example.com/match/1",
        "league": "La Liga",
        "sources": 4,
        "tier": 1,
        "score": 0.83,
        "odds_movement_direction": "up",
        "odds_movement_strength": 0.08,
        "predictions": [],
    }
    leg.update(overrides)
    return SimpleNamespace(**leg)


# ── Fake DashboardLogic ─────────────────────────────────────────────────────


class FakeDashboardLogic:
    """Real-pandas stand-in for the ``.logic`` facade consumed by routers."""

    def __init__(self, df=None, slips=None) -> None:
        self.df = df if df is not None else make_matches_df()
        self._slips = slips if slips is not None else [make_slip()]
        self._stats = make_stats()
        self._odds_history = [
            {"timestamp": "2030-01-01T10:00:00", "odds": {"home": 1.8, "draw": 3.5}},
            {"timestamp": "2030-01-01T16:00:00", "odds": {"home": 1.9, "draw": 3.4}},
        ]
        self._movement = {"home": "up", "draw": "down", "away": None, "btts_yes": "up", "btts_no": "down", "over_25": "stable"}
        self._movement_strength = {
            "home": {"direction": "up", "change_pct": 5.5, "significant": True},
            "draw": {"direction": "down", "change_pct": -2.9, "significant": False},
        }
        self._pending_urls = {"https://example.com/match/1"}
        self._last_pull = "2030-01-01 09:00"
        self._settings = {
            "services": {"generate_hour": 8, "generate_minute": 30, "toggles": {}},
            "runtime_state": {"last_time_generated": "2030-01-01T08:30:00"},
            "scraper_config": {
                "RUNNER_SETS": {"local": ["forebet", "xgscore"], "actions": ["forebet", "predictz"]}
            },
        }
        self.calls: list[str] = []

    @property
    def match_df(self) -> pd.DataFrame:
        return self.df

    @property
    def last_pull_timestamp(self) -> str:
        return self._last_pull

    @property
    def settings(self):
        holder = self

        class _S:
            @staticmethod
            def get(key, default=None):
                return holder._settings.get(key, default)

        return _S()

    def filter_matches(self, search_text=None, date_from=None, date_to=None, excluded_sources=None):
        self.calls.append("filter_matches")
        df = self.df
        if df.empty:
            return df.copy()
        if search_text:
            mask = df["home"].str.contains(search_text, case=False, na=False) | df["away"].str.contains(
                search_text, case=False, na=False
            )
            df = df[mask]
        return df.copy()

    def get_slips(self, profile=None, date_from=None, date_to=None):
        self.calls.append("get_slips")
        return list(self._slips)

    def stats(self, profile=None, date_from=None, date_to=None):
        self.calls.append("stats")
        return dict(self._stats)

    def get_odds_movement(self, match_id: int) -> dict:
        self.calls.append("get_odds_movement")
        return dict(self._movement)

    def get_odds_movement_with_strength(self, match_id: int) -> dict:
        self.calls.append("get_odds_movement_with_strength")
        return {k: dict(v) for k, v in self._movement_strength.items()}

    def get_odds_history(self, match_id: int) -> list:
        self.calls.append("get_odds_history")
        return [dict(h) for h in self._odds_history]

    def get_pending_urls(self) -> set:
        self.calls.append("get_pending_urls")
        return set(self._pending_urls)


# ── App/client builders ──────────────────────────────────────────────────────


def make_test_client(logic=None, app_mock=None):
    """Build a TestClient with all 8 routers and a spec-mocked AppLogic."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from routers import analytics, builder, matches, odds_history, profiles, services, slips, system

    mock = app_mock if app_mock is not None else MagicMock(spec=AppLogic)
    if logic is not None:
        mock.logic = logic
    application = FastAPI()
    application.state.app_logic = mock
    for router in (
        matches.router,
        builder.router,
        profiles.router,
        slips.router,
        analytics.router,
        services.router,
        system.router,
        odds_history.router,
    ):
        application.include_router(router)
    return TestClient(application), mock


@pytest.fixture()
def fake_logic() -> FakeDashboardLogic:
    return FakeDashboardLogic()


@pytest.fixture()
def fake_app(fake_logic):
    mock = MagicMock(spec=AppLogic)
    mock.logic = fake_logic
    return mock


@pytest.fixture()
def client(fake_app):
    tc, _ = make_test_client(app_mock=fake_app)
    return tc


@pytest.fixture()
def empty_client():
    tc, _ = make_test_client(logic=FakeDashboardLogic(df=make_matches_df(empty=True)))
    return tc


@pytest.fixture()
def client_factory():
    """Direct builder for scenario tests: (logic=..., app_mock=...) → (client, mock)."""
    return make_test_client


@pytest.fixture()
def broadcast_capture(monkeypatch):
    """Capture ws_manager.broadcast_sync payloads instead of broadcasting."""
    captured: list[dict] = []
    import core.ws as ws_module

    monkeypatch.setattr(ws_module.ws_manager, "broadcast_sync", lambda payload: captured.append(payload))
    return captured
