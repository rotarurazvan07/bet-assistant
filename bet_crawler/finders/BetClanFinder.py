from scrape_kit import get_logger

logger = get_logger(__name__)

from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

BETCLAN_NAME = "betclan"
BETCLAN_URL = "https://www.betclan.com/predictions/"
MAX_CONCURRENCY = 3

URLS = [
    "https://www.betclan.com/todays-football-predictions/",
    "https://www.betclan.com/tomorrows-football-predictions/",
    "https://www.betclan.com/day-after-tomorrows-football-predictions/",
    "https://www.betclan.com/future-football-predictions/",
]


class BetClanFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        matches_urls = []
        for url in URLS:
            page = fetch(url, stealthy_headers=False)
            soup = BeautifulSoup(page, "html.parser")

            matches_anchors = soup.find_all("div", class_="bclisttip")
            matches_urls.extend(anchor.find("a").get("href") for anchor in matches_anchors)

        logger.info(f"Found {len(matches_urls)} matches to scrape")
        return matches_urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, "html.parser")

            home_div = soup.find("div", class_="teamtophome")
            away_div = soup.find("div", class_="teamtopaway")
            if not home_div or not away_div:
                logger.warning(f"Could not find team names in {url}")
                return

            home_team = home_div.get_text(strip=True)
            away_team = away_div.get_text(strip=True)

            date_span = soup.find("span", class_="dategamedetailsis")
            if not date_span:
                logger.warning(f"Could not find date in {url}")
                return

            date_str = date_span.get_text(strip=True).replace("Date ", "").split(" ")[0]
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                logger.warning(f"Failed to parse date string: {date_str} in {url}")
                return

            predione = soup.find("div", class_="predione")
            if not predione:
                return
            parttwo = predione.find("div", class_="parttwo")
            if not parttwo:
                return

            h5_elements = parttwo.find_all("h5")
            if not h5_elements:
                return

            score_str = h5_elements[-1].get_text(strip=True)
            if "-" not in score_str:
                return

            try:
                home_pred, away_pred = score_str.split("-", 1)
                predictions = [Score(BETCLAN_NAME, home=home_pred.strip(), away=away_pred.strip())]
            except ValueError:
                return

            self.add_match(Match(home_team, away_team, current_date, predictions, None))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
