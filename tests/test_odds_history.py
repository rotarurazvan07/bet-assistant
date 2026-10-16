"""Tests for source-provided movement (issue #105)."""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from bet_framework.MatchesManager import MatchesManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def manager(temp_db):
    """Create a MatchesManager instance with temp database."""
    mgr = MatchesManager(temp_db)
    yield mgr
    mgr.close()


class TestCalculateMovementFromOdds:
    """Issue #105: movement comes from scraped movement_change_pp, not history."""

    def test_movement_no_pp_data(self, manager):
        odds = {"home": 1.5, "draw": 3.0, "away": 5.0}
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] is None
        assert result["draw"] is None
        assert result["away"] is None

    def test_movement_pp_up(self, manager):
        odds = {
            "home": 1.6,
            "draw": 3.0,
            "movement_change_pp": {"home": 6.67, "draw": 0.0},
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "up"
        assert result["draw"] == "stable"

    def test_movement_pp_down(self, manager):
        odds = {"home": 1.4, "movement_change_pp": {"home": -6.67}}
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "down"

    def test_movement_pp_stable(self, manager):
        odds = {
            "home": 1.5,
            "draw": 3.0,
            "movement_change_pp": {"home": 0.0, "draw": 0.0},
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "stable"
        assert result["draw"] == "stable"

    def test_movement_unconfirmed_market_is_none(self, manager):
        odds = {"home": 1.5, "over_25": 2.0, "movement_change_pp": {"home": 7.14}}
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "up"
        assert result["over_25"] is None

    def test_movement_none_odds(self, manager):
        assert manager.calculate_movement_from_odds(None) == {}


class TestCalculateMovementWithStrength:
    """Issue #105: strength derives from movement_change_pp magnitude."""

    def test_strength_no_pp(self, manager):
        result = manager.calculate_movement_with_strength({"home": 1.5})
        assert result["home"] == {
            "direction": None,
            "change_pct": 0.0,
            "significant": False,
        }

    def test_strength_large_change_significant(self, manager):
        odds = {"home": 1.6, "movement_change_pp": {"home": 10.0}}
        result = manager.calculate_movement_with_strength(odds)
        assert result["home"]["direction"] == "up"
        assert result["home"]["change_pct"] == 10.0
        assert result["home"]["significant"] is True

    def test_strength_small_change_not_significant(self, manager):
        odds = {"home": 3.0, "movement_change_pp": {"home": -2.5}}
        result = manager.calculate_movement_with_strength(odds)
        assert result["home"]["direction"] == "down"
        assert result["home"]["significant"] is False

    def test_strength_none_odds(self, manager):
        assert manager.calculate_movement_with_strength(None) == {}


class TestGetMovementForRow:
    """Test get_movement_for_row method."""

    def test_get_movement_empty_buffer(self, manager):
        result = manager.get_movement_for_row(0)
        assert result == {}

    def test_get_movement_with_data(self, manager):
        manager.ensure_buffer()
        manager.insert(
            "matches",
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": datetime.now().isoformat(),
                "predictions_scores": None,
                "odds": json.dumps(
                    {
                        "home": 1.6,
                        "draw": 3.0,
                        "movement_change_pp": {"home": 6.67, "draw": 0.0},
                    }
                ),
                "result_url": None,
                "league": None,
            },
        )

        result = manager.get_movement_for_row(0)
        assert result["home"] == "up"
        assert result["draw"] == "stable"


class TestMergeFreshDb:
    """Test merge_fresh_db method (issue #105: fresh pull replaces data)."""

    @pytest.fixture
    def fresh_db(self):
        """Create a fresh database for merging."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_merge_replaces_with_fresh_data(self, temp_db, fresh_db):
        """Issue #105: pulls replace data outright - no odds history preserved."""
        # Set up current database with a match that has odds
        current_manager = MatchesManager(temp_db)
        future_dt = (datetime.now() + timedelta(days=1)).isoformat()

        current_manager.ensure_buffer()
        current_manager.insert(
            "matches",
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.5, "draw": 3.0, "away": 5.0}),
                "result_url": None,
                "league": "Test League",
            },
        )
        current_manager.flush()

        # Set up fresh database with same match but different odds
        fresh_manager = MatchesManager(fresh_db)
        fresh_manager.ensure_buffer()
        fresh_manager.insert(
            "matches",
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.6, "draw": 3.1, "away": 4.8}),
                "result_url": None,
                "league": "Test League",
            },
        )
        fresh_manager.flush()
        fresh_manager.close()

        # Merge with history preservation
        current_manager.merge_fresh_db(fresh_db)

        # Check that history was transferred
        buf = current_manager.ensure_buffer()
        assert len(buf) == 1

        odds_json = buf.iloc[0]["odds"]
        odds = json.loads(odds_json)

        assert "history" not in odds
        assert odds["home"] == 1.6  # Fresh current odds win

        current_manager.close()

    def test_merge_prunes_past_matches(self, temp_db, fresh_db):
        """Test that past matches don't transfer history (they're ignored)."""
        current_manager = MatchesManager(temp_db)
        past_dt = (datetime.now() - timedelta(days=1)).isoformat()
        future_dt = (datetime.now() + timedelta(days=1)).isoformat()

        current_manager.ensure_buffer()
        # Past match - should NOT transfer history
        current_manager.insert(
            "matches",
            {
                "home_team_name": "Past Team A",
                "away_team_name": "Past Team B",
                "datetime": past_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.5}),
                "result_url": None,
                "league": None,
            },
        )
        current_manager.flush()

        # Fresh database has a future match
        fresh_manager = MatchesManager(fresh_db)
        fresh_manager.ensure_buffer()
        fresh_manager.insert(
            "matches",
            {
                "home_team_name": "Future Team A",
                "away_team_name": "Future Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 2.0}),
                "result_url": None,
                "league": None,
            },
        )
        fresh_manager.flush()
        fresh_manager.close()

        # Merge - past match should not transfer any history
        current_manager.merge_fresh_db(fresh_db)

        # Buffer should have the fresh match only (no history since no matching current future match)
        buf = current_manager.ensure_buffer()
        assert len(buf) == 1
        assert buf.iloc[0]["home_team_name"] == "Future Team A"

        # No history should be present (past match was ignored)
        odds = json.loads(buf.iloc[0]["odds"])
        assert "history" not in odds or len(odds.get("history", [])) == 0

        current_manager.close()


