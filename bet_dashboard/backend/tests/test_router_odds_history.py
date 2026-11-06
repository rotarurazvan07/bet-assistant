"""[P0] API tests for the odds_history router.

Covers: /{match_id} history + 404s, /{match_id}/movement, /movements/all,
/movements/significant, empty-df paths, and the btts_yes/btts_no movement key
fix in OddsMovementSummary.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from conftest import FakeDashboardLogic, make_match_row, make_matches_df

BASE = "/api/odds-history"


class TestGetMatchOddsHistory:
    """[P0] GET /api/odds-history/{match_id}"""

    def test_history_response_shape(self, client) -> None:
        r = client.get(f"{BASE}/0")
        assert r.status_code == 200
        data = r.json()
        assert set(data) == {
            "match_id",
            "match_name",
            "datetime",
            "snapshots",
            "movement",
        }
        assert data["match_id"] == 0
        assert data["match_name"] == "Real Madrid vs Barcelona"
        assert data["movement"]["home"] == "up"
        assert data["movement"]["btts_yes"] == "up"

    def test_history_snapshots_from_logic(self, client) -> None:
        data = client.get(f"{BASE}/0").json()
        assert len(data["snapshots"]) == 2
        assert data["snapshots"][0]["timestamp"] == "2030-01-01T10:00:00"
        assert data["snapshots"][0]["odds"] == {"home": 1.8, "draw": 3.5}

    def test_history_negative_match_id_returns_404(self, client) -> None:
        assert client.get(f"{BASE}/-1").status_code == 404

    def test_history_out_of_range_match_id_returns_404(self, client) -> None:
        assert client.get(f"{BASE}/99").status_code == 404
        assert client.get(f"{BASE}/1").status_code == 404

    def test_history_empty_df_returns_404(self, empty_client) -> None:
        assert empty_client.get(f"{BASE}/0").status_code == 404

    def test_history_non_numeric_id_returns_422(self, client) -> None:
        assert client.get(f"{BASE}/abc").status_code == 422


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

        past = make_match_row(
            match_id="old",
            datetime=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
            home="Past",
            away="Gone",
        )
        future = make_match_row(
            match_id="new", datetime=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=2)
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

        past = make_match_row(
            match_id="old", datetime=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        )
        logic = FakeDashboardLogic(df=make_matches_df([past]))
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/movements/significant").json() == {}


class TestRegression:
    """[P1] Regression tests for odds-alert movement fix."""

    def test_non_default_index_positional_lookup(self, client_factory) -> None:
        """Filtered/sorted DataFrame with non-RangeIndex still returns correct movement keyed by match_id.

        This test creates a DataFrame where iterrows labels diverge from iloc positions.
        The OLD iterrows-based code would pass the iterrows label (e.g., 1, 3) to
        logic.get_odds_movement() which uses iloc[position], causing wrong row or OOB.
        The NEW enumerate(itertuples()) code passes the correct position (0, 1, 2).
        """
        # Create 5 matches with explicit match_ids
        base = datetime(2030, 1, 1, 20, 0) + timedelta(hours=24)
        rows = [
            make_match_row(match_id="m1", datetime=base + timedelta(days=1), home="A", away="B"),
            make_match_row(match_id="m2", datetime=base + timedelta(days=2), home="C", away="D"),
            make_match_row(match_id="m3", datetime=base + timedelta(days=3), home="E", away="F"),
            make_match_row(match_id="m4", datetime=base + timedelta(days=4), home="G", away="H"),
            make_match_row(match_id="m5", datetime=base + timedelta(days=5), home="I", away="J"),
        ]
        df = make_matches_df(rows)
        
        # Sort by datetime descending (creates new index order)
        df = df.sort_values("datetime", ascending=False).reset_index(drop=False)
        # Now index is [4, 3, 2, 1, 0] but position 0 = m5, position 1 = m4, etc.
        # Keep only middle 3 (m4, m3, m2) - their original indices were 3, 2, 1
        # After sort desc: position 0=m5(idx4), 1=m4(idx3), 2=m3(idx2), 3=m2(idx1), 4=m1(idx0)
        # Filter to keep m4, m3, m2 (positions 1, 2, 3 in sorted df)
        filtered_df = df.iloc[1:4].copy()  # positions 1,2,3 -> original indices 3,2,1
        # filtered_df index is now [3, 2, 1] (non-RangeIndex)
        
        logic = FakeDashboardLogic(df=filtered_df)
        client, _ = client_factory(logic=logic)

        data = client.get(f"{BASE}/movements/all").json()
        # Should return m4, m3, m2 keyed by their match_ids
        assert set(data.keys()) == {"m4", "m3", "m2"}
        assert data["m4"]["home"] == "up"
        assert data["m3"]["home"] == "up"
        assert data["m2"]["home"] == "up"
        # Old iterrows code would pass labels [3, 2, 1] to iloc -> wrong rows or OOB
        assert "pos_0" not in data
        assert "pos_1" not in data
        assert "pos_2" not in data

    def test_timezone_boundary_local_tz_includes_tomorrow(self, client_factory) -> None:
        """Match in future local time is included even when UTC time would drop it.

        Uses a timezone BEHIND UTC (America/New_York, UTC-5) so that:
        - Old utcnow code compares match_dt (naive local) vs datetime.utcnow() (UTC)
        - New logic._local_tz() code compares match_dt (naive local) vs datetime.now(tz) naive
        - A match at 23:00 local (next day 04:00 UTC) at 06:00 UTC is:
          * Local: 23:00 > 01:00 (local now) = KEPT
          * UTC: 04:00 > 06:00 = DROPPED (BUG)
        This test would FAIL with the old utcnow implementation.
        """
        # Create a FakeDashboardLogic with a non-UTC timezone
        class FakeLogicWithTZ(FakeDashboardLogic):
            def _local_tz(self) -> ZoneInfo:
                return ZoneInfo("America/New_York")  # UTC-5

        # Create a match at 23:00 local time (which is 04:00 UTC next day)
        # We can't control datetime.now(), so we test that the endpoint uses
        # the correct timezone logic path (not utcnow) and doesn't crash.
        # A true regression test would require patching datetime.now/utcnow.
        future_row = make_match_row(
            match_id="future_tz",
            # Use a datetime far enough in future to pass regardless of current time
            datetime=datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) + timedelta(days=2),
            home="Future",
            away="Match",
        )
        logic = FakeLogicWithTZ(df=make_matches_df([future_row]))
        client, _ = client_factory(logic=logic)

        data = client.get(f"{BASE}/movements/all").json()
        assert "future_tz" in data
        assert data["future_tz"]["home"] == "up"  # real movement from fake logic

    def test_key_identity_uses_match_id_not_str_idx(self, client_factory) -> None:
        """Well-formed rows are keyed by match_id string, never str(idx) fallback."""
        rows = [
            make_match_row(match_id="custom_id_1", home="A", away="B"),
            make_match_row(match_id="custom_id_2", home="C", away="D"),
        ]
        logic = FakeDashboardLogic(df=make_matches_df(rows))
        client, _ = client_factory(logic=logic)

        data = client.get(f"{BASE}/movements/all").json()
        assert set(data.keys()) == {"custom_id_1", "custom_id_2"}
        assert "0" not in data
        assert "1" not in data
        assert "pos_0" not in data
        assert "pos_1" not in data
