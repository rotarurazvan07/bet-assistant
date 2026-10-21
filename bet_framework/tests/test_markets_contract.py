"""Contract freeze for the canonical market catalog (AC-01).

Characterization tests: they pin the CURRENT market key/label/type/column values
before the canonical ``bet_framework/markets/`` module takes over. An accidental
value change (rename of a persisted key) must fail here, not reach a database.
"""

import json
from pathlib import Path

import pytest

from bet_framework.core.market_config import (
    CONSENSUS_COLUMNS,
    MARKET_DEFINITIONS,
    ODDS_COLUMNS,
)
from bet_framework.core.type_defs import MarketLabel, MarketType
from bet_framework.markets.contract import emit

# Frozen expectations (live-verified 2026-10-20 against market_config.py).
EXPECTED_MARKET_LABELS = [
    "1",
    "X",
    "2",
    "Over 2.5",
    "Under 2.5",
    "BTTS Yes",
    "BTTS No",
    "Over 0.5",
    "Under 0.5",
    "Over 1.5",
    "Under 1.5",
    "Over 3.5",
    "Under 3.5",
    "Over 4.5",
    "Under 4.5",
    "1X",
    "12",
    "X2",
]
EXPECTED_MARKET_TYPES = [
    "result",
    "over_under_25",
    "over_under_15",
    "over_under_05",
    "over_under_35",
    "over_under_45",
    "btts",
    "double_chance",
]
EXPECTED_CONS_KEYS = [
    "cons_home",
    "cons_draw",
    "cons_away",
    "cons_over_25",
    "cons_under_25",
    "cons_btts_yes",
    "cons_btts_no",
    "cons_over_05",
    "cons_under_05",
    "cons_over_15",
    "cons_under_15",
    "cons_over_35",
    "cons_under_35",
    "cons_over_45",
    "cons_under_45",
    "cons_dc_1x",
    "cons_dc_12",
    "cons_dc_x2",
]
EXPECTED_ODDS_KEYS = [key.replace("cons_", "odds_") for key in EXPECTED_CONS_KEYS]


def test_market_definitions_frozen_values() -> None:
    assert [d.market for d in MARKET_DEFINITIONS] == EXPECTED_MARKET_LABELS
    assert [d.cons_key for d in MARKET_DEFINITIONS] == EXPECTED_CONS_KEYS
    assert [d.odds_key for d in MARKET_DEFINITIONS] == EXPECTED_ODDS_KEYS
    assert [d.market_type for d in MARKET_DEFINITIONS] == [
        "result",
        "result",
        "result",
        "over_under_25",
        "over_under_25",
        "btts",
        "btts",
        "over_under_05",
        "over_under_05",
        "over_under_15",
        "over_under_15",
        "over_under_35",
        "over_under_35",
        "over_under_45",
        "over_under_45",
        "double_chance",
        "double_chance",
        "double_chance",
    ]


def test_enum_values_match_definitions() -> None:
    assert {m.value for m in MarketType} == set(EXPECTED_MARKET_TYPES)
    assert {m.value for m in MarketLabel} == set(EXPECTED_MARKET_LABELS)
    assert set(CONSENSUS_COLUMNS) == set(EXPECTED_CONS_KEYS)
    assert set(ODDS_COLUMNS) == set(EXPECTED_ODDS_KEYS)


def test_snapshot_emitter_matches_definitions(tmp_path: Path) -> None:
    snapshot = emit(tmp_path / "snapshot.json")
    labels = set(EXPECTED_MARKET_LABELS)
    assert set(snapshot) == labels
    for market, row in snapshot.items():
        assert row["label"] == market
        assert row["market_type"] in EXPECTED_MARKET_TYPES
        assert row["cons_key"].startswith("cons_")
        assert row["odds_key"].startswith("odds_")
    written = json.loads(tmp_path.joinpath("snapshot.json").read_text(encoding="utf-8"))
    assert written == snapshot


EXPECTED_ODDS_TO_STRIPPED = {
    "odds_home": "home",
    "odds_draw": "draw",
    "odds_away": "away",
    "odds_over_25": "over_25",
    "odds_under_25": "under_25",
    "odds_over_05": "over_05",
    "odds_under_05": "under_05",
    "odds_over_15": "over_15",
    "odds_under_15": "under_15",
    "odds_over_35": "over_35",
    "odds_under_35": "under_35",
    "odds_over_45": "over_45",
    "odds_under_45": "under_45",
    "odds_btts_yes": "btts_yes",
    "odds_btts_no": "btts_no",
    "odds_dc_1x": "dc_1x",
    "odds_dc_12": "dc_12",
    "odds_dc_x2": "dc_x2",
}


@pytest.mark.parametrize("odds_key_value", sorted(EXPECTED_ODDS_TO_STRIPPED))
def test_stripped_key_convention(odds_key_value: str) -> None:
    """Explicit frozen mapping - not a re-implementation of the function under test."""
    from bet_framework.markets.keys import stripped_key

    assert stripped_key(odds_key_value) == EXPECTED_ODDS_TO_STRIPPED[odds_key_value]


def test_lookup_key_translates_history_field_names() -> None:
    """Movement lookups hit Odds-dataclass fields ('btts_yes'), not stripped keys."""
    from bet_framework.markets.keys import lookup_key

    assert lookup_key("btts_yes") == "btts_yes"
    assert lookup_key("btts_no") == "btts_no"
    assert lookup_key("over_25") == "over_25"
    with pytest.raises(KeyError):
        lookup_key("not_a_market")


def test_crawler_field_mapping_frozen() -> None:
    """AC-08: the canonical <-> Odds-dataclass field map is frozen.

    The BTTS Odds-dataclass fields (renamed by PR #110 to 'btts_yes'/'btts_no')
    vs their stripped odds keys ('btts_yes') is the exact PR #106 divergence
    class - the map that joins them now lives in exactly one file.
    """
    from bet_framework.markets.catalog import MARKET_BY_CRAWLER_FIELD, MARKET_CATALOG

    crawler_fields = {spec.crawler_field for spec in MARKET_CATALOG}
    assert crawler_fields == {
        "home",
        "draw",
        "away",
        "over_05",
        "under_05",
        "over_15",
        "under_15",
        "over_25",
        "under_25",
        "over_35",
        "under_35",
        "over_45",
        "under_45",
        "btts_yes",
        "btts_no",
        "dc_1x",
        "dc_12",
        "dc_x2",
    }
    # The do-or-die row: crawler map binds persisted key -> Odds dataclass field.
    assert MARKET_BY_CRAWLER_FIELD["btts_yes"].key == "BTTS Yes"
    assert MARKET_BY_CRAWLER_FIELD["btts_yes"].odds_key.removeprefix("odds_") == "btts_yes"
    assert MARKET_BY_CRAWLER_FIELD["btts_no"].key == "BTTS No"


def test_snapshot_excludes_crawler_field(tmp_path: Path) -> None:
    """Snapshot shape stays {label, market_type, cons_key, odds_key} (frontend contract)."""
    snapshot = emit(tmp_path / "snapshot.json")
    for row in snapshot.values():
        assert set(row) == {"label", "market_type", "cons_key", "odds_key"}
