from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

LEGIT_PREDICT_URL = "https://www.legitpredict.com/predictions/"
LEGIT_PREDICT_NAME = "legitpredict"


class LegitPredictFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return [LEGIT_PREDICT_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # Matches in rows
            rows = page.select("table tr")
            if not rows:
                rows = page.select(".prediction-item")

            for row in rows:
                try:
                    cols = row.select("td")
                    if len(cols) < 4:
                        continue

                    home_team = cols[1].text().strip()
                    away_team = cols[2].text().strip()
                    
                    score_text = cols[3].text().strip()
                    if "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(LEGIT_PREDICT_NAME, float(home_p), float(away_p))]
                    else:
                        continue

                    match_date = datetime.now().replace(hour=0, minute=0, second=0)

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
