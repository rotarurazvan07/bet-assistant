"""
bet_framework.core.types
────────────────────────
Project-wide type constants and enumerations.
"""

from enum import Enum


class MarketType(str, Enum):
    """Supported betting market categories."""
    RESULT = "result"
    OVER_UNDER_25 = "over_under_2.5"
    BTTS = "btts"


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
    BTTS_YES = "BTTS Yes"
    BTTS_NO = "BTTS No"
