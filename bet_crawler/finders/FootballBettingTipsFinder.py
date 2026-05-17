from scrape_kit import get_logger

logger = get_logger(__name__)
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder
import contextlib

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "footballbettingtips"
MAX_CONCURRENCY = 1


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        today = datetime.now()
        urls = [
            f"https://www.footballbettingtips.org/tips/{today.strftime('%Y-%m-%d')}.html",
            f"https://www.footballbettingtips.org/tips/{(today + timedelta(days=1)).strftime('%Y-%m-%d')}.html",
        ]
        logger.info(f"Found {len(urls)} urls to scrape")
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
            soup = BeautifulSoup(html, "html.parser")
            h2_elements = soup.find_all("h2")
            if not h2_elements:
                logger.warning(f"Could not find date header in {url}")
                return

            try:
                match_datetime = datetime.strptime(h2_elements[-1].get_text(strip=True), "%A, %d %B %Y").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            except ValueError:
                logger.warning(f"Failed to parse date header in {url}")
                return

            table_results = soup.find("table", class_="results")
            if not table_results:
                logger.warning(f"Could not find table.results in {url}")
                return

            for idx, match_html in enumerate(table_results.find_all("tr"), start=1):
                try:
                    anchor = match_html.find("a")
                    if not anchor:
                        continue

                    team_text = anchor.get_text(strip=True)
                    if " - " not in team_text:
                        continue

                    home_team_name, away_team_name = team_text.split(" - ", 1)

                    td_elements = match_html.find_all("td")
                    if len(td_elements) < 2:
                        continue

                    score_match = re.search(r"(\d+:\d+)", td_elements[-2].get_text(strip=True))
                    if not score_match:
                        continue

                    score_text = score_match.group(1)
                    try:
                        home_pred, away_pred = score_text.split(":")
                        score = Score(FOOTBALLBETTINGTIPS_NAME, int(home_pred), int(away_pred))
                    except ValueError:
                        continue

                    odds = None
                    desktop_elements = match_html.find_all(class_="desktop")
                    if len(desktop_elements) >= 3:
                        with contextlib.suppress(Exception):
                            odds = Odds(
                                home=desktop_elements[0].get_text(strip=True),
                                draw=desktop_elements[1].get_text(strip=True),
                                away=desktop_elements[2].get_text(strip=True),
                            )

                    self.add_match(
                        Match(
                            home_team=home_team_name,
                            away_team=away_team_name,
                            datetime=match_datetime,
                            predictions=[score],
                            odds=odds,
                        )
                    )
                except Exception as e:
                    logger.error(f"SKIPPED [{url}] Match #{idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
