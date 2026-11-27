"""Match finder for footballbettingtips daily tips."""

from bet_crawler.crawler_logging import get_logger, log_event

logger = get_logger(__name__)
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import browser

from bet_framework.core.Match import *

from ._browser_page import fetch_page, resolve_headless
from .BaseMatchFinder import BaseMatchFinder

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "footballbettingtips"


class FootballBettingTipsFinder(BaseMatchFinder):
    """Scrapes footballbettingtips prediction listings."""

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        """Return footballbettingtips listing URLs."""
        today = datetime.now()
        urls = [
            f"https://www.footballbettingtips.org/tips/{today.strftime('%Y-%m-%d')}.html",
            f"https://www.footballbettingtips.org/tips/{(today + timedelta(days=1)).strftime('%Y-%m-%d')}.html",
        ]
        logger.info(f"Found {len(urls)} urls to scrape")
        return urls

    _BROWSER_TIMEOUT_MS = 60_000

    def get_matches(self, urls) -> None:
        """Scrape all footballbettingtips URLs and emit matches via callback."""
        # The site sits behind a Cloudflare managed challenge on the runner, and
        # the plain HTTP STEALTH path is what raised source_scrape_exception there;
        # the browser session with the challenge solver is the path that works.
        with browser(
            solve_cloudflare=True,
            interactive=True,
            disable_resources=False,
            headless=resolve_headless(),
        ) as session:
            for url in urls:
                try:
                    # Navigating through the wrapped session is what runs the
                    # Cloudflare solver; the tips table is then client-rendered.
                    html = fetch_page(
                        session,
                        url,
                        "domcontentloaded",
                        self._BROWSER_TIMEOUT_MS,
                    )
                except Exception as e:
                    log_event(
                        logger,
                        event="source.fetch.retry",
                        outcome="error",
                        reason_code="fetch_retry_failed",
                        level=40,
                        message=f"Skipping footballbettingtips page {url}: still blocked after browser fetch: {e}",
                        source_key=FOOTBALLBETTINGTIPS_NAME,
                        url=url,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                    continue
                self._parse_page_with_log_context(url, html)

    def _parse_page(self, url, html) -> None:
        """Parse one footballbettingtips page and emit matches via callback."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            match_datetime = datetime.strptime(soup.find_all("h2")[-1].get_text(), "%A, %d %B %Y").replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            for match_html in soup.find("table", class_="results").find_all("tr"):
                try:
                    if not match_html.find("a"):
                        continue

                    home_team_name = match_html.find("a").get_text().split(" - ")[0]
                    away_team_name = match_html.find("a").get_text().split(" - ")[1]

                    score_text = re.search(r"(\d+:\d+)", match_html.find_all("td")[-2].get_text()).group(1)
                    score = Score(
                        FOOTBALLBETTINGTIPS_NAME,
                        score_text.split(":")[0],
                        score_text.split(":")[1],
                    )

                    try:
                        odds = Odds(
                            home=match_html.find_all(class_="desktop")[0].get_text().strip(),
                            draw=match_html.find_all(class_="desktop")[1].get_text().strip(),
                            away=match_html.find_all(class_="desktop")[2].get_text().strip(),
                        )
                    except Exception as exc:
                        log_event(
                            logger,
                            event="match.odds_unavailable",
                            outcome="warning",
                            reason_code="odds_parse_failed",
                            level=30,
                            message=f"Could not parse odds for {home_team_name} vs {away_team_name}: {exc}",
                            source_key=FOOTBALLBETTINGTIPS_NAME,
                            url=url,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
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
                    logger.exception(
                        "Skipping malformed FootballBettingTips candidate on %s",
                        url,
                        extra={
                            "event": "match.skipped",
                            "outcome": "error",
                            "reason_code": "candidate_parse_failed",
                            "source_key": FOOTBALLBETTINGTIPS_NAME,
                            "url": url,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )
                    continue

        except Exception as e:
            logger.exception(
                "Failed to parse FootballBettingTips page %s",
                url,
                extra={
                    "event": "source.page.failed",
                    "outcome": "error",
                    "reason_code": "page_parse_failed",
                    "source_key": FOOTBALLBETTINGTIPS_NAME,
                    "url": url,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
