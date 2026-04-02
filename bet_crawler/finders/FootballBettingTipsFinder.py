from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.Match import *
from scrape_kit import ScrapeMode, scrape
from scrape_kit import fetch, browser

from .BaseMatchFinder import BaseMatchFinder

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "footballbettingtips"
MAX_CONCURRENCY = 1


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        """Load main page via browser (CF bypass), extract prediction URLs."""
        with browser(interactive=True, solve_cloudflare=True) as session:
            page = session.fetch(
                FOOTBALLBETTINGTIPS_URL, timeout=90000, wait_until="networkidle"
            )
            session.wait_for_selector("h3", timeout=15000)
            soup = BeautifulSoup(page.html_content, "html.parser")

        return [
            FOOTBALLBETTINGTIPS_URL + a.find("a")["href"]
            for a in soup.find_all("h3")[:2]
        ]

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
            match_datetime = datetime.strptime(
                soup.find_all("h2")[-1].get_text(), "%A, %d %B %Y"
            )

            for match_html in soup.find("table", class_="results").find_all("tr"):
                if not match_html.find("a"):
                    continue

                home_team_name = match_html.find("a").get_text().split(" - ")[0]
                away_team_name = match_html.find("a").get_text().split(" - ")[1]

                score_text = re.search(
                    r"(\d+:\d+)", match_html.find_all("td")[-2].get_text()
                ).group(1)
                score = Score(
                    FOOTBALLBETTINGTIPS_NAME,
                    score_text.split(":")[0],
                    score_text.split(":")[1],
                )

                try:
                    odds = Odds(
                        home=match_html.find_all(class_="desktop")[0]
                        .get_text()
                        .strip(),
                        draw=match_html.find_all(class_="desktop")[1]
                        .get_text()
                        .strip(),
                        away=match_html.find_all(class_="desktop")[2]
                        .get_text()
                        .strip(),
                    )
                except:
                    odds = None

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
            logger.error(f"Error parsing {url}: {e}")


