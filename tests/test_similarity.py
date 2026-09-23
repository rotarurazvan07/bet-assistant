"""
Gap tests for team fuzzy matching (GitHub issue #70).

The matching logic lives in scrape_kit.SimilarityEngine; MatchesManager
(bet_framework/MatchesManager.py) integrates it in _find for buffered dedup,
near-miss logging (combined score window [40, 65), home score gate >= 30),
best-candidate selection, and cross-chunk merging.

Covered behavior:
  SimilarityEngine (real config/similarity_config.yaml):
    - threshold 65, strong_mismatch_cap 35.0 loaded from config
    - strict score > threshold comparison
    - acronym stripping (FC / CF / AC prefixes and suffixes)
    - synonym mapping (man utd -> manchester united, spurs, wolves)
    - expansion-style acronym configs (fc -> football club, utd -> united)
    - strong-token enforcement caps disjoint discriminative pairs at 35
    - phonetic rescue for typos (sevilla vs sevlla)
    - diacritic stripping (Malmo vs Malmö)
    - order-independent result cache / symmetry
  MatchesManager._find integration (deterministic stub engine):
    - near-miss recording windows and boundaries
    - home-fail vs away-fail near-miss branches
    - exact match beats fuzzy, best-average fuzzy selection
    - +/- 1 day date window
  Dedup scenarios (real config):
    - add_match merges fuzzy variants of the same fixture
    - no engine -> exact-only matching
    - merge_databases dedups fuzzy variants across chunks
    - disjoint strong tokens never merge across chunks

Note: merge_databases clears the near-miss buffer internally, so near-miss
assertions target _find / add_match directly.
"""

import contextlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from scrape_kit import SimilarityEngine

from bet_framework.core.Match import Match, Score
from bet_framework.MatchesManager import MatchesManager

# -- Constants & helpers -----------------------------------------------------------

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "similarity_config.yaml"

DT_BASE = datetime(2026, 4, 1, 15, 0, 0)

TEAM_POOL = [
    "Manchester United",
    "Manchester City",
    "Arsenal",
    "Chelsea",
    "Liverpool",
    "Tottenham Hotspur",
    "Real Madrid",
    "Barcelona",
    "Valencia",
    "Sevilla",
    "AC Milan",
    "Malmo FF",
    "Dinamo Zagreb",
    "Wolverhampton Wanderers",
]


class StubEngine:
    """Deterministic SimilarityEngine stand-in driven by a scoring function."""

    def __init__(self, score_fn):
        self.score_fn = score_fn
        self.calls = []

    def is_similar(self, a, b):
        self.calls.append((a, b))
        return self.score_fn(a, b)


def make_match(home, away, dt=None, preds=None):
    return Match(
        home_team=home,
        away_team=away,
        datetime=dt or DT_BASE,
        predictions=preds or [],
        odds=None,
        result_url="https://example.com/match/1",
    )


def make_chunk_db(path, matches):
    """Create a standalone chunk .db file compatible with MatchesManager merge."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_name     TEXT NOT NULL,
            away_team_name     TEXT NOT NULL,
            datetime           TEXT NOT NULL,
            predictions_scores TEXT,
            odds               TEXT,
            result_url         TEXT,
            league             TEXT
        )
    """
    )
    for m in matches:
        preds_json = (
            json.dumps([s.__dict__ for s in m.predictions]) if m.predictions else None
        )
        conn.execute(
            "INSERT INTO matches (home_team_name, away_team_name, datetime, predictions_scores, odds, result_url, league)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                m.home_team,
                m.away_team,
                m.datetime.isoformat(),
                preds_json,
                None,
                m.result_url,
                None,
            ),
        )
    conn.commit()
    conn.close()


# -- Fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="session")
def real_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="session")
def real_engine(real_config):
    return SimilarityEngine(real_config)


@pytest.fixture
def mm_real(tmp_path, real_config):
    manager = MatchesManager(str(tmp_path / "sim.db"), similarity_config=real_config)
    yield manager
    with contextlib.suppress(Exception):
        manager.close()


