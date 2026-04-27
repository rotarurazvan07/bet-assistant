"""
bet_framework.core.types
────────────────────────
Project-wide type constants and enumerations.
"""

from enum import Enum


class MarketType(str, Enum):
    """Supported betting market categories."""

    RESULT = "result"
    OVER_UNDER_25 = "over_under_25"
    OVER_UNDER_15 = "over_under_15"
    OVER_UNDER_05 = "over_under_05"
    OVER_UNDER_35 = "over_under_35"
    OVER_UNDER_45 = "over_under_45"
    BTTS = "btts"
    DOUBLE_CHANCE = "double_chance"


class Outcome(str, Enum):
    """The settled state of a specific leg or slip."""

    WON = "Won"
    LOST = "Lost"
    LIVE = "Live"
    PENDING = "Pending"


class MatchStatus(str, Enum):
    """Parsing-level match states for live results (source domain)."""

    FT = "FT"
    FINISHED = "Finished"
    LIVE = "LIVE"
    PENDING = "PENDING"
    HT = "HT"


class MarketLabel(str, Enum):
    """Standardised display labels for market outcomes."""

    HOME = "1"
    DRAW = "X"
    AWAY = "2"
    OVER_25 = "Over 2.5"
    UNDER_25 = "Under 2.5"
    OVER_15 = "Over 1.5"
    UNDER_15 = "Under 1.5"
    OVER_05 = "Over 0.5"
    UNDER_05 = "Under 0.5"
    OVER_35 = "Over 3.5"
    UNDER_35 = "Under 3.5"
    OVER_45 = "Over 4.5"
    UNDER_45 = "Under 4.5"
    BTTS_YES = "BTTS Yes"
    BTTS_NO = "BTTS No"
    DC_1X = "1X"
    DC_12 = "12"
    DC_X2 = "X2"
