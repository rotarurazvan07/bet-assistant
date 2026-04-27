from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class Score:
    source: str
    home: float
    away: float

    def __post_init__(self) -> None:
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
    over_05: None = None
    under_05: None = None
    over_15: None = None
    under_15: None = None
    over_25: None = None
    under_25: None = None
    over_35: None = None
    under_35: None = None
    over_45: None = None
    under_45: None = None
    btts_y: None = None
    btts_n: None = None
    dc_1x: None = None
    dc_12: None = None
    dc_x2: None = None

    def __post_init__(self) -> None:
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
    def __init__(
        self,
        home_team: str,
        away_team: str,
        datetime: datetime,
        predictions: list[Score] | Score,
        odds: Odds,
        result_url: str | None = None,
    ) -> None:
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

    def to_dict(self):
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "datetime": self.datetime.isoformat() if isinstance(self.datetime, datetime) else self.datetime,
            "predictions": self.predictions,
            "odds": asdict(self.odds) if self.odds else None,
            "result_url": self.result_url if self.result_url else None,
        }