@pytest.fixture
def mm_stub(tmp_path):
    """MatchesManager without an engine; tests assign a StubEngine explicitly."""
    manager = MatchesManager(str(tmp_path / "stub.db"), similarity_config=None)
    yield manager
    with contextlib.suppress(Exception):
        manager.close()


# -- SimilarityEngine: configuration ----------------------------------------------------


class TestEngineConfiguration:
    def test_real_config_threshold_and_cap(self, real_config, real_engine):
        assert real_config["threshold"] == 65
        assert real_config["weights"]["strong_mismatch_cap"] == 35.0
        assert real_engine.similarity_threshold == 65.0
        assert real_engine.strong_mismatch_cap == 35.0

    def test_default_threshold_is_65(self):
        engine = SimilarityEngine({"acronyms": {}})
        assert engine.similarity_threshold == 65.0
        assert engine.strong_mismatch_cap == 35.0

    def test_empty_config_raises_value_error(self):
        with pytest.raises(ValueError, match="Configuration is required"):
            SimilarityEngine({})

    def test_threshold_comparison_is_strictly_greater(self, real_config):
        # A pair scoring exactly at the threshold must NOT count as similar.
        engine = SimilarityEngine(real_config)  # fresh instance: no cached results
        _ok, score = engine.is_similar("Liverpool FC", "Liverpool")
        assert score == 90.0
        engine.similarity_threshold = score
        ok, score2 = engine.is_similar("Manchester United", "Man Utd")
        assert score2 == 90.0
        assert ok is False


# -- SimilarityEngine: acronym stripping and synonyms ----------------------------------


class TestAcronymsAndSynonyms:
    def test_fc_prefix_is_stripped(self, real_engine):
        ok, _score = real_engine.is_similar("FC Arsenal", "Arsenal")
        assert ok is True

    def test_fc_suffix_is_stripped(self, real_engine):
        ok, _score = real_engine.is_similar("Liverpool FC", "Liverpool")
        assert ok is True

    def test_cf_suffix_is_stripped(self, real_engine):
        ok, _score = real_engine.is_similar("Barcelona CF", "Barcelona")
        assert ok is True

    def test_ac_prefix_is_stripped(self, real_engine):
        ok, _score = real_engine.is_similar("AC Milan", "Milan")
        assert ok is True

    def test_dotted_acronym_is_expanded(self, real_engine):
        # "din." -> "dinamo" per the diacritic/acronym table.
        ok, _score = real_engine.is_similar("Din. Zagreb", "Dinamo Zagreb")
        assert ok is True

    def test_synonym_man_utd_expands_to_manchester_united(self, real_engine):
        ok, score = real_engine.is_similar("Man Utd", "Manchester United")
        assert ok is True
        assert score == pytest.approx(90.0)

    def test_synonym_spurs_expands_to_tottenham(self, real_engine):
        ok, score = real_engine.is_similar("Spurs", "Tottenham Hotspur")
        assert ok is True
        assert score == pytest.approx(90.0)

    def test_synonym_wolves_expands_to_wolverhampton(self, real_engine):
        ok, score = real_engine.is_similar("Wolves", "Wolverhampton Wanderers")
        assert ok is True
        assert score == pytest.approx(90.0)

    def test_expansion_style_acronyms(self):
        # Issue #70 names fc -> "football club" and utd -> "united" expansions.
        # The shipped config strips them instead; both semantics must work.
        cfg = {
            "acronyms": {"fc": "football club", "utd": "united"},
            "synonyms": {},
            "weak_tokens": [],
            "weights": {
                "token": 0.5,
                "substr": 0.1,
                "phonetic": 0.1,
                "ratio": 0.3,
                "partial": 0.0,
                "strong_mismatch_cap": 35.0,
            },
            "threshold": 65,
        }
        engine = SimilarityEngine(cfg)
        ok, _score = engine.is_similar("FC Arsenal", "Arsenal Football Club")
        assert ok is True
        ok, _score = engine.is_similar("Man Utd", "Manchester United")
        assert ok is True


