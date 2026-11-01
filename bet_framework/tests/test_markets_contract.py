"""Contract freeze for the canonical market catalog.

Characterization tests: they pin the CURRENT market identity (persisted DB
field spellings), display labels, types and column keys before/after any
change. An accidental rename of a persisted key or label must fail here,
not reach a database.

Identity (``key``) is the persisted Odds/DB field spelling - exactly what
matches.db odds JSON and odds-* columns use. Display text lives in
``label``. The two were two layers until U1:
there is no translation layer anymore. ``crawler_field`` and
``lookup_key`` were deleted as tautologies - tests asserting them are
gone with them.
"""

import json
from pathlib import Path

import pytest

from bet_framework.markets.catalog import MARKET_BY_KEY, MARKET_CATALOG, MarketSpec
from bet_framework.markets.contract import emit
from bet_framework.markets.enums import MarketKey, MarketType
from bet_framework.markets.views import (
    CONSENSUS_COLUMN_NAMES,
    ODDS_COLUMN_NAMES,
)

# Frozen expectations (live-verified against catalog.py under U1, 2026-10-21).
EXPECTED_KEYS = [
    "home",
    "draw",
    "away",
    "over_25",
    "under_25",
    "btts_yes",
    "btts_no",
    "over_05",
    "under_05",
    "over_15",
    "under_15",
    "over_35",
    "under_35",
    "over_45",
    "under_45",
    "dc_1x",
    "dc_12",
    "dc_x2",
]
EXPECTED_LABELS = [
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
EXPECTED_CONS_KEYS = [key.upper().replace("_", "_") for key in []]  # placeholder replaced below
EXPECTED_CONS_KEYS = [f"cons_{key}" for key in EXPECTED_KEYS]
EXPECTED_ODDS_KEYS = [key.replace("cons_", "odds_") for key in EXPECTED_CONS_KEYS]
EXPECTED_ODDS_TO_STRIPPED = {f"odds_{key}": key for key in EXPECTED_KEYS}


def test_frozen_catalog_shape() -> None:
    """18 rows, 5-field MarketSpec (no crawler_field column)."""
    assert len(MARKET_CATALOG) == 18
    assert {spec.key for spec in MARKET_CATALOG} == set(EXPECTED_KEYS)
    assert all(len(spec) == 5 for spec in MARKET_CATALOG)


def test_frozen_values() -> None:
    assert [spec.key for spec in MARKET_CATALOG] == EXPECTED_KEYS
    assert [spec.label for spec in MARKET_CATALOG] == EXPECTED_LABELS
    assert [spec.cons_key for spec in MARKET_CATALOG] == EXPECTED_CONS_KEYS
    assert [spec.odds_key for spec in MARKET_CATALOG] == EXPECTED_ODDS_KEYS
    assert {spec.market_type for spec in MARKET_CATALOG} == set(EXPECTED_MARKET_TYPES)


def test_enum_values_match_catalog() -> None:
    assert {m.value for m in MarketType} == set(EXPECTED_MARKET_TYPES)
    # U1: MarketKey members ARE the persisted spellings (no label indirection).
    assert {m.value for m in MarketKey} == set(EXPECTED_KEYS)
    # MarketKey (StrEnum) and the catalog identities are the same strings.
    assert set(CONSENSUS_COLUMN_NAMES) == set(EXPECTED_CONS_KEYS)
    assert set(ODDS_COLUMN_NAMES) == set(EXPECTED_ODDS_KEYS)


def test_labels_stay_display_text() -> None:
    """U1 keeps MarketSpec.label as the presentation string."""
    assert MARKET_BY_KEY["home"].label == "1"
    assert MARKET_BY_KEY["btts_yes"].label == "BTTS Yes"
    assert MARKET_BY_KEY["over_25"].label == "Over 2.5"
    assert MARKET_BY_KEY["dc_1x"].label == "1X"


@pytest.mark.parametrize("odds_key_value", sorted(EXPECTED_ODDS_TO_STRIPPED))
def test_stripped_key_convention(odds_key_value: str) -> None:
    """Explicit frozen mapping - not a re-implementation of the function under test."""
    from bet_framework.markets.keys import stripped_key

    assert stripped_key(odds_key_value) == EXPECTED_ODDS_TO_STRIPPED[odds_key_value]


def test_snapshot_emitter_matches_catalog(tmp_path: Path) -> None:
    snapshot = emit(tmp_path / "snapshot.json")
    assert set(snapshot) == set(EXPECTED_KEYS)  # frontend identity == DB spellings
    for key, row in snapshot.items():
        assert row["label"] == MARKET_BY_KEY[key].label
        assert row["market_type"] in EXPECTED_MARKET_TYPES
        assert row["cons_key"] == f"cons_{key}"
        assert row["odds_key"] == f"odds_{key}"
        assert set(row) == {"label", "market_type", "cons_key", "odds_key"}
    written = json.loads(tmp_path.joinpath("snapshot.json").read_text(encoding="utf-8"))
    assert written == snapshot


def test_market_spec_shape() -> None:
    """MarketSpec is the canonical 5-field row; deleted columns stay gone."""
    spec = MARKET_BY_KEY["btts_yes"]
    assert isinstance(spec, MarketSpec)
    assert len(spec) == 5
    assert not hasattr(spec, "crawler_field")
    with pytest.raises(AttributeError):
        spec.crawler_field
