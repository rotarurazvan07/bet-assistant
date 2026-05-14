from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

BETCLAN_NAME = "betclan"
BETCLAN_URL = "https://www.betclan.com/predictions/"

URLS = [
    "https://www.betclan.com/todays-football-predictions/",
    "https://www.betclan.com/tomorrows-football-predictions/",
    "https://www.betclan.com/day-after-tomorrows-football-predictions/",
    "https://www.betclan.com/future-football-predictions/",
]


class BetClanFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        # Note: This pattern of multiple discovery fetches is discouraged in v2
        # but kept for compatibility with the site structure.
        matches_urls = []
        for url in URLS:
            try:
                page = Page.from_url(url)
                matches_anchors = page.find(".bclisttip")
                matches_urls.extend(anchor.find("a").attr("href") for anchor in matches_anchors if anchor.find("a"))
            except Exception as e:
                logger.warning(f"Failed to discover URLs from {url}: {e}")

        logger.info(f"Found {len(matches_urls)} matches to scrape")
        return matches_urls

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            home_team = page.find(".teamtophome").text().strip()
            away_team = page.find(".teamtopaway").text().strip()
            
            date_element = page.find(".dategamedetailsis")
            if not date_element:
                logger.warning(f"Could not find date for {url}")
                return
            
            date_str = date_element.text().strip().replace("Date ", "").split(" ")[0]
            current_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            
            # The last h5 inside .predione .parttwo contains the score
            h5_elements = page.find(".predione .parttwo h5")
            if not h5_elements:
                logger.warning(f"Could not find score prediction for {url}")
                return
                
            score_str = h5_elements[-1].text().strip()
            home_score, away_score = score_str.split("-")
            predictions = [Score(BETCLAN_NAME, home_score.strip(), away_score.strip())]

            self.add_match(Match(home_team, away_team, current_date, predictions))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
