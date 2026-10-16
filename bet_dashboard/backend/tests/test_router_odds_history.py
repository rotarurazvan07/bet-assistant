"""[P0] API tests for the odds_history router (issue #58).

Covers: /{match_id}/movement, /movements/all,
/movements/significant, empty-df paths, and the btts_yes/btts_no movement key
fix in OddsMovementSummary.
"""

from conftest import FakeDashboardLogic, make_match_row, make_matches_df

BASE = "/api/odds-history"


class TestGetMatchMovement:
    """[P0] GET /api/odds-history/{match_id}/movement"""

    def test_movement_summary_includes_btts_keys_after_fix(self, client) -> None:
        """Guards the btts_yes/btts_no field rename in OddsMovementSummary."""
        data = client.get(f"{BASE}/0/movement").json()
        assert data["home"] == "up"
        assert data["draw"] == "down"
        assert data["away"] is None
        assert data["btts_yes"] == "up"
        assert data["btts_no"] == "down"
        assert data["over_25"] == "stable"

    def test_movement_missing_keys_default_none(self, client) -> None:
        data = client.get(f"{BASE}/0/movement").json()
        assert data["over_05"] is None
        assert data["dc_12"] is None


class TestAllMovements:
    """[P1] GET /api/odds-history/movements/all"""

    def test_future_match_movement_returned(self, client) -> None:
        data = client.get(f"{BASE}/movements/all").json()
        assert "m1" in data
        assert data["m1"]["home"] == "up"
        assert data["m1"]["btts_yes"] == "up"

    def test_past_match_excluded(self, client_factory) -> None:
        from datetime import datetime, timedelta

        past = make_match_row(
            match_id="old",
            datetime=datetime.utcnow() - timedelta(hours=2),
            home="Past",
            away="Gone",
        )
        future = make_match_row(
            match_id="new", datetime=datetime.utcnow() + timedelta(hours=2)
        )
        logic = FakeDashboardLogic(df=make_matches_df([past, future]))
        client, _ = client_factory(logic=logic)
        data = client.get(f"{BASE}/movements/all").json()
        assert set(data) == {"new"}

    def test_empty_df_returns_empty_dict(self, empty_client) -> None:
        assert empty_client.get(f"{BASE}/movements/all").json() == {}

    def test_match_without_movement_skipped(self, client_factory) -> None:
        logic = FakeDashboardLogic()
        logic.get_odds_movement = lambda idx: {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/all").json() == {}


class TestSignificantMovements:
    """[P1] GET /api/odds-history/movements/significant"""

    def test_significant_movement_included(self, client) -> None:
        data = client.get(f"{BASE}/movements/significant").json()
        assert "m1" in data
        assert data["m1"]["home"]["significant"] is True

    def test_no_significant_movement_excluded(self, client_factory) -> None:
        logic = FakeDashboardLogic()
        logic._movement_strength = {
            "home": {"direction": "up", "change_pct": 1.0, "significant": False}
        }
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}

    def test_empty_strength_skipped(self, client_factory) -> None:
        logic = FakeDashboardLogic()
        logic.get_odds_movement_with_strength = lambda idx: {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}

    def test_empty_df_returns_empty_dict(self, empty_client) -> None:
        assert empty_client.get(f"{BASE}/movements/significant").json() == {}

    def test_past_match_excluded(self, client_factory) -> None:
        from datetime import datetime, timedelta

        past = make_match_row(
            match_id="old", datetime=datetime.utcnow() - timedelta(hours=2)
        )
        logic = FakeDashboardLogic(df=make_matches_df([past]))
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}


class TestMovementsAllPayload:
    """F8: matches whose movement has no non-None value are not emitted."""

    def test_all_none_movement_excluded(self, client_factory) -> None:
        """F8: calculate_movement_from_odds returns {market: None} when the
        source confirmed no opening odds; such matches must not appear."""
        logic = FakeDashboardLogic()
        logic.get_odds_movement = lambda idx: {"home": None, "draw": None, "away": None}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/all").json() == {}

    def test_empty_movement_excluded(self, client_factory) -> None:
        """F8: empty movement dicts are skipped as before."""
        logic = FakeDashboardLogic()
        logic.get_odds_movement = lambda idx: {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/all").json() == {}


class TestMatchMovementNotFound:
    """F15: out-of-range / negative match ids must 404, not 200-with-nulls."""

    def test_out_of_range_id_returns_404(self, client) -> None:
        assert client.get(f"{BASE}/99/movement").status_code == 404

    def test_negative_id_returns_404(self, client) -> None:
        assert client.get(f"{BASE}/-1/movement").status_code == 404

    def test_valid_id_returns_200(self, client) -> None:
        assert client.get(f"{BASE}/0/movement").status_code == 200
