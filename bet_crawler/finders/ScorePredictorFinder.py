from datetime import datetime, timedelta

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SCORE_PREDICTOR_URL = "https://www.scorepredictor.net/index.php?clanek=quicktips&sekce=fotbal&lang=en"
SCORE_PREDICTOR_NAME = "scorepredictor"


class ScorePredictorFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        # ScorePredictor often uses a daily parameter
        urls = [f"{SCORE_PREDICTOR_URL}&day={i}" for i in range(self.num_days_ahead + 1)]
        logger.info(f"Found {len(urls)} ScorePredictor date URLs")
        return urls

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # ScorePredictor usually has a table with class 'prediction'
            rows = page.find("table.prediction tr")
            if not rows:
                logger.warning(f"No prediction table found on {url}")
                return

            for row in rows[1:]:  # Skip header
                try:
                    cols = row.find("td")
                    if len(cols) < 5:
                        continue

                    date_str = cols[0].text().strip()
                    home_team = cols[1].text().strip()
                    away_team = cols[2].text().strip()
                    
                    try:
                        home_score = float(cols[3].text().strip())
                        away_score = float(cols[4].text().strip())
                    except (ValueError, IndexError):
                        continue

                    # Date format DD.MM.YYYY
                    try:
                        match_date = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        day_offset = int(url.split("day=")[-1]) if "day=" in url else 0
                        match_date = (datetime.now() + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)

                    predictions = [Score(SCORE_PREDICTOR_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
