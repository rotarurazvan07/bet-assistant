import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

ONEMILLION_URL = "https://onemillionpredictions.com"
ONEMILLION_NAME = "onemillionpredictions"

TOP_LEAGUES = [
    "https://onemillionpredictions.com/england-premier-league/predictions/",
    "https://onemillionpredictions.com/italy-serie-a/predictions/",
    "https://onemillionpredictions.com/spain-la-liga/predictions/",
    "https://onemillionpredictions.com/germany-bundesliga/predictions/",
    "https://onemillionpredictions.com/france-ligue-1/predictions/",
    "https://onemillionpredictions.com/netherland-eredivisie/predictions/",
    "https://onemillionpredictions.com/portugal-primeira-liga/predictions/",
    "https://onemillionpredictions.com/argentina-liga-profesional/predictions/",
    "https://onemillionpredictions.com/brazil-serie-a/predictions/",
    "https://onemillionpredictions.com/mexico-liga-mx/predictions/",
    "https://onemillionpredictions.com/usa-mls/predictions/",
    "https://onemillionpredictions.com/uefa-champions-league/predictions/",
    "https://onemillionpredictions.com/uefa-europa-league/predictions/",
    "https://onemillionpredictions.com/uefa-europa-conference-league/predictions/",
]


class OneMillionPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return TOP_LEAGUES

    def get_match_urls(self) -> list[str]:
        return TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse match predictions from OneMillionPredictions league page."""
        try:
            rows = page.select("table.table tbody tr, table tbody tr")
            if not rows:
                logger.debug(f"No table rows on {url}")
                return
            for row in rows:
                try:
                    cols = row.select("td")
                    if len(cols) < 4:
                        continue
                    # Date in first column
                    date_str = cols[0].text().strip()
                    match_date = self.parse_date_robust(date_str)
                    if not match_date:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    # Teams - try link text or plain text
                    home_link = cols[1].find("a")
                    home_team = home_link.text().strip() if home_link else cols[1].text().strip()
                    away_link = cols[2].find("a")
                    away_team = away_link.text().strip() if away_link else cols[2].text().strip()
                    if not home_team or not away_team:
                        continue
                    # Score prediction
                    score_text = cols[3].text().strip()
                    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
                    if not m:
                        continue
                    predictions = [Score(ONEMILLION_NAME, float(m.group(1)), float(m.group(2)))]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")