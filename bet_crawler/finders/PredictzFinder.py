import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

PREDICTZ_URL = "https://www.predictz.com/"
PREDICTZ_NAME = "predictz"

TOP_LEAGUES = [
    "https://www.predictz.com/predictions/champions-league/",
    "https://www.predictz.com/predictions/europa-league/",
    "https://www.predictz.com/predictions/conference-league/",
    "https://www.predictz.com/predictions/england-premier-league/",
    "https://www.predictz.com/predictions/italy-serie-a/",
    "https://www.predictz.com/predictions/spain-la-liga/",
    "https://www.predictz.com/predictions/germany-bundesliga/",
    "https://www.predictz.com/predictions/france-ligue-1/",
    "https://www.predictz.com/predictions/belgium-jupiler-league/",
    "https://www.predictz.com/predictions/england-championship/",
    "https://www.predictz.com/predictions/portugal-primeira-liga/",
    "https://www.predictz.com/predictions/brazil-serie-a/",
    "https://www.predictz.com/predictions/usa-mls/",
    "https://www.predictz.com/predictions/netherlands-eredivisie/",
    "https://www.predictz.com/predictions/denmark-superliga/",
    "https://www.predictz.com/predictions/poland-ekstraklasa/",
    "https://www.predictz.com/predictions/argentina-primera-division/",
    "https://www.predictz.com/predictions/japan-j-league/",
    "https://www.predictz.com/predictions/turkey-super-lig/",
    "https://www.predictz.com/predictions/sweden-allsvenskan/",
    "https://www.predictz.com/predictions/croatia-1-hnl/",
    "https://www.predictz.com/predictions/mexico-liga-mx/",
    "https://www.predictz.com/predictions/spain-segunda-division/",
    "https://www.predictz.com/predictions/norway-eliteserien/",
    "https://www.predictz.com/predictions/austria-bundesliga/",
    "https://www.predictz.com/predictions/switzerland-super-league/",
    "https://www.predictz.com/predictions/italy-serie-b/",
    "https://www.predictz.com/predictions/germany-2-bundesliga/",
    "https://www.predictz.com/predictions/france-ligue-2/",
    "https://www.predictz.com/predictions/scotland-premiership/",
]


class PredictzFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return league URLs directly."""
        return TOP_LEAGUES

    def get_match_urls(self) -> list[str]:
        """Return league URLs for scraping."""
        return TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse match predictions from a Predictz league page."""
        try:
            current_date = None
            items = page.select(".pzcnth")
            if not items:
                logger.debug(f"No prediction items on {url}")
                return
            for item in items:
                try:
                    # Check if this is a date header
                    text = item.text().strip()
                    if not item.find(".fixt"):
                        # Try to parse as date header
                        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
                        parsed = self.parse_date_robust(cleaned)
                        if parsed:
                            current_date = parsed
                        continue
                    # Match row with "fixt" class
                    fixt = item.find(".fixt")
                    if not fixt:
                        continue
                    fixt_text = fixt.text().strip()
                    if " vs " not in fixt_text:
                        continue
                    parts = fixt_text.split(" vs ")
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()
                    # Score prediction
                    score_el = item.find(".pointed")
                    if not score_el:
                        continue
                    score_text = score_el.text().strip()
                    if "-" not in score_text:
                        continue
                    score_parts = score_text.split("-")
                    home_score = float(score_parts[0].strip())
                    away_score = float(score_parts[1].strip())
                    predictions = [Score(PREDICTZ_NAME, home_score, away_score)]
                    # Odds (optional)
                    odds = None
                    odds_els = item.select(".pointed")
                    if len(odds_els) >= 4:
                        try:
                            odds = Odds(
                                home=odds_els[1].text().strip(),
                                draw=odds_els[2].text().strip(),
                                away=odds_els[3].text().strip(),
                            )
                        except Exception:
                            pass
                    match_date = current_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    self.add_match(Match(home_team, away_team, match_date, predictions, odds))
                except Exception as e:
                    logger.debug(f"Skipping item: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")