# -- SimilarityEngine: strong-token enforcement ----------------------------------------


class TestStrongTokenEnforcement:
    def test_manchester_city_vs_united_capped(self, real_engine):
        # strong = {city} vs {united}: disjoint -> capped below threshold.
        ok, score = real_engine.is_similar("Manchester City", "Manchester United")
        assert ok is False
        assert score <= 35.0

    def test_shared_weak_location_words_do_not_merge(self, real_engine):
        ok, score = real_engine.is_similar("New York City", "New York Bulls")
        assert ok is False
        assert score <= 35.0

    def test_single_word_clubs_never_merge(self, real_engine):
        ok, score = real_engine.is_similar("Barcelona", "Valencia")
        assert ok is False
        assert score <= 35.0

    def test_weak_real_prefix_does_not_rescue_mismatch(self, real_engine):
        # "real" is a weak token; madrid vs sociedad are disjoint strong tokens.
        ok, score = real_engine.is_similar("Real Madrid", "Real Sociedad")
        assert ok is False
        assert score <= 35.0

    def test_cap_is_min_of_base_and_cap(self, real_engine):
        # Cap behaves as a ceiling: score = min(base_score, 35.0).
        _ok1, capped = real_engine.is_similar("Manchester City", "Manchester United")
        _ok2, lower = real_engine.is_similar("Real Madrid", "Real Betis")
        assert capped == pytest.approx(35.0)
        assert lower <= 35.0

    def test_disjoint_teams_score_below_threshold(self, real_engine):
        ok, _score = real_engine.is_similar("Totally Different", "Completely Other")
        assert ok is False


# -- SimilarityEngine: normalization resilience -----------------------------------------


class TestNormalization:
    def test_diacritics_are_stripped(self, real_engine):
        ok, score = real_engine.is_similar("Malmo FF", "Malmö FF")
        assert ok is True
        assert score == pytest.approx(99.2)

    def test_typo_rescued_phonetically(self, real_engine):
        ok, score = real_engine.is_similar("Sevilla", "Sevlla")
        assert ok is True
        assert score > 65.0

    def test_empty_strings_never_match(self, real_engine):
        ok, score = real_engine.is_similar("", "")
        assert ok is False
        assert score == 0.0

    def test_identity_is_similar_for_pool_teams(self, real_engine):
        for name in TEAM_POOL:
            ok, _score = real_engine.is_similar(name, name)
            assert ok is True, name


# -- SimilarityEngine: properties (hypothesis) ------------------------------------------


class TestEngineProperties:
    @settings(deadline=None)
    @given(a=st.sampled_from(TEAM_POOL), b=st.sampled_from(TEAM_POOL))
    def test_property_symmetry(self, real_engine, a, b):
        forward = real_engine.is_similar(a, b)
        backward = real_engine.is_similar(b, a)
        assert forward[0] == backward[0]
        assert forward[1] == pytest.approx(backward[1])

    @settings(deadline=None)
    @given(a=st.sampled_from(TEAM_POOL), b=st.sampled_from(TEAM_POOL))
    def test_property_score_range_and_threshold_consistency(self, real_engine, a, b):
        ok, score = real_engine.is_similar(a, b)
        assert 0.0 <= score <= 100.0
        assert ok == (score > real_engine.similarity_threshold)

    @settings(deadline=None)
    @given(a=st.sampled_from(TEAM_POOL))
    def test_property_names_from_config_pool_match_themselves(self, real_engine, a):
        ok, score = real_engine.is_similar(a, a)
        assert ok is True
        assert score > 65.0


# -- MatchesManager._find: near-miss windows (stub engine) -------------------------------


