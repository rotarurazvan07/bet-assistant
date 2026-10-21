"""Match finder for legitpredict.com predictions."""

from bet_crawler.crawler_logging import exception_event, get_logger, log_event

logger = get_logger(__name__)

from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

LEGITPREDICT_URL = "https://legitpredict.com/correct-score?dt="
LEGITPREDICT_NAME = "legitpredict"
MAX_CONCURRENCY = 1


class LegitPredictFinder(BaseMatchFinder):
    """Scrapes legitpredict.com daily prediction listings."""

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        """Return legitpredict listing URLs."""
        urls = [
            f"{LEGITPREDICT_URL}{(datetime.now() + timedelta(days=i)).strftime('%d-%m-%Y')}"
            for i in range(self.num_days_ahead + 1)
        ]
        logger.info(f"{len(urls)} urls to scrape")
        return urls

    def get_matches(self, urls) -> None:
        """Scrape all legitpredict URLs and emit matches via callback."""
        scrape(
            urls,
            self._parse_page_with_log_context,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        """Parse one legitpredict page and emit matches via callback."""
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
                try:
                    tds = tr.find_all("td")
                    if len(tds) < 4:
                        log_event(
                            logger,
                            event="match.skipped",
                            outcome="warning",
                            reason_code="required_cells_missing",
                            level=30,
                            message=f"Skipping LegitPredict row with missing cells: {url}",
                            source_key="legitpredict",
                            url=url,
                        )
                        continue
                    home_team = tds[2].text.strip().split("VS")[0].strip()
                    away_team = tds[2].text.strip().split("VS")[1].strip()
                    score_parts = tds[3].text.strip().split("-")
                    time_parts = tds[0].text.strip().split(":")
                    # AC-10: skip unless both score parts and HH:MM parse
                    if len(score_parts) < 2 or len(time_parts) < 2:
                        log_event(
                            logger,
                            event="match.skipped",
                            outcome="warning",
                            reason_code="score_or_time_incomplete",
                            level=30,
                            message=f"Skipping LegitPredict row with incomplete score/time: {url}",
                            source_key="legitpredict",
                            url=url,
                        )
                        continue
                    try:
                        home_score = int(score_parts[0])
                        away_score = int(score_parts[1])
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                    except ValueError:
                        log_event(
                            logger,
                            event="match.skipped",
                            outcome="warning",
                            reason_code="score_or_time_invalid",
                            level=30,
                            message=f"Skipping LegitPredict row with invalid score/time: {url}",
                            source_key="legitpredict",
                            url=url,
                        )
                        continue
                    score = Score(LEGITPREDICT_NAME, home_score, away_score)

                    dt_obj = dt_obj.replace(hour=hour, minute=minute).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

                    self.add_match(
                        Match(home_team, away_team, dt_obj, score, None, None)
                    )

                except Exception as e:
                    exception_event(
                        logger,
                        event="match.parse.failed",
                        reason_code="candidate_parse_failed",
                        message=f"Skipping malformed LegitPredict candidate on {url}: {e}",
                        source_key="legitpredict",
                        url=url,
                    )
                    continue

        except Exception as e:
            exception_event(
                logger,
                event="source.page.failed",
                reason_code="page_parse_failed",
                message=f"Failed to parse LegitPredict page {url}: {e}",
                source_key="legitpredict",
                url=url,
            )
