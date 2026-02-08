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

@dataclass
class Odds:
    home: float
    draw: float
    away: float
    over: float
    under: float
    btts_y: float
    btts_n: float

    def __post_init__(self):
        self.home = float(self.home) if self.home is not None else None
        self.draw = float(self.draw) if self.draw is not None else None
        self.away = float(self.away) if self.away is not None else None
        self.over = float(self.over) if self.over is not None else None
        self.under = float(self.under) if self.under is not None else None
        self.btts_y = float(self.btts_y) if self.btts_y is not None else None
        self.btts_n = float(self.btts_n) if self.btts_n is not None else None

class Match:
    def __init__(self, home_team: str, away_team: str, datetime: datetime, predictions: List[Score], odds: Odds):
        self.home_team = home_team
        self.away_team = away_team
        self.datetime = datetime
        self.predictions = predictions
        self.odds = odds

    def to_dict(self):
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "datetime": self.datetime.isoformat() if isinstance(self.datetime, datetime) else self.datetime,
            "predictions": self.predictions,
            "odds": asdict(self.odds) if self.odds else None,
        }