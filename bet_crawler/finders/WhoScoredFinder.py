from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from bet_framework.core.Match import *
from scrape_kit import ScrapeMode, scrape
from scrape_kit import fetch, browser

from .BaseMatchFinder import BaseMatchFinder

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"
MAX_CONCURRENCY = 3


class WhoScoredFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    TIMEZONE = "UTC"  # WhoScored provides UTC timestamps

    def get_matches_urls(self):
        """Get match URLs via browser (needs JS rendering)."""
        with browser(solve_cloudflare=True) as session:
            page = session.fetch(WHOSCORED_URL + "previews")
            soup = BeautifulSoup(page.html_content, "html.parser")

        table = soup.find("table", class_="grid")
        urls = [
            WHOSCORED_URL + a["href"]
            for a in table.find_all("a")
            if "matches" in a["href"]
        ]
        logger.info(f"{len(urls)} matches to scrape")
        return urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            # 1. Look for the embedded JSON config that WhoScored now uses
            import json

            match_json = re.search(r"matchHeaderJson: JSON\.parse\(\'(.*?)\'\),", html)
            if not match_json:
                logger.info(f"[{url}] WhoScored: Could not find matchHeaderJson block.")
                return

            data = json.loads(match_json.group(1))
            home_team = data.get("HomeTeamName")
            away_team = data.get("AwayTeamName")

            # StartTimeUtc format: /Date(1772290800000)/
            ts_str = data.get("StartTimeUtc", "").strip("/Date()")
            ts = int(ts_str) / 1000
            match_datetime = datetime.fromtimestamp(ts, tz=timezone.utc).replace(
                tzinfo=None
            )

            # 2. Extract score predictions from DOM
            soup = BeautifulSoup(html, "html.parser")
            score_container = soup.find("div", id="preview-prediction")
            score = score_container.find_all("span", class_="predicted-score")
            scores = [
                Score(
                    WHOSCORED_NAME,
                    score[0].get_text(strip=True),
                    score[1].get_text(strip=True),
                )
            ]
            self.add_match(Match(home_team, away_team, match_datetime, scores, None))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")