class TestMergeFreshDbFlushFailure:
    """F7: a flush failure after merge must not wipe previously stored data."""

    @pytest.fixture
    def fresh_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @staticmethod
    def _insert_match(mgr, home, odds):
        mgr.ensure_buffer()
        mgr.insert(
            "matches",
            {
                "home_team_name": home,
                "away_team_name": "Team B",
                "datetime": (datetime.now() + timedelta(days=1)).isoformat(),
                "predictions_scores": None,
                "odds": json.dumps(odds),
                "result_url": None,
                "league": None,
            },
        )

    def test_flush_failure_keeps_old_data(self, temp_db, fresh_db, monkeypatch):
        """F7: monkeypatched flush() raising must leave the OLD rows intact on disk."""
        current_manager = MatchesManager(temp_db)
        self._insert_match(current_manager, "Old Team", {"home": 1.5})
        current_manager.flush()

        fresh_manager = MatchesManager(fresh_db)
        self._insert_match(fresh_manager, "New Team", {"home": 2.0})
        fresh_manager.flush()
        fresh_manager.close()

        def boom():
            raise RuntimeError("simulated flush failure")

        monkeypatch.setattr(current_manager, "flush", boom)
        with pytest.raises(RuntimeError, match="simulated flush failure"):
            current_manager.merge_fresh_db(fresh_db)
        monkeypatch.undo()  # restore flush before close(), else teardown re-raises

        # Old data must still be readable from disk after the failed merge.
        reloaded = MatchesManager(temp_db)
        buf = reloaded.ensure_buffer()
        assert len(buf) == 1
        assert buf.iloc[0]["home_team_name"] == "Old Team"
        reloaded.close()
        current_manager.close()


class TestMovementCorruptData:
    """F11: corrupt movement_change_pp must not raise — unconfirmed instead."""

    def test_pp_not_a_dict_is_unconfirmed(self, manager):
        result = manager.calculate_movement_from_odds(
            {"home": 1.5, "movement_change_pp": "not-a-dict"}
        )
        assert result["home"] is None

    def test_pp_list_is_unconfirmed(self, manager):
        result = manager.calculate_movement_from_odds(
            {"home": 1.5, "movement_change_pp": [5.0, 1.0]}
        )
        assert result["home"] is None

    def test_value_string_is_unconfirmed(self, manager):
        result = manager.calculate_movement_from_odds(
            {"home": 1.5, "movement_change_pp": {"home": "5.6"}}
        )
        assert result["home"] is None

    def test_strength_pp_not_a_dict_is_safe(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": "garbage"}
        )
        assert result["home"]["direction"] is None
        assert result["home"]["significant"] is False

    def test_strength_value_string_is_unconfirmed(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": "5.6"}}
        )
        assert result["home"]["direction"] is None
        assert result["home"]["significant"] is False


class TestSignificanceThreshold:
    """F12: significance is abs(pp) >= threshold (default 5%), no low-odds rule."""

    def test_boundary_exactly_threshold_is_significant(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": 5.0}}
        )
        assert result["home"]["significant"] is True

    def test_boundary_below_threshold_not_significant(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": 4.99}}
        )
        assert result["home"]["significant"] is False

    def test_negative_magnitude_uses_abs(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": -5.0}}
        )
        assert result["home"]["direction"] == "down"
        assert result["home"]["significant"] is True

    def test_low_odds_no_longer_inflates_significance(self, manager):
        """F12: |pp| = 2.0 at odds < 2.0 is NOT significant anymore (old rule dropped)."""
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": 2.0}}
        )
        assert result["home"]["direction"] == "up"
        assert result["home"]["significant"] is False

    def test_custom_threshold_argument(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": 2.0}}, threshold=1.0
        )
        assert result["home"]["significant"] is True

    def test_stable_is_never_significant(self, manager):
        result = manager.calculate_movement_with_strength(
            {"home": 1.5, "movement_change_pp": {"home": 0.0}}
        )
        assert result["home"]["direction"] == "stable"
        assert result["home"]["significant"] is False
