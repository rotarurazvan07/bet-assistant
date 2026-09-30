"""[P0] API tests for the builder router (issue #58).

Covers: POST /preview shape, excluded CRUD (/excluded, /details, /remove,
clear), /leagues, and the _to_config mapping helper.
"""

from __future__ import annotations


from conftest import FakeDashboardLogic, make_candidate_leg, make_matches_df, make_match_row

BASE = "/api/builder"


class TestPreview:
    """[P0] POST /api/builder/preview"""

    def test_preview_shape_matches_frontend_contract(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg()]
        r = client.post(f"{BASE}/preview", json={})
        assert r.status_code == 200
        data = r.json()
        assert set(data) == {"total_odds", "pending_urls", "legs"}
        leg = data["legs"][0]
        for key in (
            "match_name", "datetime", "market", "market_type", "consensus", "odds",
            "result_url", "league", "sources", "tier", "score",
            "odds_movement_direction", "odds_movement_strength", "predictions",
        ):
            assert key in leg, f"missing contract key: {key}"
        # CandidateLeg contract assertions
        assert leg["market"] == "1"
        assert leg["market_type"] == "result"
        assert leg["odds_movement_strength"] == 0.08
        assert leg["datetime"] == "2030-01-01T20:00:00"

    def test_preview_total_odds_is_product_of_leg_odds(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(odds=2.0), make_candidate_leg(odds=1.5, match_name="X vs Y")]
        data = client.post(f"{BASE}/preview", json={}).json()
        assert data["total_odds"] == 3.0

    def test_preview_empty_legs_total_odds_one(self, client, fake_app):
        fake_app.build_preview.return_value = []
        data = client.post(f"{BASE}/preview", json={}).json()
        assert data["total_odds"] == 1.0
        assert data["legs"] == []

    def test_preview_pending_urls_from_logic(self, client, fake_app, fake_logic):
        fake_app.build_preview.return_value = []
        data = client.post(f"{BASE}/preview", json={}).json()
        assert data["pending_urls"] == ["https://example.com/match/1"]

    def test_preview_config_passed_to_build(self, client, fake_app):
        fake_app.build_preview.return_value = []
        body = {"target_odds": 5.0, "target_legs": 4, "consensus_floor": 70.0}
        client.post(f"{BASE}/preview", json=body)
        cfg = fake_app.build_preview.call_args[0][0]
        assert cfg.target_odds == 5.0
        assert cfg.target_legs == 4
        assert cfg.consensus_floor == 70.0

    def test_preview_defaults_applied(self, client, fake_app):
        fake_app.build_preview.return_value = []
        client.post(f"{BASE}/preview", json={})
        cfg = fake_app.build_preview.call_args[0][0]
        assert cfg.target_odds == 3.0
        assert cfg.target_legs == 3
        assert cfg.min_odds == 1.05
        assert cfg.balance_decay == "linear"

    def test_preview_enum_market_serialized_to_value(self, client, fake_app):
        from bet_framework.core.type_defs import MarketLabel, MarketType

        fake_app.build_preview.return_value = [
            make_candidate_leg(market=MarketLabel.OVER_25, market_type=MarketType.OVER_UNDER_25)
        ]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["market"] == "Over 2.5"
        assert leg["market_type"] == "over_under_25"

    def test_preview_none_market_type_serialized_null(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(market_type=None)]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["market_type"] is None

    def test_preview_none_datetime_serialized_null(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(datetime=None)]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["datetime"] is None

    def test_preview_string_datetime_passthrough(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(datetime="2030-01-01 20:00")]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["datetime"] == "2030-01-01 20:00"

    def test_preview_zero_movement_strength_stays_zero(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(odds_movement_direction=None, odds_movement_strength=0.0)]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["odds_movement_direction"] is None
        assert leg["odds_movement_strength"] == 0.0

    def test_preview_nan_score_sanitized_to_none(self, client, fake_app):
        fake_app.build_preview.return_value = [make_candidate_leg(score=float("nan"))]
        leg = client.post(f"{BASE}/preview", json={}).json()["legs"][0]
        assert leg["score"] is None

    def test_preview_extra_body_fields_ignored(self, client, fake_app):
        fake_app.build_preview.return_value = []
        assert client.post(f"{BASE}/preview", json={"unknown_field": 1}).status_code == 200


class TestExcludedCrud:
    """[P0] Excluded URL management endpoints."""

    def test_get_excluded_returns_manual_list(self, client, fake_app):
        fake_app.get_manual_excluded.return_value = ["https://x.com/1"]
        assert client.get(f"{BASE}/excluded").json() == {"excluded": ["https://x.com/1"]}

    def test_add_excluded_persists_and_returns_list(self, client, fake_app):
        fake_app.get_manual_excluded.return_value = ["https://x.com/2"]
        r = client.post(f"{BASE}/excluded", json={"url": "https://x.com/2"})
        assert r.status_code == 200
        fake_app.add_excluded.assert_called_once_with("https://x.com/2")
        assert r.json() == {"excluded": ["https://x.com/2"]}

    def test_remove_excluded_calls_remove(self, client, fake_app):
        fake_app.get_manual_excluded.return_value = []
        r = client.post(f"{BASE}/excluded/remove", json={"url": "https://x.com/2"})
        assert r.status_code == 200
        fake_app.remove_excluded.assert_called_once_with("https://x.com/2")
        assert r.json() == {"excluded": []}

    def test_clear_excluded_returns_empty_list(self, client, fake_app):
        r = client.delete(f"{BASE}/excluded")
        assert r.status_code == 200
        fake_app.clear_excluded.assert_called_once()
        assert r.json() == {"excluded": []}

    def test_add_excluded_missing_url_returns_422(self, client):
        assert client.post(f"{BASE}/excluded", json={}).status_code == 422


