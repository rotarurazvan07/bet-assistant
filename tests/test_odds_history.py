"""Tests for embedded odds history tracking functionality."""

from __future__ import annotations

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


class TestExtractHistoryFromOdds:
    """Test _extract_history_from_odds helper."""

    def test_extract_empty_dict(self):
        assert MatchesManager._extract_history_from_odds({}) == []

    def test_extract_none(self):
        assert MatchesManager._extract_history_from_odds(None) == []

    def test_extract_no_history_key(self):
        odds = {"home": 1.5, "draw": 3.0, "away": 5.0}
        assert MatchesManager._extract_history_from_odds(odds) == []

    def test_extract_with_history(self):
        odds = {
            "home": 1.5,
            "history": [{"ts": "2026-05-18T10:00:00", "home": 1.6}],
        }
        result = MatchesManager._extract_history_from_odds(odds)
        assert len(result) == 1
        assert result[0]["ts"] == "2026-05-18T10:00:00"


class TestGetCurrentOddsSnapshot:
    """Test _get_current_odds_snapshot helper."""

    def test_snapshot_excludes_history(self):
        odds = {
            "home": 1.5,
            "draw": 3.0,
            "history": [{"ts": "2026-05-18T10:00:00", "home": 1.6}],
        }
        result = MatchesManager._get_current_odds_snapshot(odds)
        assert "history" not in result
        assert result["home"] == 1.5
        assert result["draw"] == 3.0

    def test_snapshot_excludes_none_values(self):
        odds = {"home": 1.5, "draw": None, "away": 5.0}
        result = MatchesManager._get_current_odds_snapshot(odds)
        assert "draw" not in result
        assert result["home"] == 1.5
        assert result["away"] == 5.0

    def test_snapshot_empty_dict(self):
        assert MatchesManager._get_current_odds_snapshot({}) == {}

    def test_snapshot_none(self):
        assert MatchesManager._get_current_odds_snapshot(None) == {}


class TestAppendToHistory:
    """Test _append_to_history helper."""

    def test_append_first_snapshot(self):
        odds = {"home": 1.5, "draw": 3.0}
        snapshot = {"ts": "2026-05-18T10:00:00", "home": 1.6, "draw": 3.1}
        result = MatchesManager._append_to_history(odds, snapshot, max_entries=3)

        assert "history" in result
        assert len(result["history"]) == 1
        assert result["history"][0]["ts"] == "2026-05-18T10:00:00"
        assert result["home"] == 1.5  # Current values preserved

    def test_append_to_existing_history(self):
        odds = {
            "home": 1.5,
            "history": [{"ts": "2026-05-17T10:00:00", "home": 1.7}],
        }
        snapshot = {"ts": "2026-05-18T10:00:00", "home": 1.6}
        result = MatchesManager._append_to_history(odds, snapshot, max_entries=3)

        assert len(result["history"]) == 2
        assert result["history"][0]["ts"] == "2026-05-17T10:00:00"
        assert result["history"][1]["ts"] == "2026-05-18T10:00:00"

    def test_append_trims_to_max_entries(self):
        odds = {
            "home": 1.5,
            "history": [
                {"ts": "2026-05-16T10:00:00", "home": 1.8},
                {"ts": "2026-05-17T10:00:00", "home": 1.7},
                {"ts": "2026-05-18T10:00:00", "home": 1.6},
            ],
        }
        snapshot = {"ts": "2026-05-19T10:00:00", "home": 1.55}
        result = MatchesManager._append_to_history(odds, snapshot, max_entries=3)

        assert len(result["history"]) == 3
        # Oldest entry should be trimmed
        assert result["history"][0]["ts"] == "2026-05-17T10:00:00"
        assert result["history"][2]["ts"] == "2026-05-19T10:00:00"

    def test_append_empty_snapshot_returns_unchanged(self):
        odds = {"home": 1.5}
        result = MatchesManager._append_to_history(odds, {}, max_entries=3)
        assert result == odds

    def test_append_snapshot_with_only_ts_returns_unchanged(self):
        odds = {"home": 1.5}
        result = MatchesManager._append_to_history(odds, {"ts": "2026-05-18T10:00:00"}, max_entries=3)
        assert result == odds


