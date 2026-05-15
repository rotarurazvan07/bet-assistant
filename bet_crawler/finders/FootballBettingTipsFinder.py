from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

FOOTBALL_BETTING_TIPS_URL = "https://www.footballbettingtips.org/predictions/"
FOOTBALL_BETTING_TIPS_NAME = "footballbettingtips"


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return [FOOTBALL_BETTING_TIPS_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # Match containers
            rows = page.select(".match-row")
            if not rows:
                rows = page.select("tr.prediction-row")

            for row in rows:
                try:
                    home_team = row.find(".home-team-name").text().strip()
                    away_team = row.find(".away-team-name").text().strip()
                    
                    # Date extraction
                    date_text = row.find(".match-time").text().strip()
                    try:
                        # Assuming format like "15/05 20:45"
                        match_date = datetime.strptime(date_text, "%d/%m %H:%M").replace(year=datetime.now().year)
                    except ValueError:
                        match_date = datetime.now()

                    score_div = row.select(".predicted-score")
                    if score_div:
                        score_text = score_div[0].text().strip()
                        if "-" in score_text:
                            home_p, away_p = score_text.split("-")
                            predictions = [Score(FOOTBALL_BETTING_TIPS_NAME, float(home_p), float(away_p))]
                        else:
                            continue
                    else:
                        continue

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
