"""[P0] API tests for the odds_history router (issue #58).

Covers: /{match_id} history + 404s, /{match_id}/movement, /movements/all,
/movements/significant, empty-df paths, and the btts_yes/btts_no movement key
fix in OddsMovementSummary.
"""

from __future__ import annotations

from conftest import FakeDashboardLogic, make_matches_df, make_match_row

BASE = "/api/odds-history"


class TestGetMatchOddsHistory:
    """[P0] GET /api/odds-history/{match_id}"""

    def test_history_response_shape(self, client):
        r = client.get(f"{BASE}/0")
        assert r.status_code == 200
        data = r.json()
        assert set(data) == {"match_id", "match_name", "datetime", "snapshots", "movement"}
        assert data["match_id"] == 0
        assert data["match_name"] == "Real Madrid vs Barcelona"
        assert data["movement"]["home"] == "up"
        assert data["movement"]["btts_yes"] == "up"

    def test_history_snapshots_from_logic(self, client):
        data = client.get(f"{BASE}/0").json()
        assert len(data["snapshots"]) == 2
        assert data["snapshots"][0]["timestamp"] == "2030-01-01T10:00:00"
        assert data["snapshots"][0]["odds"] == {"home": 1.8, "draw": 3.5}

    def test_history_negative_match_id_returns_404(self, client):
        assert client.get(f"{BASE}/-1").status_code == 404

    def test_history_out_of_range_match_id_returns_404(self, client):
        assert client.get(f"{BASE}/99").status_code == 404
        assert client.get(f"{BASE}/1").status_code == 404

    def test_history_empty_df_returns_404(self, empty_client):
        assert empty_client.get(f"{BASE}/0").status_code == 404

    def test_history_non_numeric_id_returns_422(self, client):
        assert client.get(f"{BASE}/abc").status_code == 422


class TestGetMatchMovement:
    """[P0] GET /api/odds-history/{match_id}/movement"""

    def test_movement_summary_includes_btts_keys_after_fix(self, client):
        """Guards the btts_yes/btts_no field rename in OddsMovementSummary."""
        data = client.get(f"{BASE}/0/movement").json()
        assert data["home"] == "up"
        assert data["draw"] == "down"
        assert data["away"] is None
        assert data["btts_yes"] == "up"
        assert data["btts_no"] == "down"
        assert data["over_25"] == "stable"

    def test_movement_missing_keys_default_none(self, client):
        data = client.get(f"{BASE}/0/movement").json()
        assert data["over_05"] is None
        assert data["dc_12"] is None


class TestAllMovements:
    """[P1] GET /api/odds-history/movements/all"""

    def test_future_match_movement_returned(self, client):
        data = client.get(f"{BASE}/movements/all").json()
        assert "m1" in data
        assert data["m1"]["home"] == "up"
        assert data["m1"]["btts_yes"] == "up"

    def test_past_match_excluded(self, client_factory):
        from datetime import datetime, timedelta

        past = make_match_row(match_id="old", datetime=datetime.utcnow() - timedelta(hours=2), home="Past", away="Gone")
        future = make_match_row(match_id="new", datetime=datetime.utcnow() + timedelta(hours=2))
        logic = FakeDashboardLogic(df=make_matches_df([past, future]))
        client, _ = client_factory(logic=logic)
        data = client.get(f"{BASE}/movements/all").json()
        assert set(data) == {"new"}

    def test_empty_df_returns_empty_dict(self, empty_client):
        assert empty_client.get(f"{BASE}/movements/all").json() == {}

    def test_match_without_movement_skipped(self, client_factory):
        logic = FakeDashboardLogic()
        logic.get_odds_movement = lambda idx: {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/all").json() == {}


class TestSignificantMovements:
    """[P1] GET /api/odds-history/movements/significant"""

    def test_significant_movement_included(self, client):
        data = client.get(f"{BASE}/movements/significant").json()
        assert "m1" in data
        assert data["m1"]["home"]["significant"] is True

    def test_no_significant_movement_excluded(self, client_factory):
        logic = FakeDashboardLogic()
        logic._movement_strength = {"home": {"direction": "up", "change_pct": 1.0, "significant": False}}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}

    def test_empty_strength_skipped(self, client_factory):
        logic = FakeDashboardLogic()
        logic.get_odds_movement_with_strength = lambda idx: {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}

    def test_empty_df_returns_empty_dict(self, empty_client):
        assert empty_client.get(f"{BASE}/movements/significant").json() == {}

    def test_past_match_excluded(self, client_factory):
        from datetime import datetime, timedelta

        past = make_match_row(match_id="old", datetime=datetime.utcnow() - timedelta(hours=2))
        logic = FakeDashboardLogic(df=make_matches_df([past]))
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}
