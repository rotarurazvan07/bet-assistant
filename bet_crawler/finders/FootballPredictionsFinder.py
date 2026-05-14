from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

FOOTBALL_PREDICTIONS_URL = "https://www.footballpredictions.net/"
FOOTBALL_PREDICTIONS_NAME = "footballpredictions"


class FootballPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return [FOOTBALL_PREDICTIONS_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # Matches are usually in blocks
            match_items = page.find(".match-item")
            if not match_items:
                match_items = page.find(".prediction-card")

            for item in match_items:
                try:
                    home_team = item.find(".home-team").text().strip()
                    away_team = item.find(".away-team").text().strip()
                    
                    date_text = item.find(".date").text().strip()
                    try:
                        # Format: "15 May 2026"
                        match_date = datetime.strptime(date_text, "%d %b %Y").replace(hour=0, minute=0, second=0)
                    except ValueError:
                        match_date = datetime.now()

                    score_text = item.find(".prediction").text().strip()
                    if ":" in score_text:
                        home_p, away_p = score_text.split(":")
                        predictions = [Score(FOOTBALL_PREDICTIONS_NAME, float(home_p), float(away_p))]
                    elif "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(FOOTBALL_PREDICTIONS_NAME, float(home_p), float(away_p))]
                    else:
                        continue

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
