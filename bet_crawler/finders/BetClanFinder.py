from datetime import datetime

from scrape_kit import fetch, get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

BETCLAN_NAME = "betclan"

# Discovery URLs - listing pages that contain links to match pages
DISCOVERY_URLS = [
    "https://www.betclan.com/todays-football-predictions/",
    "https://www.betclan.com/tomorrows-football-predictions/",
    "https://www.betclan.com/day-after-tomorrows-football-predictions/",
    "https://www.betclan.com/future-football-predictions/",
]


class BetClanFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URLs for scraping."""
        return DISCOVERY_URLS

    def get_match_urls(self) -> list[str]:
        """Discover match URLs from listing pages via lightweight HTTP."""
        all_urls = []
        for url in DISCOVERY_URLS:
            try:
                page = fetch(url)
                for anchor in page.select(".bclisttip"):
                    link = anchor.find("a")
                    if link:
                        href = link.attr("href")
                        if href:
                            all_urls.append(href)
                logger.info(f"Found {len(all_urls)} match URLs from {url}")
            except Exception as e:
                logger.warning(f"Failed to discover from {url}: {e}")
        return list(set(all_urls))

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse individual match page for predictions."""
        try:
            home_team = page.find(".teamtophome").text().strip()
            away_team = page.find(".teamtopaway").text().strip()

            date_element = page.find(".dategamedetailsis")
            if not date_element:
                logger.warning(f"Could not find date for {url}")
                return

            date_str = date_element.text().strip().replace("Date ", "").split(" ")[0]
            current_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)

            h5_elements = page.select(".predione .parttwo h5")
            if not h5_elements:
                logger.warning(f"Could not find score prediction for {url}")
                return

            score_str = h5_elements[-1].text().strip()
            home_score, away_score = score_str.split("-")
            predictions = [Score(BETCLAN_NAME, home_score.strip(), away_score.strip())]

            self.add_match(Match(home_team, away_team, current_date, predictions, None))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")