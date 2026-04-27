from scrape_kit import get_logger

logger = get_logger(__name__)

import re
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
    "https://www.betclan.com/future-football-predictions/"
]
class BetClanFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

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

            home_team = soup.find("div", class_="teamtophome").get_text().strip()
            away_team = soup.find("div", class_="teamtopaway").get_text().strip()
            date_str = soup.find("span", class_="dategamedetailsis").get_text().strip().replace("Date ", "").split(" ")[0]
            current_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            score_str = soup.find("div", class_="predione").find("div", class_="parttwo").find_all("h5")[-1].get_text().strip()
            predictions = [Score(BETCLAN_NAME,
                                 home=(score_str.split("-")[0]),
                                 away=(score_str.split("-")[1])
                                 )]
            odds = None

            self.add_match(Match(home_team, away_team, current_date, predictions, odds))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
