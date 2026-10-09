"""Core match dataclasses: Score, Odds, Match."""

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class Score:
    """One source's predicted score for a match."""

    source: str
    home: float
    away: float

    def __post_init__(self) -> None:
        """Coerce score values to floats after construction."""
        self.source = str(self.source) if self.source is not None else None
        self.home = float(self.home) if self.home is not None else None
        self.away = float(self.away) if self.away is not None else None


def ensure_decimal_odds(odds_value) -> float | None:
    """
    Detects if odds are American or Decimal and returns Decimal (European).
    Handles strings, integers, and floats.

    Examples:
        "+120" -> 2.20
        "-110" -> 1.91
        "1.91" -> 1.91
        "2.20" -> 2.20
        120 -> 2.20
        -110 -> 1.91
        1.91 -> 1.91
    """
    try:
        # Convert to string and clean
        if odds_value is None:
            return None

        # Handle if it's already a number
        if isinstance(odds_value, (int, float)):
            val = float(odds_value)
        else:
            # Clean the string
            cleaned = str(odds_value).strip().replace(",", ".")
            # Remove any non-numeric characters except +, -, and .
            cleaned = "".join(c for c in cleaned if c.isdigit() or c in "+-.")
            val = float(cleaned)

        # Check if it's American odds (absolute value >= 100 and not between 0 and 3 typically)
        # American odds are usually 3-digit numbers like 110, -150, +200, etc.
        if abs(val) >= 100 and (abs(val) < 10 or abs(val) > 3):
            if val > 0:  # Positive American odds
                return round((val / 100) + 1, 2)
            else:  # Negative American odds
                return round((100 / abs(val)) + 1, 2)
        else:
            # Already decimal odds
            return round(val, 2)

    except ValueError, TypeError, AttributeError:
        return None


@dataclass
class Odds:
    # Optional decimal odds per market — None when the source doesn't
    # provide it (was mis-annotated as literal None type; ensure_decimal_odds
    # returns float | None and __post_init__ stores it back).
    """1X2 odds for a match (any leg may be None)."""

    home: float | None = None
    draw: float | None = None
    away: float | None = None
    over_05: float | None = None
    under_05: float | None = None
    over_15: float | None = None
    under_15: float | None = None
    over_25: float | None = None
    under_25: float | None = None
    over_35: float | None = None
    under_35: float | None = None
    over_45: float | None = None
    under_45: float | None = None
    btts_y: float | None = None
    btts_n: float | None = None
    dc_1x: float | None = None
    dc_12: float | None = None
    dc_x2: float | None = None

    def __post_init__(self) -> None:
        """Coerce odds values to floats where present."""
        self.home = ensure_decimal_odds(self.home)
        self.draw = ensure_decimal_odds(self.draw)
        self.away = ensure_decimal_odds(self.away)
        self.over_05 = ensure_decimal_odds(self.over_05)
        self.under_05 = ensure_decimal_odds(self.under_05)
        self.over_15 = ensure_decimal_odds(self.over_15)
        self.under_15 = ensure_decimal_odds(self.under_15)
        self.over_25 = ensure_decimal_odds(self.over_25)
        self.under_25 = ensure_decimal_odds(self.under_25)
        self.over_35 = ensure_decimal_odds(self.over_35)
        self.under_35 = ensure_decimal_odds(self.under_35)
        self.over_45 = ensure_decimal_odds(self.over_45)
        self.under_45 = ensure_decimal_odds(self.under_45)
        self.btts_y = ensure_decimal_odds(self.btts_y)
        self.btts_n = ensure_decimal_odds(self.btts_n)
        self.dc_1x = ensure_decimal_odds(self.dc_1x)
        self.dc_12 = ensure_decimal_odds(self.dc_12)
        self.dc_x2 = ensure_decimal_odds(self.dc_x2)


class Match:
    """One match with predictions, odds and provenance."""

    def __init__(
        self,
        home_team: str,
        away_team: str,
        datetime: datetime,
        # Runtime callers pass None / a single Score / a list — the branch
        # below normalizes all three (widened type kills the dead-check error).
        predictions: list[Score] | Score | None,
        odds: Odds,
        result_url: str | None = None,
        league: str | None = None,
    ) -> None:
        """Build a match, storing source predictions and odds."""
        self.home_team = home_team
        self.away_team = away_team
        self.datetime = datetime
        if predictions is None:
            self.predictions = []
        elif isinstance(predictions, list):
            self.predictions = predictions
        else:
            self.predictions = [predictions]
        self.odds = odds
        self.result_url = result_url
        self.league = league

    def to_dict(self):
        """Serialize the match to a plain dict."""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "datetime": self.datetime.isoformat() if isinstance(self.datetime, datetime) else self.datetime,
            "predictions": self.predictions,
            "odds": asdict(self.odds) if self.odds else None,
            "result_url": self.result_url if self.result_url else None,
            "league": self.league,
        }
