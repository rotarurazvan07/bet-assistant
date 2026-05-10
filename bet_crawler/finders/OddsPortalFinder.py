import threading
import time

from scrape_kit import browser, get_logger

logger = get_logger(__name__)
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder
import contextlib

ODDSPORTAL_NAME = "oddsportal"
MAX_CONCURRENCY = 1
NUM_DAYS_AHEAD = 3


class OddsPortalFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)
        self._add_match_lock = threading.Lock()

    def get_matches_urls(self):
        urls = []

        for date_str in [(date.today() + timedelta(days=i)).strftime("%Y%m%d") for i in range(NUM_DAYS_AHEAD)]:
            url = f"https://www.oddsportal.com/matches/football/{date_str}/"
            try:
                with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
                    session.fetch(url, wait_until="domcontentloaded", timeout=90000)

                    session.scroll_to_bottom()

                    soup = BeautifulSoup(session.page.content(), "html.parser")

                    links = list(
                        dict.fromkeys(
                            f"https://www.oddsportal.com{a['href']}"
                            for a in soup.find_all("a", href=True)
                            if "/football/h2h/" in a["href"]
                            for time_div in a.find_all("div", {"data-testid": "time-item"})
                            for p in time_div.find_all("p")
                            if re.match(r"^\d{2}:\d{2}$", p.text.strip())
                        )
                    )
                    urls.extend(links)
                    logger.info("Found %d match URLs on %s (total: %d)", len(links), date_str, len(urls))

            except Exception as e:
                logger.error("Failed to scrape %s: %s", date_str, e)
                continue

        logger.info("Total URLs found: %d", len(urls))
        return list(set(urls))

    def _process_url_batch(self, urls: list) -> None:
        thread_name = threading.current_thread().name
        logger.info("[%s] Starting batch of %d URLs", thread_name, len(urls))

        with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
            for url in urls:
                try:
                    try:
                        session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                    except Exception as e:
                        logger.warning("[%s] Fetch error (retrying): %s", thread_name, e)
                        time.sleep(4)
                        with contextlib.suppress(Exception):
                            session.fetch(url, wait_until="domcontentloaded", timeout=60000)

                    soup = BeautifulSoup(session.page.content(), "html.parser")

                    home_team = soup.select_one('[data-testid="game-host"] a').text.strip()
                    away_team = soup.select_one('[data-testid="game-guest"] a').text.strip()
                    match_date = datetime.strptime(
                        soup.select_one('[data-testid="game-time-item"] p:nth-of-type(2)').text.strip().rstrip(","), "%d %B %Y"
                    ).replace(hour=0, minute=0, second=0)

                    odds_1, odds_X, odds_2 = None, None, None
                    odds_btts_y, odds_btts_n = None, None
                    odds_dc_1x, odds_dc_12, odds_dc_x2 = None, None, None
                    odds_over05, odds_under05 = None, None
                    odds_over15, odds_under15 = None, None
                    odds_over25, odds_under25 = None, None
                    odds_over35, odds_under35 = None, None
                    odds_over45, odds_under45 = None, None

                    try:
                        logger.info("[%s] Extracting 1X2 odds", thread_name)
                        assert session.click("li.odds-item", "1X2"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_1 = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_X = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_2 = cells[2].find("a", class_="odds-link").get_text(strip=True)
                        odds_1 = odds_1 if odds_1 != "-" else None
                        odds_X = odds_X if odds_X != "-" else None
                        odds_2 = odds_2 if odds_2 != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape 1X2 odds", thread_name)

                    try:
                        logger.info("[%s] Extracting BTTS odds", thread_name)
                        assert session.click("li.odds-item", "Both Teams to Score"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_btts_y = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_btts_n = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_btts_y = odds_btts_y if odds_btts_y != "-" else None
                        odds_btts_n = odds_btts_n if odds_btts_n != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape BTTS odds", thread_name)

                    try:
                        logger.info("[%s] Extracting DC odds", thread_name)
                        assert session.click("li.odds-item", "Double Chance"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_dc_1x = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_12 = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_x2 = cells[2].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_1x = odds_dc_1x if odds_dc_1x != "-" else None
                        odds_dc_12 = odds_dc_12 if odds_dc_12 != "-" else None
                        odds_dc_x2 = odds_dc_x2 if odds_dc_x2 != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape DC odds", thread_name)

                    try:
                        logger.info("[%s] Extracting O/U odds", thread_name)
                        assert session.click("li.odds-item", "Over/Under"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        for row in soup.find_all("div", {"data-testid": "over-under-collapsed-row"}):
                            name = row.find("div", {"data-testid": "over-under-collapsed-option-box"}).get_text(strip=True)
                            conts = row.find_all("div", {"data-testid": "odd-container-default"})
                            over = conts[0].find("p").get_text(strip=True)
                            under = conts[1].find("p").get_text(strip=True)
                            if "+0.5" in name:
                                odds_over05 = over if over != "-" else None
                                odds_under05 = under if under != "-" else None
                            if "+1.5" in name:
                                odds_over15 = over if over != "-" else None
                                odds_under15 = under if under != "-" else None
                            if "+2.5" in name:
                                odds_over25 = over if over != "-" else None
                                odds_under25 = under if under != "-" else None
                            if "+3.5" in name:
                                odds_over35 = over if over != "-" else None
                                odds_under35 = under if under != "-" else None
                            if "+4.5" in name:
                                odds_over45 = over if over != "-" else None
                                odds_under45 = under if under != "-" else None
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

                    with self._add_match_lock:
                        self.add_match(
                            Match(home_team=home_team, away_team=away_team, datetime=match_date, predictions=None, odds=odds)
                        )

                except Exception as e:
                    logger.error("[%s] Error parsing %s: %s", thread_name, url, e)
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

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="oddsportal") as executor:
            futures = {executor.submit(self._process_url_batch, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    future.result()
                    logger.info("Worker %d finished successfully", chunk_idx)
                except Exception as e:
                    logger.error("Worker %d raised an exception: %s", chunk_idx, e)
