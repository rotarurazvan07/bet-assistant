import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org.uk/"
FOOTBALLBETTINGTIPS_NAME = "footballbettingtips"

TOP_LEAGUES = [
    "https://www.footballbettingtips.org.uk/correct-score-tips/premier-league.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/serie-a.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/la-liga.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/bundesliga.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/ligue-1.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/eredivisie.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/primeira-liga.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/championship.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/serie-b.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/segunda-division.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/2-bundesliga.html",
    "https://www.footballbettingtips.org.uk/correct-score-tips/ligue-2.html",
]


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return TOP_LEAGUES

    def get_match_urls(self) -> list[str]:
        return TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse match predictions from football betting tips page."""
        try:
            rows = page.select("table.table tr, table.predictions tr")
            if not rows:
                logger.debug(f"No prediction table on {url}")
                return
            for row in rows:
                try:
                    cols = row.select("td")
                    if len(cols) < 4:
                        continue
                    date_str = cols[0].text().strip()
                    match_date = self.parse_date_robust(date_str)
                    if not match_date:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    home_team = cols[1].text().strip()
                    away_team = cols[2].text().strip()
                    score_text = cols[3].text().strip()
                    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
                    if not m:
                        continue
                    predictions = [Score(FOOTBALLBETTINGTIPS_NAME, float(m.group(1)), float(m.group(2)))]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")