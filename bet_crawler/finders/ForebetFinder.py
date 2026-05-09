from scrape_kit import browser, get_logger

logger = get_logger(__name__)

import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
MAX_CONCURRENCY = 1


class ForebetFinder(BaseMatchFinder):
    """Forebet uses interactive browser (JS execution to load more matches).
    get_matches overrides the standard flow since it needs a live session.
    """

    TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        # TODO : Can use the Countries list on the left to align with other crawlers
        return [FOREBET_URL]

    def get_matches(self, urls=None) -> None:
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
                    logger.info(f"Attempt {attempt}/{max_attempts}: Loading predictions page (Cloudflare)...")
                    session.fetch(
                        FOREBET_ALL_PREDICTIONS_URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    session.click('button.fc-cta-consent')

                    while session.click('div#mrows span', visible_only=True):
                        pass

                    html = session.page.content()
                    self._parse_page(FOREBET_ALL_PREDICTIONS_URL, html)
                    return

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.error("All Forebet scraping attempts failed.")
                time.sleep(5)

    def _parse_page(self, url, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        all_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")
        logger.info(f"Found {len(all_anchors)} matches to scan")

        for anchor in all_anchors:
            try:
                home_team = anchor.find("div", class_="tnms").find("span", class_="homeTeam").get_text()
                away_team = anchor.find("div", class_="tnms").find("span", class_="awayTeam").get_text()

                if anchor.find("div", class_="scoreLnk").get_text().strip():
                    logger.info(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date = anchor.find("span", class_="date_bah").get_text()
                match_date = datetime.strptime(match_date, "%d/%m/%Y %H:%M")

                home = float(anchor.find("div", class_="ex_sc").get_text().split("-")[0])
                away = float(anchor.find("div", class_="ex_sc").get_text().split("-")[1])
                predictions = [Score(FOREBET_NAME, home, away)]

                odds_tags = [o.get_text() for o in anchor.find("div", class_="haodd").find_all("span")]
                odds = Odds(
                    home=float(odds_tags[0]) if odds_tags[0] not in ("", " - ") else None,
                    draw=float(odds_tags[1]) if odds_tags[1] not in ("", " - ") else None,
                    away=float(odds_tags[2]) if odds_tags[2] not in ("", " - ") else None,
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error - {e}")
