import re
from datetime import datetime, timedelta

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

LEGITPREDICT_URL = "https://legitpredict.com/correct-score?dt="
LEGITPREDICT_NAME = "legitpredict"


class LegitPredictFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return date-based URLs for scraping."""
        urls = []
        for i in range(self.num_days_ahead + 1):
            date = datetime.now() + timedelta(days=i)
            urls.append(LEGITPREDICT_URL + date.strftime("%Y-%m-%d"))
        return urls

    def get_match_urls(self) -> list[str]:
        """Return date URLs directly (no discovery needed)."""
        return self.get_urls()

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse match predictions from LegitPredict page."""
        try:
            cards = page.select("div.card-body")
            if not cards:
                logger.debug(f"No prediction cards on {url}")
                return
            for card in cards:
                try:
                    # Teams from h5 heading
                    h5 = card.find("h5")
                    if not h5:
                        continue
                    title = h5.text().strip()
                    if " vs " in title:
                        parts = title.split(" vs ")
                    elif " - " in title:
                        parts = title.split(" - ")
                    else:
                        continue
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()
                    # Date
                    date_str = url.split("dt=")[-1] if "dt=" in url else None
                    if date_str:
                        try:
                            match_date = datetime.strptime(date_str, "%Y-%m-%d")
                        except ValueError:
                            match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    else:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    # Score prediction
                    score_el = card.find("div.score, span.score, .prediction-score")
                    if not score_el:
                        # Try finding text with score pattern
                        card_text = card.text()
                        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", card_text)
                        if not m:
                            continue
                        home_score = float(m.group(1))
                        away_score = float(m.group(2))
                    else:
                        score_text = score_el.text().strip()
                        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
                        if not m:
                            continue
                        home_score = float(m.group(1))
                        away_score = float(m.group(2))
                    predictions = [Score(LEGITPREDICT_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping card: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")