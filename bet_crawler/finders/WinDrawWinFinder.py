from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
MAX_CONCURRENCY = 3


class WinDrawWinFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        page = fetch(WINDRAWWIN_URL, stealthy_headers=True)
        soup = BeautifulSoup(page, "html.parser")

        all_trs = soup.find("div", class_="widetable").find_all("tr")
        start = (
            next(i for i, r in enumerate(all_trs) if "European Leagues" in r.text) + 1
        )
        league_urls = []
        for tr in all_trs[start:]:
            anchors = tr.find_all("a")
            if anchors:
                league_urls.append(anchors[-1]["href"])

        logger.info(f"Found {len(league_urls)} leagues to scrape")
        return league_urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, "html.parser")

            current_date = None
            matches_div = soup.find("div", class_="wdwtablest mb30")
            if matches_div is None:
                logger.info(f"SKIPPED [{url}]: No matches")
                return

            for match_div in matches_div.contents[2:]:
                try:
                    if match_div.has_attr("class") and "wttrdt" in match_div["class"]:
                        date_str = re.sub(
                            r"(?<=\d)(st|nd|rd|th)", "", match_div.get_text()
                        )
                        date_str = date_str.replace("Today, ", "").replace(
                            "Tomorrow, ", ""
                        )
                        current_date = datetime.strptime(
                            date_str, "%A, %B %d, %Y"
                        ).replace(hour=0, minute=0, second=0, microsecond=0)
                        continue

                    inner = match_div.contents[:-1]
                    home_team = inner[0].find("div").get_text()
                    away_team = inner[1].find("div").get_text()

                    score_text = inner[-1].get_text()
                    home = float(score_text.split("-")[0])
                    away = float(score_text.split("-")[1])
                    predictions = [Score(WINDRAWWIN_NAME, home, away)]

                    mo_tag = match_div.find("div", class_="wtmo")
                    ou_tag = match_div.find("div", class_="wtou")
                    bt_tag = match_div.find("div", class_="wtbt")

                    odds = Odds(
                        home=mo_tag.contents[1].get_text() if mo_tag else None,
                        draw=mo_tag.contents[2].get_text() if mo_tag else None,
                        away=mo_tag.contents[3].get_text() if mo_tag else None,
                        over=ou_tag.contents[1].get_text() if ou_tag else None,
                        under=ou_tag.contents[2].get_text() if ou_tag else None,
                        btts_y=bt_tag.contents[1].get_text() if bt_tag else None,
                        btts_n=bt_tag.contents[2].get_text() if bt_tag else None,
                    )

                    self.add_match(
                        Match(home_team, away_team, current_date, predictions, odds)
                    )

                except Exception as e:
                    logger.info(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
