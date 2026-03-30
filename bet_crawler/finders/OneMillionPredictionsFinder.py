from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import get_logger

logger = get_logger(__name__)

from bet_framework.core.Match import *
from bet_framework.WebScraper import ScrapeMode, WebScraper

from .BaseMatchFinder import BaseMatchFinder

ONE_MILLION_PREDICTIONS_NAME = "onemillionpredictions"
ONE_MILLION_PREDICTIONS_URL = "https://onemillionpredictions.com"
MAX_CONCURRENCY = 1


class OneMillionPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        page = WebScraper.fetch(ONE_MILLION_PREDICTIONS_URL, stealthy_headers=True)
        soup = BeautifulSoup(page, "html.parser")
        table = soup.find("table", attrs={"aria-label": "Predictions by Days"})
        links = [a["href"] + "correct-score/" for a in table.find_all("a")][1:]
        logger.info(f"Found {len(links)} leagues to scrape")
        return links

    def get_matches(self, urls) -> None:
        self.scrape_urls(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, "html.parser")

            for match_tr in soup.find_all("tbody")[2].find_all("tr"):
                try:
                    cells = match_tr.find_all("td")
                    dt_tag = cells[0].find(class_="fulldatetime")
                    if dt_tag:
                        dt_str = dt_tag.get_text(strip=True)
                        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

                        teams = list(cells[1].stripped_strings)
                        home_team = teams[0]
                        away_team = teams[1]

                        score_text = cells[2].get_text(strip=True)

                        predictions = [
                            Score(
                                ONE_MILLION_PREDICTIONS_NAME,
                                int(score_text.split(":")[0]),
                                int(score_text.split(":")[1]),
                            )
                        ]
                        odds = None

                        self.add_match(
                            Match(home_team, away_team, dt_obj, predictions, odds)
                        )

                except Exception as e:
                    logger.info(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
