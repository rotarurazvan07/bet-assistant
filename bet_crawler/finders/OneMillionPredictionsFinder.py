from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

ONE_MILLION_URL = "https://www.onemillionpredictions.com/football-predictions/"
ONE_MILLION_NAME = "onemillionpredictions"


class OneMillionPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        # Usually scrapes a few pages
        urls = [f"{ONE_MILLION_URL}?page={i}" for i in range(1, 4)]
        logger.info(f"Found {len(urls)} OneMillionPredictions pages to scrape")
        return urls

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # Match containers
            match_cards = page.select(".match-card")
            if not match_cards:
                # Try table fallback if class changed
                match_cards = page.select(".prediction-item")
            
            for card in match_cards:
                try:
                    home_team = card.find(".home-team").text().strip()
                    away_team = card.find(".away-team").text().strip()
                    
                    date_text = card.find(".match-date").text().strip()
                    # Expecting format like "May 15, 2026"
                    try:
                        match_date = datetime.strptime(date_text, "%b %d, %Y").replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

                    score_text = card.find(".prediction-score").text().strip()
                    if "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(ONE_MILLION_NAME, float(home_p), float(away_p))]
                    else:
                        continue

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
