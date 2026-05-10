import time

from scrape_kit import browser, get_logger

logger = get_logger(__name__)
import contextlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

BETEXPLORER_URL = ""
BETEXPLORER_NAME = "betexplorer"
MAX_CONCURRENCY = 10
NUM_DAYS_AHEAD = 3


class BetExplorerFinder(BaseMatchFinder):
    TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)
        self._add_match_lock = threading.Lock()

    def get_matches_urls(self):
        urls = []

        for date_str in [(date.today() + timedelta(days=i)).strftime("%Y%m%d") for i in range(NUM_DAYS_AHEAD)]:
            year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
            url = f"https://www.betexplorer.com/?year={year}&month={month}&day={day}"

            try:
                with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
                    session.fetch(url, wait_until="domcontentloaded", timeout=90000)

                    session.scroll_to_bottom()

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    links = list(
                        {
                            f"https://www.betexplorer.com{a['href']}"
                            for row in soup.find_all("li", class_="showHide")
                            for status in row.find_all("span", {"data-live-cell": "time"})
                            for a in row.find_all("a", {"data-live-cell": "matchlink"})
                            if re.match(r"^\d{2}:\d{2}$", status.text.strip())
                        }
                    )

                    urls.extend(links)
                    logger.info("Found %d match URLs on %s (total: %d)", len(links), date_str, len(urls))

            except Exception as e:
                logger.error("Failed to scrape %s: %s", date_str, e)
                continue

        logger.info("Total URLs found: %d", len(urls))
        return list(set(urls))

    def _process_url_batch(self, urls: list) -> None:
        """Process a batch of URLs in a single browser session (runs in its own thread)."""
        thread_name = threading.current_thread().name
        logger.info("[%s] Starting batch of %d URLs", thread_name, len(urls))

        with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
            for url in urls:
                try:
                    try:
                        session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                    except Exception as fetch_err:
                        logger.warning("[%s] Fetch error (retrying fetch): %s", thread_name, fetch_err)
                        time.sleep(4)
                        with contextlib.suppress(Exception):
                            session.fetch(url, wait_until="domcontentloaded", timeout=60000)

                    try:
                        session.page.wait_for_selector(".list-details__item__title", state="attached", timeout=30000)
                        session.page.wait_for_selector("#match-date", state="attached", timeout=30000)
                    except Exception:
                        logger.warning("[%s] Critical selectors not found, skipping: %s", thread_name, url)
                        continue

                    try:
                        session.page.wait_for_selector("#bettype_menu_best", state="attached", timeout=30000)
                        logger.debug("[%s] Odds tab menu found", thread_name)
                    except Exception:
                        logger.warning(
                            "[%s] Odds tab menu (#bettype_menu_best) not found — odds will be empty: %s", thread_name, url
                        )
                        continue

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    home_team = soup.select_one(".list-details__item:nth-child(1) .list-details__item__title").text.strip()
                    away_team = soup.select_one(".list-details__item:nth-child(3) .list-details__item__title").text.strip()

                    date_str = soup.select_one("#match-date").text.strip()
                    date_part, time_part = date_str.split(" - ")
                    day, month, year = map(int, date_part.split("."))
                    hour, minute = map(int, time_part.split(":"))
                    match_date = datetime(year, month, day, hour, minute)

                    odds_1 = odds_X = odds_2 = odds_btts_y = odds_btts_n = odds_dc_1x = odds_dc_12 = odds_dc_x2 = None
                    odds_over05 = odds_under05 = odds_over15 = odds_under15 = odds_over25 = odds_under25 = odds_over35 = (
                        odds_under35
                    ) = odds_over45 = odds_under45 = None

                    try:
                        logger.info("[%s] Extracting 1x2 Odds", thread_name)
                        assert session.click('#bettype_menu_best li[title="1X2"]'), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        odds_1 = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_X = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape 1X2 odds", thread_name)

                    try:
                        logger.info("[%s] Extracting BTTS Odds", thread_name)
                        assert session.click('#bettype_menu_best li[title="Both Teams To Score"]'), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        odds_btts_y = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_btts_n = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape BTTS odds", thread_name)

                    try:
                        logger.info("[%s] Extracting DC Odds", thread_name)
                        assert session.click('#bettype_menu_best li[title="Double Chance"]'), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        odds_dc_1x = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_dc_12 = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_dc_x2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape DC odds", thread_name)

                    try:
                        logger.info("[%s] Extracting Over/Under Odds", thread_name)
                        assert session.click('#bettype_menu_best li[title="Over/Under"]'), "Click failed"
                        assert session.click(".oddsComparison__ul.bestOddsComparison li#all"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        h = {
                            s.get("data-all-handicap"): s.find("div", class_="oddsComparisonAll__rowBookie")
                            for s in soup.find_all("div", {"data-all-handicap": True})
                        }
                        c = {k: v.find_all("div", attrs={"data-odd": True}) for k, v in h.items()}
                        odds_over05, odds_under05 = c["0.50"][0].get("data-odd"), c["0.50"][1].get("data-odd")
                        odds_over15, odds_under15 = c["1.50"][0].get("data-odd"), c["1.50"][1].get("data-odd")
                        odds_over25, odds_under25 = c["2.50"][0].get("data-odd"), c["2.50"][1].get("data-odd")
                        odds_over35, odds_under35 = c["3.50"][0].get("data-odd"), c["3.50"][1].get("data-odd")
                        odds_over45, odds_under45 = c["4.50"][0].get("data-odd"), c["4.50"][1].get("data-odd")
                    except Exception:
                        logger.warning("[%s] Failed to scrape O/U odds", thread_name)

                    odds = Odds(
                        home=odds_1,
                        draw=odds_X,
                        away=odds_2,
                        over_05=odds_over05,
                        under_05=odds_under05,
                        over_15=odds_over15,
                        under_15=odds_under15,
                        over_25=odds_over25,
                        under_25=odds_under25,
                        over_35=odds_over35,
                        under_35=odds_under35,
                        over_45=odds_over45,
                        under_45=odds_under45,
                        btts_y=odds_btts_y,
                        btts_n=odds_btts_n,
                        dc_1x=odds_dc_1x,
                        dc_12=odds_dc_12,
                        dc_x2=odds_dc_x2,
                    )
                    logger.info("[%s] %s", thread_name, odds)

                    match = Match(home_team=home_team, away_team=away_team, datetime=match_date, predictions=None, odds=odds)
                    with self._add_match_lock:
                        self.add_match(match)

                except Exception as e:
                    logger.error("[%s] Error parsing %s: %s", thread_name, url, str(e))
                    continue

        logger.info("[%s] Batch complete", thread_name)

    def get_matches(self, urls) -> None:
        if not urls:
            return

        if MAX_CONCURRENCY <= 1:
            self._process_url_batch(urls)
            return

        chunk_size = max(1, len(urls) // MAX_CONCURRENCY)
        chunks = [urls[i : i + chunk_size] for i in range(0, len(urls), chunk_size)]
        while len(chunks) > MAX_CONCURRENCY:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

        logger.info(
            "Parallelizing %d URLs across %d workers (chunks: %s)",
            len(urls),
            len(chunks),
            [len(c) for c in chunks],
        )

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="betexp") as executor:
            futures = {executor.submit(self._process_url_batch, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    future.result()
                    logger.info("Worker %d finished successfully", chunk_idx)
                except Exception as e:
                    logger.error("Worker %d raised an exception: %s", chunk_idx, e)
