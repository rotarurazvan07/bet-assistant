"""Match finder for whoscored.com (UTC timestamps, browser pages)."""

from bet_crawler.crawler_logging import exception_event, get_logger, log_event

logger = get_logger(__name__)

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, browser, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"
MAX_CONCURRENCY = 3


class WhoScoredFinder(BaseMatchFinder):
    """Scrapes whoscored fixture pages via browser sessions."""

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract for whoscored (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)

    # TIMEZONE = "UTC"  # WhoScored provides UTC timestamps

    def get_matches_urls(self):
        """Get match URLs via browser (needs JS rendering)."""
        with browser(solve_cloudflare=True) as session:
            page = session.fetch(WHOSCORED_URL + "previews")
            soup = BeautifulSoup(page, "html.parser")

        table = soup.find("table", class_="grid")
        urls = [WHOSCORED_URL + a["href"] for a in table.find_all("a") if "matches" in a["href"]]
        logger.info(f"{len(urls)} matches to scrape")
        return urls

    def get_matches(self, urls) -> None:
        """Fetch whoscored fixture URLs and parse them via scrape."""
        scrape(
            urls,
            self._parse_page_with_log_context,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        # 1. Look for the embedded JSON config that WhoScored now uses
        """Parse one whoscored page (UTC datetimes) and emit matches."""
        import json

        try:
            match_json = re.search(r"matchHeaderJson: JSON\.parse\(\'(.*?)\'\),", html)
            if not match_json:
                log_event(
                    logger,
                    event="match.skipped",
                    outcome="error",
                    reason_code="match_header_json_missing",
                    level=40,
                    message=f"Skipping WhoScored page without matchHeaderJson: {url}",
                    source_key="whoscored",
                    url=url,
                )
                return

            data = json.loads(match_json.group(1))
            home_team = data.get("HomeTeamName")
            away_team = data.get("AwayTeamName")

            # StartTimeUtc format: /Date(1772290800000)/
            ts_str = data.get("StartTimeUtc", "").strip("/Date()")
            ts = int(ts_str) / 1000
            match_datetime = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)

            # 2. Extract score predictions from DOM
            soup = BeautifulSoup(html, "html.parser")
            score_container = soup.find("div", id="preview-prediction")
            score = score_container.find_all("span", class_="predicted-score")

            # Try to create the match object, but handle exceptions for individual matches
            try:
                scores = [
                    Score(
                        WHOSCORED_NAME,
                        score[0].get_text(strip=True),
                        score[1].get_text(strip=True),
                    )
                ]
                self.add_match(
                    Match(
                        home_team,
                        away_team,
                        match_datetime.replace(hour=0, minute=0, second=0, microsecond=0),
                        scores,
                        None,
                    )
                )
            except Exception as e:
                exception_event(
                    logger,
                    event="match.parse.failed",
                    reason_code="match_object_creation_failed",
                    message=f"Skipping malformed WhoScored match at {url}: {e}",
                    source_key="whoscored",
                    url=url,
                )
                return

        except Exception as e:
            exception_event(
                logger,
                event="source.page.failed",
                reason_code="page_parse_failed",
                message=f"Failed to parse WhoScored page {url}: {e}",
                source_key="whoscored",
                url=url,
            )
