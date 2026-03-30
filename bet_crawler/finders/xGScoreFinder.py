from scrape_kit import get_logger

logger = get_logger(__name__)

import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

from .BaseMatchFinder import BaseMatchFinder

XGSCORE_URL = "https://xgscore.io/predictions/correct-score"
XGSCORE_NAME = "xgscore"
MAX_CONCURRENCY = 1


class xGScoreFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        return [XGSCORE_URL]

    def get_matches(self, urls=None) -> None:
        """Load predictions page, execute JS to expand, then parse."""
        with WebScraper.browser(solve_cloudflare=True, interactive=True) as session:
            logger.info("Loading predictions page...")
            session.fetch(XGSCORE_URL)
            session.wait_for_selector("mat-button-toggle-group", timeout=15000)

            logger.info("Clicking on Week view.")

            try:
                clicked = session.execute_script("""
                    (function() {
                        const buttons = Array.from(document.querySelectorAll('.mat-button-toggle-label-content'));
                        const weekBtn = buttons.find(el => el.textContent.trim() === 'Week');
                        if (weekBtn) {
                            weekBtn.scrollIntoView({behavior: 'smooth', block: 'center'});
                            weekBtn.click();
                            return true;
                        }
                        return false;
                    })()
                """)
                if clicked:
                    logger.info("Successfully switched to Week view")
                    # Wait for the content to reload/update
                    time.sleep(5)
                else:
                    logger.info("Could not find 'Week' button.")
            except Exception as e:
                logger.info(f"Click error: {e}")

            html = session.page.content()

        self._parse_page(None, html)

    def _parse_page(self, _, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        all_anchors = soup.find_all("div", class_="xgs-category-forecast-fixture")
        for anchor in all_anchors:
            try:
                home_team = (
                    anchor.find("a", class_="xgs-category-forecast-fixture_teams")
                    .find_all("span")[0]
                    .get_text()
                )
                away_team = (
                    anchor.find("a", class_="xgs-category-forecast-fixture_teams")
                    .find_all("span")[-1]
                    .get_text()
                )
                match_datetime = min(
                    (
                        datetime.strptime(
                            f"{anchor.find('div', class_='xgs-fixture_datetime').get_text().strip()} {y}",
                            "%b %d %H:%M %Y",
                        )
                        for y in [
                            datetime.now().year - 1,
                            datetime.now().year,
                            datetime.now().year + 1,
                        ]
                    ),
                    key=lambda d: abs(d - datetime.now()),
                )
                score_text = anchor.find(
                    "div", class_="xgs-category-forecast-fixture_bet"
                ).get_text()
                predictions = [
                    Score(
                        XGSCORE_NAME, score_text.split("-")[0], score_text.split("-")[1]
                    )
                ]
                odds = None

                self.add_match(
                    Match(home_team, away_team, match_datetime, predictions, odds)
                )

            except Exception as e:
                logger.info(f"SKIPPED: Parse error - {e}")