class TestFindNearMisses:
    def test_home_fail_mid_window_records_near_miss(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(lambda a, b: (False, 50.0))
        found, idx = mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert found is None and idx is None
        assert len(mm_stub._near_misses) == 1
        near = mm_stub._near_misses[0]
        assert near.home_a == "QueryHome"
        assert near.away_a == "QueryAway"
        assert near.home_b == "RowHome"
        assert near.away_b == "RowAway"
        assert near.score == pytest.approx(50.0)

    def test_home_fail_below_30_skips_near_miss_check(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(lambda a, b: (False, 29.9))
        found, _idx = mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert found is None
        assert mm_stub._near_misses == []

    def test_home_score_exactly_30_enters_window_check(self, mm_stub):
        # sc_h = 30 (>= 30 gate), sc_a = 50 -> combined 40 -> recorded (>= 40).
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(
            lambda a, b: (False, 30.0) if b == "QueryHome" else (False, 50.0)
        )
        mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert len(mm_stub._near_misses) == 1
        assert mm_stub._near_misses[0].score == pytest.approx(40.0)

    def test_combined_below_40_not_recorded(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(
            lambda a, b: (False, 30.0) if b == "QueryHome" else (False, 49.0)
        )
        mm_stub._find("QueryHome", "QueryAway", DT_BASE)  # combined 39.5
        assert mm_stub._near_misses == []

    def test_combined_exactly_65_not_recorded(self, mm_stub):
        # Window is [40, 65): the upper bound is exclusive.
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(
            lambda a, b: (False, 50.0) if b == "QueryHome" else (False, 80.0)
        )
        mm_stub._find("QueryHome", "QueryAway", DT_BASE)  # combined 65.0
        assert mm_stub._near_misses == []

    def test_combined_just_below_65_recorded(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))
        mm_stub.similarity_engine = StubEngine(
            lambda a, b: (False, 50.0) if b == "QueryHome" else (False, 79.8)
        )
        mm_stub._find("QueryHome", "QueryAway", DT_BASE)  # combined 64.9
        assert len(mm_stub._near_misses) == 1

    def test_away_fail_records_near_miss(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))

        def score(a, b):
            if b == "QueryHome":
                return (True, 80.0)
            return (False, 49.0)  # away fails; combined (80+49)/2 = 64.5

        mm_stub.similarity_engine = StubEngine(score)
        found, _idx = mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert found is None
        assert len(mm_stub._near_misses) == 1
        assert mm_stub._near_misses[0].score == pytest.approx(64.5)

    def test_away_fail_above_window_not_recorded(self, mm_stub):
        mm_stub.add_match(make_match("RowHome", "RowAway"))

        def score(a, b):
            if b == "QueryHome":
                return (True, 80.0)
            return (False, 50.0)  # combined 65.0 -> outside [40, 65)

        mm_stub.similarity_engine = StubEngine(score)
        mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert mm_stub._near_misses == []


# -- MatchesManager._find: selection semantics (stub engine) -----------------------------


class TestFindSelection:
    def test_exact_match_wins_over_fuzzy(self, mm_stub):
        mm_stub.add_match(make_match("FuzzyHome", "FuzzyAway"))
        mm_stub.add_match(make_match("ExactHome", "ExactAway"))
        mm_stub.similarity_engine = StubEngine(lambda a, b: (True, 95.0))
        found, idx = mm_stub._find("ExactHome", "ExactAway", DT_BASE)
        assert found is not None
        assert found["home_team_name"] == "ExactHome"
        assert idx == 1

    def test_exact_match_short_circuits_before_fuzzy_rows(self, mm_stub):
        mm_stub.add_match(make_match("ExactHome", "ExactAway"))
        mm_stub.add_match(make_match("FuzzyHome", "FuzzyAway"))
        mm_stub.similarity_engine = StubEngine(lambda a, b: (True, 95.0))
        found, idx = mm_stub._find("ExactHome", "ExactAway", DT_BASE)
        assert found["home_team_name"] == "ExactHome"
        assert idx == 0
        # Engine never consulted: exact match short-circuits the loop.
        assert mm_stub.similarity_engine.calls == []

    def test_highest_average_fuzzy_score_wins(self, mm_stub):
        mm_stub.add_match(make_match("WeakHome", "WeakAway"))
        mm_stub.add_match(make_match("BestHome", "BestAway"))

        def score(a, b):
            return (True, 70.0) if a == "WeakHome" else (True, 85.0)

        mm_stub.similarity_engine = StubEngine(score)
        found, idx = mm_stub._find("QueryHome", "QueryAway", DT_BASE)
        assert found["home_team_name"] == "BestHome"
        assert idx == 1

    def test_no_engine_means_exact_matching_only(self, mm_stub):
        mm_stub.add_match(make_match("Manchester United", "Chelsea"))
        found, _idx = mm_stub._find("Manchester United", "Chelsea", DT_BASE)
        assert found is not None  # exact still works
        missing, _idx2 = mm_stub._find("Man Utd", "Chelsea", DT_BASE)
        assert missing is None  # fuzzy variants are NOT found without an engine
        assert mm_stub._near_misses == []  # near-miss logic requires the engine

    def test_date_window_is_plus_minus_one_day(self, mm_stub):
        mm_stub.add_match(make_match("SameHome", "SameAway"))
        mm_stub.similarity_engine = StubEngine(lambda a, b: (True, 90.0))
        # Same day and +/- 1 day are inside the window.
        for delta in (timedelta(days=0), timedelta(days=1), timedelta(days=-1)):
            found, _idx = mm_stub._find("SameHome", "SameAway", DT_BASE + delta)
            assert found is not None, delta
        # +/- 2 days fall outside the window.
        for delta in (timedelta(days=2), timedelta(days=-2)):
            found, _idx = mm_stub._find("SameHome", "SameAway", DT_BASE + delta)
            assert found is None, delta


# -- Dedup scenarios (real config) -------------------------------------------------------


class TestDedupScenarios:
    def test_add_match_merges_fuzzy_variants(self, mm_real):
        mm_real.add_match(
            make_match("Manchester United", "Chelsea", preds=[Score("src_a", 2, 1)])
        )
        mm_real.add_match(
            make_match("Man Utd", "Chelsea", preds=[Score("src_b", 1, 0)])
        )
        buf = mm_real.ensure_buffer()
        assert len(buf) == 1  # merged into a single row
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        assert len(preds) == 2

    def test_add_match_keeps_disjoint_strong_tokens_separate(self, mm_real):
        mm_real.add_match(make_match("Manchester United", "Chelsea"))
        mm_real.add_match(make_match("Manchester City", "Chelsea"))
        buf = mm_real.ensure_buffer()
        assert len(buf) == 2  # city vs united: capped at 35, never merged

    def test_cross_chunk_merge_dedups_fuzzy_variants(self, mm_real, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db",
            [make_match("Manchester United", "Chelsea", preds=[Score("src_a", 2, 1)])],
        )
        make_chunk_db(
            chunk_dir / "chunk2.db",
            [make_match("Man Utd", "Chelsea", preds=[Score("src_b", 1, 0)])],
        )
        mm_real.merge_databases(str(chunk_dir))
        buf = mm_real.ensure_buffer()
        assert len(buf) == 1
        preds = json.loads(buf.iloc[0]["predictions_scores"])
        assert len(preds) == 2

    def test_cross_chunk_merge_keeps_different_clubs_separate(self, mm_real, tmp_path):
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(chunk_dir / "chunk1.db", [make_match("Barcelona", "Valencia")])
        make_chunk_db(chunk_dir / "chunk2.db", [make_match("Real Madrid", "Sevilla")])
        mm_real.merge_databases(str(chunk_dir))
        buf = mm_real.ensure_buffer()
        assert len(buf) == 2

    def test_cross_chunk_merge_never_merges_capped_variants(self, mm_real, tmp_path):
        # Manchester City chunk must NOT fold into a Manchester United row.
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        make_chunk_db(
            chunk_dir / "chunk1.db", [make_match("Manchester United", "Chelsea")]
        )
        make_chunk_db(
            chunk_dir / "chunk2.db", [make_match("Manchester City", "Chelsea")]
        )
        mm_real.merge_databases(str(chunk_dir))
        buf = mm_real.ensure_buffer()
        assert len(buf) == 2
