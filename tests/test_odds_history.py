"""Tests for odds history tracking functionality."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from bet_framework.MatchesManager import MatchesManager
from bet_framework.core.Match import Match, Odds


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
    return MatchesManager(temp_db)


class TestOddsHistoryTable:
    """Test odds_history table creation and schema."""

    def test_odds_history_table_created(self, manager):
        """Verify odds_history table is created."""
        with manager.db_lock:
            cursor = manager.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='odds_history'"
            )
            result = cursor.fetchone()
        assert result is not None
        assert result[0] == "odds_history"

    def test_odds_history_indexes_created(self, manager):
        """Verify indexes are created on odds_history table."""
        with manager.db_lock:
            cursor = manager.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_odds_history%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_odds_history_match" in indexes
        assert "idx_odds_history_ts" in indexes


class TestCaptureOddsSnapshot:
    """Test capture_odds_snapshot functionality."""

    def test_capture_snapshot_inserts_record(self, manager):
        """Test that capturing a snapshot inserts a record."""
        odds = {"home": 1.5, "draw": 3.0, "away": 5.0}
        manager.capture_odds_snapshot(match_id=1, odds=odds)

        with manager.db_lock:
            cursor = manager.conn.execute(
                "SELECT match_id, odds FROM odds_history WHERE match_id = 1"
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == 1
        stored_odds = json.loads(row[1])
        assert stored_odds["home"] == 1.5
        assert stored_odds["draw"] == 3.0
        assert stored_odds["away"] == 5.0

    def test_capture_snapshot_empty_odds_skipped(self, manager):
        """Test that empty odds are not captured."""
        manager.capture_odds_snapshot(match_id=1, odds={})
        manager.capture_odds_snapshot(match_id=2, odds=None)

        with manager.db_lock:
            cursor = manager.conn.execute("SELECT COUNT(*) FROM odds_history")
            count = cursor.fetchone()[0]

        assert count == 0

    def test_capture_multiple_snapshots(self, manager):
        """Test capturing multiple snapshots for the same match."""
        odds1 = {"home": 1.5, "draw": 3.0, "away": 5.0}
        odds2 = {"home": 1.6, "draw": 2.9, "away": 4.8}

        manager.capture_odds_snapshot(match_id=1, odds=odds1)
        manager.capture_odds_snapshot(match_id=1, odds=odds2)

        with manager.db_lock:
            cursor = manager.conn.execute(
                "SELECT COUNT(*) FROM odds_history WHERE match_id = 1"
            )
            count = cursor.fetchone()[0]

        assert count == 2


class TestGetOddsHistory:
    """Test get_odds_history functionality."""

    def test_get_history_empty(self, manager):
        """Test getting history for match with no snapshots."""
        history = manager.get_odds_history(match_id=999)
        assert history == []

    def test_get_history_returns_snapshots(self, manager):
        """Test getting history returns all snapshots."""
        odds1 = {"home": 1.5}
        odds2 = {"home": 1.6}

        manager.capture_odds_snapshot(match_id=1, odds=odds1)
        manager.capture_odds_snapshot(match_id=1, odds=odds2)

        history = manager.get_odds_history(match_id=1)

        assert len(history) == 2
        assert history[0]["odds"]["home"] == 1.5
        assert history[1]["odds"]["home"] == 1.6

    def test_get_history_chronological_order(self, manager):
        """Test that history is returned in chronological order."""
        for i in range(5):
            manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5 + i * 0.1})

        history = manager.get_odds_history(match_id=1)

        assert len(history) == 5
        # Verify ascending order by checking odds values
        for i in range(len(history) - 1):
            assert history[i]["odds"]["home"] <= history[i + 1]["odds"]["home"]


class TestPruneOldHistory:
    """Test prune_old_history functionality."""

    def test_prune_removes_past_match_history(self, manager, temp_db):
        """Test that pruning removes history for past matches."""
        # Insert a past match directly
        past_dt = (datetime.utcnow() - timedelta(days=1)).isoformat()
        with manager.db_lock:
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime) VALUES (?, ?, ?)",
                ("Past Home", "Past Away", past_dt),
            )
            manager.conn.commit()
            # Get the match ID
            cursor = manager.conn.execute("SELECT id FROM matches WHERE home_team_name = 'Past Home'")
            match_id = cursor.fetchone()[0]

        # Capture odds for this past match
        manager.capture_odds_snapshot(match_id=match_id, odds={"home": 1.5})

        # Verify snapshot exists
        history_before = manager.get_odds_history(match_id)
        assert len(history_before) == 1

        # Prune
        deleted = manager.prune_old_history()

        # Verify snapshot was deleted
        history_after = manager.get_odds_history(match_id)
        assert deleted == 1
        assert len(history_after) == 0

    def test_prune_keeps_future_match_history(self, manager):
        """Test that pruning keeps history for future matches."""
        # Insert a future match directly
        future_dt = (datetime.utcnow() + timedelta(days=1)).isoformat()
        with manager.db_lock:
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime) VALUES (?, ?, ?)",
                ("Future Home", "Future Away", future_dt),
            )
            manager.conn.commit()
            cursor = manager.conn.execute("SELECT id FROM matches WHERE home_team_name = 'Future Home'")
            match_id = cursor.fetchone()[0]

        # Capture odds
        manager.capture_odds_snapshot(match_id=match_id, odds={"home": 1.5})

        # Prune
        deleted = manager.prune_old_history()

        # Verify snapshot still exists
        history = manager.get_odds_history(match_id)
        assert deleted == 0
        assert len(history) == 1


class TestCalculateMovement:
    """Test calculate_movement functionality."""

    def test_calculate_movement_no_history(self, manager):
        """Test movement calculation with no history returns empty dict."""
        movement = manager.calculate_movement(match_id=999)
        assert movement == {}

    def test_calculate_movement_single_snapshot(self, manager):
        """Test movement calculation with single snapshot returns empty dict."""
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5})
        movement = manager.calculate_movement(match_id=1)
        assert movement == {}

    def test_calculate_movement_up(self, manager):
        """Test movement calculation detects upward movement."""
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5, "draw": 3.0})
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.7, "draw": 3.2})

        movement = manager.calculate_movement(match_id=1)

        assert movement["home"] == "up"
        assert movement["draw"] == "up"

    def test_calculate_movement_down(self, manager):
        """Test movement calculation detects downward movement."""
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.7, "away": 5.0})
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5, "away": 4.5})

        movement = manager.calculate_movement(match_id=1)

        assert movement["home"] == "down"
        assert movement["away"] == "down"

    def test_calculate_movement_stable(self, manager):
        """Test movement calculation detects stable odds."""
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5})
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5})

        movement = manager.calculate_movement(match_id=1)

        assert movement["home"] == "stable"

    def test_calculate_movement_mixed(self, manager):
        """Test movement calculation with mixed directions."""
        manager.capture_odds_snapshot(
            match_id=1,
            odds={"home": 1.5, "draw": 3.0, "away": 5.0}
        )
        manager.capture_odds_snapshot(
            match_id=1,
            odds={"home": 1.7, "draw": 3.0, "away": 4.5}
        )

        movement = manager.calculate_movement(match_id=1)

        assert movement["home"] == "up"
        assert movement["draw"] == "stable"
        assert movement["away"] == "down"

    def test_calculate_movement_missing_values(self, manager):
        """Test movement calculation handles missing values."""
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.5})
        manager.capture_odds_snapshot(match_id=1, odds={"home": 1.7, "draw": 3.0})

        movement = manager.calculate_movement(match_id=1)

        assert movement["home"] == "up"
        assert movement["draw"] is None  # Missing in first snapshot


class TestCaptureAllFutureOdds:
    """Test capture_all_future_odds functionality."""

    def test_capture_all_future_odds(self, manager):
        """Test capturing odds for all future matches."""
        # Insert future matches with odds
        future_dt = (datetime.utcnow() + timedelta(days=1)).isoformat()
        odds_json = json.dumps({"home": 1.5, "draw": 3.0, "away": 5.0})

        with manager.db_lock:
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime, odds) VALUES (?, ?, ?, ?)",
                ("Home 1", "Away 1", future_dt, odds_json),
            )
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime, odds) VALUES (?, ?, ?, ?)",
                ("Home 2", "Away 2", future_dt, odds_json),
            )
            manager.conn.commit()

        # Capture all future odds
        captured = manager.capture_all_future_odds()

        # Verify snapshots were created
        assert captured == 2

        with manager.db_lock:
            cursor = manager.conn.execute("SELECT COUNT(*) FROM odds_history")
            count = cursor.fetchone()[0]

        assert count == 2

    def test_capture_skips_past_matches(self, manager):
        """Test that capturing skips past matches."""
        past_dt = (datetime.utcnow() - timedelta(days=1)).isoformat()
        odds_json = json.dumps({"home": 1.5})

        with manager.db_lock:
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime, odds) VALUES (?, ?, ?, ?)",
                ("Past Home", "Past Away", past_dt, odds_json),
            )
            manager.conn.commit()

        # Capture all future odds
        captured = manager.capture_all_future_odds()

        # Verify no snapshots were created for past match
        assert captured == 0

    def test_capture_skips_matches_without_odds(self, manager):
        """Test that capturing skips matches without odds."""
        future_dt = (datetime.utcnow() + timedelta(days=1)).isoformat()

        with manager.db_lock:
            manager.conn.execute(
                "INSERT INTO matches (home_team_name, away_team_name, datetime) VALUES (?, ?, ?)",
                ("No Odds Home", "No Odds Away", future_dt),
            )
            manager.conn.commit()

        # Capture all future odds
        captured = manager.capture_all_future_odds()

        # Verify no snapshots were created
        assert captured == 0
