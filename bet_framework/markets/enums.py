"""Canonical market enums (AC-02).

Values are FROZEN: byte-identical to the persisted wire format (matches.db
column names, slips.db labels, odds-history JSON keys, frontend localStorage).
``StrEnum`` keeps strings and members interchangeable, which existing tests
already rely on (test_outcomes: determine_outcome(2, 1, "1", "result")).
"""

from enum import StrEnum


class MarketType(StrEnum):
    """Supported betting market categories (routing keys for dispatch)."""

    RESULT = "result"
    OVER_UNDER_25 = "over_under_25"
    OVER_UNDER_15 = "over_under_15"
    OVER_UNDER_05 = "over_under_05"
    OVER_UNDER_35 = "over_under_35"
    OVER_UNDER_45 = "over_under_45"
    BTTS = "btts"
    DOUBLE_CHANCE = "double_chance"


class MarketKey(StrEnum):
    """Persisted market identity: the persisted DB/Odds field spellings.

    Values are IDENTICAL to the Odds dataclass fields / odds-* stripped keys
    ('home', 'over_25', 'btts_yes', 'dc_1x', ...): no translation layer exists
    between the canonical identity and the persisted format. Display text
    lives in MarketSpec.label, never here.
    """

    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    OVER_25 = "over_25"
    UNDER_25 = "under_25"
    BTTS_YES = "btts_yes"
    BTTS_NO = "btts_no"
    OVER_05 = "over_05"
    UNDER_05 = "under_05"
    OVER_15 = "over_15"
    UNDER_15 = "under_15"
    OVER_35 = "over_35"
    UNDER_35 = "under_35"
    OVER_45 = "over_45"
    UNDER_45 = "under_45"
    DC_1X = "dc_1x"
    DC_12 = "dc_12"
    DC_X2 = "dc_x2"


class Outcome(StrEnum):
    """The settled state of a specific leg or slip."""

    WON = "Won"
    LOST = "Lost"
    LIVE = "Live"
    PENDING = "Pending"


class MatchStatus(StrEnum):
    """Parsing-level match states for live results (source domain)."""

    FT = "FT"
    FINISHED = "Finished"
    LIVE = "LIVE"
    PENDING = "PENDING"
    HT = "HT"