class TestCalculateMovementFromOdds:
    """Test calculate_movement_from_odds method."""

    def test_movement_no_history(self, manager):
        odds = {"home": 1.5, "draw": 3.0, "away": 5.0}
        result = manager.calculate_movement_from_odds(odds)
        assert result == {}

    def test_movement_with_history_up(self, manager):
        odds = {
            "home": 1.6,
            "draw": 3.0,
            "history": [{"ts": "2026-05-17T10:00:00", "home": 1.5, "draw": 3.0}],
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "up"
        assert result["draw"] == "stable"

    def test_movement_with_history_down(self, manager):
        odds = {
            "home": 1.4,
            "draw": 3.0,
            "history": [{"ts": "2026-05-17T10:00:00", "home": 1.5, "draw": 3.0}],
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "down"

    def test_movement_with_history_stable(self, manager):
        odds = {
            "home": 1.5,
            "draw": 3.0,
            "history": [{"ts": "2026-05-17T10:00:00", "home": 1.5, "draw": 3.0}],
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "stable"
        assert result["draw"] == "stable"

    def test_movement_missing_market_in_history(self, manager):
        odds = {
            "home": 1.5,
            "over_25": 2.0,
            "history": [{"ts": "2026-05-17T10:00:00", "home": 1.4}],
        }
        result = manager.calculate_movement_from_odds(odds)
        assert result["home"] == "up"
        assert result["over_25"] is None  # Not in history

    def test_movement_none_odds(self, manager):
        result = manager.calculate_movement_from_odds(None)
        assert result == {}


class TestGetOddsHistoryFromRow:
    """Test get_odds_history_from_row method."""

    def test_get_history_empty_buffer(self, manager):
        result = manager.get_odds_history_from_row(0)
        assert result == []

    def test_get_history_invalid_index(self, manager):
        result = manager.get_odds_history_from_row(-1)
        assert result == []
        result = manager.get_odds_history_from_row(999)
        assert result == []

    def test_get_history_converts_format(self, manager):
        # Insert a match with embedded history
        manager.ensure_buffer()
        manager.insert(
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": datetime.now().isoformat(),
                "predictions_scores": None,
                "odds": json.dumps(
                    {
                        "home": 1.5,
                        "history": [
                            {"ts": "2026-05-17T10:00:00", "home": 1.6, "draw": 3.0},
                            {"ts": "2026-05-18T10:00:00", "home": 1.55, "draw": 3.1},
                        ],
                    }
                ),
                "result_url": None,
                "league": None,
            }
        )

        result = manager.get_odds_history_from_row(0)
        assert len(result) == 2
        assert result[0]["timestamp"] == "2026-05-17T10:00:00"
        assert result[0]["odds"]["home"] == 1.6
        assert "ts" not in result[0]["odds"]  # ts should not be in odds dict


class TestGetMovementForRow:
    """Test get_movement_for_row method."""

    def test_get_movement_empty_buffer(self, manager):
        result = manager.get_movement_for_row(0)
        assert result == {}

    def test_get_movement_with_data(self, manager):
        manager.ensure_buffer()
        manager.insert(
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": datetime.now().isoformat(),
                "predictions_scores": None,
                "odds": json.dumps(
                    {
                        "home": 1.6,
                        "draw": 3.0,
                        "history": [{"ts": "2026-05-17T10:00:00", "home": 1.5, "draw": 3.0}],
                    }
                ),
                "result_url": None,
                "league": None,
            }
        )

        result = manager.get_movement_for_row(0)
        assert result["home"] == "up"
        assert result["draw"] == "stable"


class TestMergeWithHistoryPreservation:
    """Test merge_with_history_preservation method."""

    @pytest.fixture
    def fresh_db(self):
        """Create a fresh database for merging."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_merge_transfers_history(self, temp_db, fresh_db):
        """Test that history is transferred from current to fresh database."""
        # Set up current database with a match that has odds
        current_manager = MatchesManager(temp_db)
        future_dt = (datetime.now() + timedelta(days=1)).isoformat()

        current_manager.ensure_buffer()
        current_manager.insert(
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.5, "draw": 3.0, "away": 5.0}),
                "result_url": None,
                "league": "Test League",
            }
        )
        current_manager.flush()

        # Set up fresh database with same match but different odds
        fresh_manager = MatchesManager(fresh_db)
        fresh_manager.ensure_buffer()
        fresh_manager.insert(
            {
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.6, "draw": 3.1, "away": 4.8}),
                "result_url": None,
                "league": "Test League",
            }
        )
        fresh_manager.flush()
        fresh_manager.close()

        # Merge with history preservation
        current_manager.merge_with_history_preservation(fresh_db, max_history=3, local_tz="UTC")

        # Check that history was transferred
        buf = current_manager.ensure_buffer()
        assert len(buf) == 1

        odds_json = buf.iloc[0]["odds"]
        odds = json.loads(odds_json)

        assert "history" in odds
        assert len(odds["history"]) == 1
        assert odds["history"][0]["home"] == 1.5  # Old odds in history
        assert odds["home"] == 1.6  # New current odds

        current_manager.close()

    def test_merge_prunes_past_matches(self, temp_db, fresh_db):
        """Test that past matches don't transfer history (they're ignored)."""
        current_manager = MatchesManager(temp_db)
        past_dt = (datetime.now() - timedelta(days=1)).isoformat()
        future_dt = (datetime.now() + timedelta(days=1)).isoformat()

        current_manager.ensure_buffer()
        # Past match - should NOT transfer history
        current_manager.insert(
            {
                "home_team_name": "Past Team A",
                "away_team_name": "Past Team B",
                "datetime": past_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 1.5}),
                "result_url": None,
                "league": None,
            }
        )
        current_manager.flush()

        # Fresh database has a future match
        fresh_manager = MatchesManager(fresh_db)
        fresh_manager.ensure_buffer()
        fresh_manager.insert(
            {
                "home_team_name": "Future Team A",
                "away_team_name": "Future Team B",
                "datetime": future_dt,
                "predictions_scores": None,
                "odds": json.dumps({"home": 2.0}),
                "result_url": None,
                "league": None,
            }
        )
        fresh_manager.flush()
        fresh_manager.close()

        # Merge - past match should not transfer any history
        current_manager.merge_with_history_preservation(fresh_db, max_history=3, local_tz="UTC")

        # Buffer should have the fresh match only (no history since no matching current future match)
        buf = current_manager.ensure_buffer()
        assert len(buf) == 1
        assert buf.iloc[0]["home_team_name"] == "Future Team A"

        # No history should be present (past match was ignored)
        odds = json.loads(buf.iloc[0]["odds"])
        assert "history" not in odds or len(odds.get("history", [])) == 0

        current_manager.close()
