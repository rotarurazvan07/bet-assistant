from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

@dataclass
class Score:
    source: str
    home: float
    away: float

    def __post_init__(self):
        self.source = str(self.source) if self.source is not None else None
        self.home = float(self.home) if self.home is not None else None
        self.away = float(self.away) if self.away is not None else None

def ensure_decimal_odds(odds_value) -> float:
    """
    Detects if odds are American or Decimal and returns Decimal (European).
    Handles strings, integers, and floats.
    """
    try:
        val = float(odds_value)
        if abs(val) >= 100:
            if val > 0:
                return round((val / 100) + 1, 2)
            else:
                return round((100 / abs(val)) + 1, 2)
        return round(val, 2)

    except (ValueError, TypeError):
        return None

@dataclass
class Odds:
    home: None = None
    draw: None = None
    away: None = None
    over: None = None
    under: None = None
    btts_y: None = None
    btts_n: None = None

    def __post_init__(self):
        self.home = ensure_decimal_odds(self.home)
        self.draw = ensure_decimal_odds(self.draw)
        self.away = ensure_decimal_odds(self.away)
        self.over = ensure_decimal_odds(self.over)
        self.under = ensure_decimal_odds(self.under)
        self.btts_y = ensure_decimal_odds(self.btts_y)
        self.btts_n = ensure_decimal_odds(self.btts_n)

class Match:
    def __init__(self, home_team: str, away_team: str, datetime: datetime, predictions: List[Score], odds: Odds, result_url: str | None = None):
        self.home_team = home_team
        self.away_team = away_team
        self.datetime = datetime
        self.predictions = predictions
        self.odds = odds
        self.result_url = result_url

    def to_dict(self):
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "datetime": self.datetime.isoformat() if isinstance(self.datetime, datetime) else self.datetime,
            "predictions": self.predictions,
            "odds": asdict(self.odds) if self.odds else None,
            "result_url": self.result_url if self.result_url else None
        }