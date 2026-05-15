import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

FOOTBALLPREDICTIONS_URL = "https://footballpredictions.net/"
FOOTBALLPREDICTIONS_NAME = "footballpredictions"

TOP_LEAGUES = [
    "https://footballpredictions.net/champions-league-predictions",
    "https://footballpredictions.net/europa-league-predictions",
    "https://footballpredictions.net/conference-league-predictions",
    "https://footballpredictions.net/premier-league-predictions",
    "https://footballpredictions.net/serie-a-predictions",
    "https://footballpredictions.net/la-liga-predictions",
    "https://footballpredictions.net/bundesliga-predictions",
    "https://footballpredictions.net/ligue-1-predictions",
    "https://footballpredictions.net/eredivisie-predictions",
    "https://footballpredictions.net/primeira-liga-predictions",
    "https://footballpredictions.net/championship-predictions",
    "https://footballpredictions.net/serie-b-predictions",
    "https://footballpredictions.net/segunda-division-predictions",
    "https://footballpredictions.net/2-bundesliga-predictions",
    "https://footballpredictions.net/ligue-2-predictions",
    "https://footballpredictions.net/scottish-premiership-predictions",
    "https://footballpredictions.net/mls-predictions",
    "https://footballpredictions.net/super-lig-predictions",
    "https://footballpredictions.net/jupiler-pro-league-predictions",
]


class FootballPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return league URLs directly."""
        return TOP_LEAGUES

    def get_match_urls(self) -> list[str]:
        """Return league URLs for scraping."""
        return TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse match predictions from table.table-tips."""
        try:
            rows = page.select("table.table-tips tbody tr")
            if not rows:
                rows = page.select("table.table-tips tr")
            if not rows:
                logger.debug(f"No tips table on {url}")
                return
            for row in rows:
                try:
                    # Team names from span.table-tips__team-wrapper
                    team_spans = row.select("span.table-tips__team-wrapper")
                    if len(team_spans) < 2:
                        continue
                    home_team = team_spans[0].text().strip()
                    away_team = team_spans[1].text().strip()
                    # Date from data-datetime attribute
                    date_el = row.find("span.table-tips__date-time-wrapper")
                    if date_el:
                        date_attr = date_el.attr("data-datetime")
                        if date_attr:
                            match_date = self.parse_date_robust(date_attr)
                        else:
                            match_date = self.parse_date_robust(date_el.text().strip())
                    else:
                        match_date = None
                    if not match_date:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    # Correct Score prediction from li containing "Correct Score:"
                    score_li = row.find_by_text("li", "Correct Score:")
                    if not score_li:
                        continue
                    score_text = score_li.text().strip()
                    # Extract numbers after "Correct Score:"
                    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
                    if not m:
                        continue
                    home_score = float(m.group(1))
                    away_score = float(m.group(2))
                    predictions = [Score(FOOTBALLPREDICTIONS_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")