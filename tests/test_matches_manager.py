"""
Comprehensive tests for MatchesManager.

Public API covered:
  __init__, add_match, fetch_matches, reset_matches_db, merge_databases, flush, _find

Each method has: normal case(s), edge case(s), error case.
Plus 5 complex integration scenarios at the bottom.
"""

import contextlib
import json
import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

from bet_framework.core.Match import Match, Odds, Score
from bet_framework.MatchesManager import MatchesManager

# ── Helpers ──────────────────────────────────────────────────────────────────

SIMILARITY_CONFIG = {
    "threshold": 65,
    "acronyms": {"fc": "football club", "utd": "united"},
    "synonyms": {},
    "weights": {"token": 0.5, "substr": 0.1, "phonetic": 0.1, "ratio": 0.3},
}

DT_BASE = datetime(2026, 4, 1, 15, 0, 0)


def make_match(
    home="Team A",
    away="Team B",
    dt=None,
    preds=None,
    odds=None,
    url=None,
):
    """Helper to build a Match object quickly."""
    return Match(
        home_team=home,
        away_team=away,
        datetime=dt or DT_BASE,
        predictions=preds or [],
        odds=odds,
        result_url=url,
    )


def make_chunk_db(path, matches):
    """Create a standalone chunk .db file compatible with MatchesManager merge."""
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_name     TEXT NOT NULL,
            away_team_name     TEXT NOT NULL,
            datetime           TEXT NOT NULL,
            predictions_scores TEXT,
            odds               TEXT,
            result_url         TEXT
        )
    """)
    for m in matches:
        preds_json = (
            json.dumps([s.__dict__ for s in m.predictions]) if m.predictions else None
        )
        odds_json = None
        if m.odds:
            from dataclasses import asdict
            odds_json = json.dumps(asdict(m.odds))
        conn.execute(
            "INSERT INTO matches (home_team_name, away_team_name, datetime, predictions_scores, odds, result_url) VALUES (?, ?, ?, ?, ?, ?)",
            (
                m.home_team,
                m.away_team,
                m.datetime.isoformat(),
                preds_json,
                odds_json,
                m.result_url,
            ),
        )
    conn.commit()
    conn.close()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mm(tmp_path):
    """MatchesManager with similarity engine enabled."""
    manager = MatchesManager(
        str(tmp_path / "test.db"), similarity_config=SIMILARITY_CONFIG
    )
    yield manager
    with contextlib.suppress(Exception):
        manager.close()


@pytest.fixture
def mm_no_sim(tmp_path):
    """MatchesManager without similarity engine."""
    manager = MatchesManager(str(tmp_path / "nosim.db"), similarity_config=None)
    yield manager
    with contextlib.suppress(Exception):
        manager.close()


@pytest.fixture
def populated_mm(tmp_path):
    """MatchesManager pre-loaded with 3 matches."""
    manager = MatchesManager(
        str(tmp_path / "populated.db"), similarity_config=SIMILARITY_CONFIG
    )
    manager.add_match(
        make_match("Arsenal", "Chelsea", DT_BASE, [Score("src_a", 2, 1)])
    )
    manager.add_match(
        make_match(
            "Liverpool",
            "Man City",
            DT_BASE + timedelta(hours=2),
            [Score("src_a", 1, 1)],
        )
    )
    manager.add_match(
        make_match(
            "Real Madrid",
            "Barcelona",
            DT_BASE + timedelta(days=1),
            [Score("src_b", 3, 2)],
        )
    )
    yield manager
    with contextlib.suppress(Exception):
        manager.close()


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestInit:
    def test_normal_creates_db_file(self, tmp_path):
        path = str(tmp_path / "init_test.db")
        mm = MatchesManager(path, similarity_config=SIMILARITY_CONFIG)
        assert os.path.exists(path)
        mm.close()

    def test_normal_with_similarity_engine(self, tmp_path):
        mm = MatchesManager(
            str(tmp_path / "sim.db"), similarity_config=SIMILARITY_CONFIG
        )
        assert mm.similarity_engine is not None
        mm.close()

    def test_normal_without_similarity_engine(self, tmp_path):
        mm = MatchesManager(str(tmp_path / "nosim.db"), similarity_config=None)
        assert mm.similarity_engine is None
        mm.close()

    def test_edge_empty_db_has_matches_table(self, mm):
        rows = mm.fetch_rows("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        assert len(rows) == 1


# ── add_match ─────────────────────────────────────────────────────────────────


class TestAddMatch:
    def test_normal_inserts_single_match(self, mm):
        idx = mm.add_match(make_match("Home", "Away"))
        assert idx is not None
        buf = mm.ensure_buffer()
        assert len(buf) == 1
        assert buf.iloc[0]["home_team_name"] == "Home"

    def test_normal_inserts_match_with_predictions(self, mm):
        match = make_match("H", "A", preds=[Score("src1", 2, 1), Score("src2", 0, 0)])
        mm.add_match(match)
        buf = mm.ensure_buffer()
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        assert len(preds) == 2
        assert preds[0]["source"] == "src1"

    def test_normal_inserts_match_with_odds(self, mm):
        match = make_match("H", "A", odds=Odds(home=1.5, draw=3.2, away=4.0))
        mm.add_match(match)
        buf = mm.ensure_buffer()
        odds = json.loads(buf.iloc[0]["odds"])
        assert odds["home"] == 1.5
        assert odds["draw"] == 3.2

    def test_normal_inserts_match_with_url(self, mm):
        match = make_match("H", "A", url="https://example.com/match/1")
        mm.add_match(match)
        buf = mm.ensure_buffer()
        assert buf.iloc[0]["result_url"] == "https://example.com/match/1"

    def test_normal_merges_predictions_for_same_match(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_a", 2, 1)]))
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_b", 1, 0)]))
        buf = mm.ensure_buffer()
        assert len(buf) == 1  # merged into one row
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        sources = {p["source"] for p in preds}
        assert sources == {"src_a", "src_b"}

    def test_normal_merges_odds_for_same_match(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", odds=Odds(home=1.5)))
        mm.add_match(make_match("Arsenal", "Chelsea", odds=Odds(draw=3.0)))
        buf = mm.ensure_buffer()
        assert len(buf) == 1
        odds = json.loads(buf.iloc[0]["odds"])
        assert odds["home"] == 1.5
        assert odds["draw"] == 3.0

    def test_normal_url_preserved_from_first_insert(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_a", 2, 1)], url="https://first.com"))
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_b", 1, 0)], url="https://second.com"))
        buf = mm.ensure_buffer()
        # First URL is preserved, second is not overwritten
        assert buf.iloc[0]["result_url"] == "https://first.com"

    def test_normal_updates_datetime_precision(self, mm):
        # First add with midnight (date-only), then with precise time
        dt_midnight = datetime(2026, 4, 1, 0, 0, 0)
        dt_precise = datetime(2026, 4, 1, 15, 30, 0)
        mm.add_match(make_match("Arsenal", "Chelsea", dt=dt_midnight))
        mm.add_match(make_match("Arsenal", "Chelsea", dt=dt_precise))
        buf = mm.ensure_buffer()
        assert "15:30" in buf.iloc[0]["datetime"]

    def test_edge_source_collision_skips_merge(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_a", 2, 1)]))
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("src_a", 3, 0)]))
        buf = mm.ensure_buffer()
        # Source collision — second match added as a separate row
        # or predictions not merged (depending on implementation)
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        # Should only have one prediction from src_a (the original)
        src_a_preds = [p for p in preds if p["source"] == "src_a"]
        assert len(src_a_preds) == 1

    def test_edge_no_predictions_no_odds(self, mm):
        match = make_match("H", "A", preds=[], odds=None)
        idx = mm.add_match(match)
        assert idx is not None

    def test_edge_similar_team_names_merge(self, mm):
        """Teams with fuzzy-similar names should be merged."""
        mm.add_match(make_match("Arsenal FC", "Chelsea", preds=[Score("s1", 1, 0)]))
        mm.add_match(make_match("Arsenal", "Chelsea", preds=[Score("s2", 2, 1)]))
        buf = mm.ensure_buffer()
        assert len(buf) == 1  # merged via similarity

    def test_edge_different_dates_not_merged(self, mm):
        """Matches on different dates should not be merged."""
        dt1 = datetime(2026, 4, 1, 15, 0)
        dt2 = datetime(2026, 4, 10, 15, 0)
        mm.add_match(make_match("Arsenal", "Chelsea", dt=dt1))
        mm.add_match(make_match("Arsenal", "Chelsea", dt=dt2))
        buf = mm.ensure_buffer()
        assert len(buf) == 2  # different dates

    def test_error_returns_none_on_exception(self, mm):
        """add_match should not raise — returns None on error."""
        # Pass something that will cause an internal error
        result = mm.add_match(Match(None, None, None, None, None))
        assert result is None


# ── fetch_matches ─────────────────────────────────────────────────────────────


class TestFetchMatches:
    def test_normal_returns_dataframe(self, populated_mm):
        df = populated_mm.fetch_matches()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_normal_has_expected_columns(self, populated_mm):
        df = populated_mm.fetch_matches()
        for col in ["home_name", "away_name", "datetime", "scores", "odds", "result_url"]:
            assert col in df.columns

    def test_normal_scores_deserialized_as_lists(self, populated_mm):
        df = populated_mm.fetch_matches()
        for scores in df["scores"]:
            assert isinstance(scores, list)

    def test_normal_datetime_is_python_datetime(self, populated_mm):
        df = populated_mm.fetch_matches()
        for dt in df["datetime"]:
            assert isinstance(dt, datetime)

    def test_edge_empty_db_returns_empty_dataframe(self, mm):
        df = mm.fetch_matches()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_edge_match_with_no_scores_returns_empty_list(self, mm):
        mm.add_match(make_match("A", "B", preds=[]))
        df = mm.fetch_matches()
        assert df.iloc[0]["scores"] == []


# ── reset_matches_db ──────────────────────────────────────────────────────────


class TestResetMatchesDb:
    def test_normal_clears_all_matches(self, populated_mm):
        populated_mm.reset_matches_db()
        buf = populated_mm.ensure_buffer()
        assert len(buf) == 0

    def test_normal_can_add_after_reset(self, populated_mm):
        populated_mm.reset_matches_db()
        populated_mm.add_match(make_match("New", "Match"))
        buf = populated_mm.ensure_buffer()
        assert len(buf) == 1

    def test_edge_reset_empty_db_is_noop(self, mm):
        mm.reset_matches_db()  # should not raise
        buf = mm.ensure_buffer()
        assert len(buf) == 0


# ── flush ─────────────────────────────────────────────────────────────────────


class TestFlush:
    def test_normal_dirty_buffer_persists_to_disk(self, mm):
        mm.add_match(make_match("Flush", "Test"))
        mm.flush()
        # Read from disk directly
        rows = mm.fetch_rows("SELECT * FROM matches WHERE home_team_name = ?", ("Flush",))
        assert len(rows) == 1

    def test_normal_flush_clears_dirty_flag(self, mm):
        mm.add_match(make_match("A", "B"))
        assert mm._dirty is True
        mm.flush()
        assert mm._dirty is False

    def test_edge_flush_when_not_dirty_is_noop(self, mm):
        mm.ensure_buffer()
        mm._dirty = False
        mm.flush()  # should not raise

    def test_edge_flush_preserves_indexes(self, mm):
        mm.add_match(make_match("A", "B"))
        mm.flush()
        # Verify indexes still exist
        rows = mm.fetch_rows(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='matches'"
        )
        index_names = [r["name"] for r in rows]
        assert "idx_datetime" in index_names
        assert "idx_home_team" in index_names


# ── _find ─────────────────────────────────────────────────────────────────────


class TestFind:
    def test_normal_finds_exact_match(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea"))
        found, idx = mm._find("Arsenal", "Chelsea", DT_BASE)
        assert found is not None
        assert idx is not None

    def test_normal_finds_similar_match(self, mm):
        mm.add_match(make_match("Manchester United", "Liverpool"))
        found, idx = mm._find("Manchester United FC", "Liverpool", DT_BASE)
        assert found is not None

    def test_normal_returns_none_for_different_team(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea"))
        found, idx = mm._find("Barcelona", "Real Madrid", DT_BASE)
        assert found is None
        assert idx is None

    def test_edge_date_window_within_one_day(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", dt=DT_BASE))
        # Same day offset
        found, _ = mm._find("Arsenal", "Chelsea", DT_BASE + timedelta(hours=5))
        assert found is not None

    def test_edge_date_too_far_returns_none(self, mm):
        mm.add_match(make_match("Arsenal", "Chelsea", dt=DT_BASE))
        found, _ = mm._find("Arsenal", "Chelsea", DT_BASE + timedelta(days=5))
        assert found is None

    def test_edge_empty_buffer_returns_none(self, mm):
        found, idx = mm._find("Any", "Team", DT_BASE)
        assert found is None

    def test_edge_no_similarity_engine_returns_none(self, mm_no_sim):
        mm_no_sim.add_match(make_match("Arsenal", "Chelsea"))
        found, _ = mm_no_sim._find("Arsenal", "Chelsea", DT_BASE)
        assert found is None  # no engine → cannot find


# ── merge_databases ───────────────────────────────────────────────────────────


class TestMergeDatabases:
    def test_normal_merges_single_chunk(self, mm, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db",
            [make_match("Arsenal", "Chelsea", preds=[Score("s1", 2, 1)])],
        )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 1

    def test_normal_merges_multiple_chunks(self, mm, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        for i in range(3):
            make_chunk_db(
                chunk_dir / f"chunk{i}.db",
                [
                    make_match(
                        f"Team{i}A",
                        f"Team{i}B",
                        dt=DT_BASE + timedelta(days=i),
                        preds=[Score(f"src{i}", i, i + 1)],
                    )
                ],
            )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 3

    def test_normal_merges_predictions_from_different_chunks(self, mm, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db",
            [make_match("Arsenal", "Chelsea", preds=[Score("src_a", 2, 1)])],
        )
        make_chunk_db(
            chunk_dir / "chunk2.db",
            [make_match("Arsenal", "Chelsea", preds=[Score("src_b", 1, 0)])],
        )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 1  # merged into one
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        sources = {p["source"] for p in preds}
        assert sources == {"src_a", "src_b"}

    def test_edge_empty_directory_is_noop(self, mm, tmp_path):
        empty_dir = tmp_path / "empty_chunks"
        empty_dir.mkdir()
        mm.merge_databases(str(empty_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 0

    def test_edge_chunk_with_odds(self, mm, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db",
            [make_match("A", "B", odds=Odds(home=1.5, draw=3.0, away=5.0))],
        )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        odds = json.loads(buf.iloc[0]["odds"])
        assert odds["home"] == 1.5


# ── Complex Scenarios ─────────────────────────────────────────────────────────


class TestMatchesManagerScenarios:
    def test_scenario_full_lifecycle_add_flush_fetch(self, mm):
        """Add matches → flush → fetch_matches → verify DataFrame integrity."""
        mm.add_match(
            make_match(
                "Arsenal",
                "Chelsea",
                preds=[Score("src1", 2, 1)],
                odds=Odds(home=1.8, draw=3.5, away=4.2),
                url="https://example.com/1",
            )
        )
        mm.add_match(
            make_match(
                "Liverpool",
                "Man City",
                dt=DT_BASE + timedelta(hours=3),
                preds=[Score("src2", 1, 1)],
            )
        )
        mm.flush()

        df = mm.fetch_matches()
        assert len(df) == 2
        arsenal_row = df[df["home_name"] == "Arsenal"].iloc[0]
        assert arsenal_row["away_name"] == "Chelsea"
        assert len(arsenal_row["scores"]) == 1
        assert arsenal_row["result_url"] == "https://example.com/1"

    def test_scenario_multi_source_merge_dedup(self, mm, tmp_path):
        """3 chunks with overlapping matches — ensure dedup and source merging."""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()

        # All three chunks have Arsenal vs Chelsea but from different sources
        for i, src in enumerate(["soccervista", "forebet", "predictz"]):
            make_chunk_db(
                chunk_dir / f"chunk{i}.db",
                [make_match("Arsenal", "Chelsea", preds=[Score(src, 2, 1)])],
            )

        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 1
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        sources = {p["source"] for p in preds}
        assert sources == {"soccervista", "forebet", "predictz"}

    def test_scenario_reset_then_merge_fresh(self, mm, tmp_path):
        """Pre-populate, reset, merge fresh data, verify only new data."""
        mm.add_match(make_match("Old", "Match"))
        mm.flush()
        mm.reset_matches_db()

        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "fresh.db",
            [make_match("Fresh", "Match", preds=[Score("s", 1, 0)])],
        )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 1
        assert buf.iloc[0]["home_team_name"] == "Fresh"

    def test_scenario_large_batch_merge(self, mm, tmp_path):
        """Merge a chunk with many matches to test performance/correctness."""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        matches = [
            make_match(
                f"Home_{i}",
                f"Away_{i}",
                dt=DT_BASE + timedelta(hours=i),
                preds=[Score("src", i % 5, (i + 1) % 5)],
            )
            for i in range(50)
        ]
        make_chunk_db(chunk_dir / "big.db", matches)
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        assert len(buf) == 50

    def test_scenario_fuzzy_merge_across_chunks(self, mm, tmp_path):
        """Two chunks with slightly different team name spellings should merge."""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db",
            [make_match("Manchester United", "Liverpool", preds=[Score("s1", 2, 0)])],
        )
        make_chunk_db(
            chunk_dir / "chunk2.db",
            [
                make_match(
                    "Manchester United FC", "Liverpool", preds=[Score("s2", 1, 1)]
                )
            ],
        )
        mm.merge_databases(str(chunk_dir))
        buf = mm.ensure_buffer()
        # Should be merged into 1 row due to fuzzy matching
        assert len(buf) == 1
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        sources = {p["source"] for p in preds}
        assert sources == {"s1", "s2"}
