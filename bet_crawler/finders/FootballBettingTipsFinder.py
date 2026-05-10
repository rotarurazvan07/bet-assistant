from scrape_kit import get_logger

logger = get_logger(__name__)
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, browser, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "footballbettingtips"
MAX_CONCURRENCY = 1


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        with browser(interactive=True, solve_cloudflare=True, disable_resources=False, headless=True) as session:
            session.fetch(FOOTBALLBETTINGTIPS_URL, timeout=90000, wait_until="domcontentloaded")

            try:
                session.page.wait_for_selector("table.top_tipsters", state="attached", timeout=30000)
            except Exception:
                logger.warning("Content selector not found after 30s")

            html = session.page.content()

        soup = BeautifulSoup(html, "html.parser")

        if len(html) < 5000:
            logger.warning("Page too small (%d bytes), likely blocked", len(html))
            return []

        return [FOOTBALLBETTINGTIPS_URL + a.find("a")["href"] for a in soup.find_all("h3")[:2] if a.find("a")]

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        import time

        max_retries = 5
        retry_delay = 5  # seconds between retries

        for retry in range(1, max_retries + 1):
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
                        logger.error(f"SKIPPED [{url}]: {e}")
                        continue

                # Success - break retry loop
                break

            except Exception as e:
                if retry < max_retries:
                    logger.warning(f"Parse error on {url} (retry {retry}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Error parsing {url} after {max_retries} retries: {e}")