class TestExcludedDetails:
    """[P1] GET /api/builder/excluded/details"""

    def test_details_for_url_in_matches_df(self, client_factory):
        row = make_match_row(result_url="https://x.com/1", home="Real Madrid", away="Barcelona")
        logic = FakeDashboardLogic(df=make_matches_df([row]))

        from unittest.mock import MagicMock
        from core.logic import AppLogic

        app_mock = MagicMock(spec=AppLogic)
        app_mock.logic = logic
        app_mock.get_manual_excluded.return_value = ["https://x.com/1"]
        client, _ = client_factory(app_mock=app_mock)
        data = client.get(f"{BASE}/excluded/details").json()
        assert data["excluded"] == [
            {
                "url": "https://x.com/1",
                "match_name": "Real Madrid vs Barcelona",
                "datetime": "2030-01-02T20:00:00",
                "reason": "Manually excluded",
            }
        ]

    def test_details_for_url_not_in_df_uses_url_tail(self, client_factory):
        from unittest.mock import MagicMock
        from core.logic import AppLogic

        app_mock = MagicMock(spec=AppLogic)
        app_mock.logic = FakeDashboardLogic()
        app_mock.get_manual_excluded.return_value = ["https://x.com/missing"]
        client, _ = client_factory(app_mock=app_mock)
        entry = client.get(f"{BASE}/excluded/details").json()["excluded"][0]
        assert entry["match_name"] == "missing"
        assert entry["datetime"] is None

    def test_details_skips_non_http_entries(self, client_factory):
        from unittest.mock import MagicMock
        from core.logic import AppLogic

        app_mock = MagicMock(spec=AppLogic)
        app_mock.logic = FakeDashboardLogic()
        app_mock.get_manual_excluded.return_value = ["not-a-url", "https://x.com/1"]
        client, _ = client_factory(app_mock=app_mock)
        urls = [e["url"] for e in client.get(f"{BASE}/excluded/details").json()["excluded"]]
        assert urls == ["https://x.com/1"]

    def test_details_empty_excluded(self, client, fake_app):
        fake_app.get_manual_excluded.return_value = []
        assert client.get(f"{BASE}/excluded/details").json() == {"excluded": []}


class TestLeagues:
    """[P1] GET /api/builder/leagues"""

    def test_leagues_delegates_to_app(self, client, fake_app):
        fake_app.get_leagues.return_value = ["La Liga", "Serie A"]
        assert client.get(f"{BASE}/leagues").json() == ["La Liga", "Serie A"]


class TestToConfigUnit:
    """[P2] _to_config maps all BetSlipConfigIn fields to BetSlipConfig."""

    def test_full_mapping(self):
        from core.schemas import BetSlipConfigIn
        from routers.builder import _to_config

        body = BetSlipConfigIn(
            target_odds=4.0, target_legs=5, max_legs_overflow=2, consensus_floor=60.0,
            min_odds=1.2, tolerance_factor=0.3, stop_threshold=0.9, min_legs_fill_ratio=0.8,
            quality_vs_balance=0.7, consensus_vs_sources=0.4, included_markets=["1", "X"],
            included_leagues=["La Liga"], date_from="2030-01-01", date_to="2030-01-02",
            excluded_sources=["forebet"], consensus_shrinkage_k=2.0, min_source_edge=0.1,
            max_single_leg_odds=3.0, tol_lower=0.2, tol_upper=0.15, balance_decay="gaussian",
            min_pick_quality=0.3, odds_movement_weight=0.1, odds_movement_strength_min=0.2,
        )
        cfg = _to_config(body)
        assert cfg.target_odds == 4.0
        assert cfg.target_legs == 5
        assert cfg.max_legs_overflow == 2
        assert cfg.consensus_floor == 60.0
        assert cfg.min_odds == 1.2
        assert cfg.tolerance_factor == 0.3
        assert cfg.stop_threshold == 0.9
        assert cfg.min_legs_fill_ratio == 0.8
        assert cfg.quality_vs_balance == 0.7
        assert cfg.consensus_vs_sources == 0.4
        assert cfg.included_markets == ["1", "X"]
        assert cfg.included_leagues == ["La Liga"]
        assert cfg.date_from == "2030-01-01"
        assert cfg.date_to == "2030-01-02"
        assert cfg.excluded_sources == ["forebet"]
        assert cfg.consensus_shrinkage_k == 2.0
        assert cfg.min_source_edge == 0.1
        assert cfg.max_single_leg_odds == 3.0
        assert cfg.tol_lower == 0.2
        assert cfg.tol_upper == 0.15
        assert cfg.balance_decay == "gaussian"
        assert cfg.min_pick_quality == 0.3
        assert cfg.odds_movement_weight == 0.1
        assert cfg.odds_movement_strength_min == 0.2