from scrape_kit import get_logger

logger = get_logger(__name__)

from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

LEGITPREDICT_URL = "https://legitpredict.com/correct-score?dt="
LEGITPREDICT_NAME = "legitpredict"
MAX_CONCURRENCY = 3


class LegitPredictFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        urls = [
            f"{LEGITPREDICT_URL}{(datetime.now() + timedelta(days=i)).strftime('%d-%m-%Y')}"
            for i in range(7)
        ]
        logger.info(f"{len(urls)} urls to scrape")
        return urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            if "OOPS! NO GAME HERE" in html:
                logger.info(f"No games found for {url}")
                return
            dt_obj = datetime.strptime(url.split("dt=")[-1], "%d-%m-%Y")
            soup = BeautifulSoup(html, "html.parser")
            matches_trs = (
                soup.find("div", class_="content nopaddingsmall")
                .find("tbody")
                .find_all("tr")
            )
            for tr in matches_trs:
                home_team = tr.find_all("td")[2].text.strip().split("VS")[0].strip()
                away_team = tr.find_all("td")[2].text.strip().split("VS")[1].strip()
                score = Score(
                    LEGITPREDICT_NAME,
                    int(tr.find_all("td")[3].text.strip().split("-")[0]),
                    int(tr.find_all("td")[3].text.strip().split("-")[1]),
                )

                dt_obj = dt_obj.replace(
                    hour=int(tr.find("td").text.strip().split(":")[0]),
                    minute=int(tr.find("td").text.strip().split(":")[1]),
                )

                self.add_match(Match(home_team, away_team, dt_obj, score, None, None))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
