from scrape_kit import browser, get_logger
import time
logger = get_logger(__name__)
from datetime import date, timedelta
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

BETEXPLORER_URL = ""
BETEXPLORER_NAME = "betexplorer"
MAX_CONCURRENCY = 10


class BetExplorerFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)
        self._add_match_lock = threading.Lock()

    def get_matches_urls(self):
        urls = []
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    with browser(
                        solve_cloudflare=True,
                        interactive=True,
                        disable_resources=False,
                        headless=True
                    ) as session:
                        time.sleep(3)

                        hide_finished = False
                        for date_str in [
                            (date.today() + timedelta(days=i)).strftime("%Y%m%d")
                            for i in range(7)
                        ]:
                            date_urls = self._scrape_date(
                                session, date_str, hide_finished
                            )
                            if not hide_finished and date_urls:
                                hide_finished = True
                            urls.extend(date_urls)
                            logger.info(
                                "Found %d match URLs on %s (total: %d)",
                                len(date_urls), date_str, len(urls)
                            )
                        logger.info("Total URLs found: %d", len(urls))
                        return list(set(urls))

                except Exception as e:
                    logger.error("Attempt %d failed: %s", attempt, e)
                    if attempt == max_attempts:
                        logger.critical("All scraping attempts failed.")
                    time.sleep(10)

            except Exception as outer_e:
                logger.exception("Outer setup error attempt %d: %s", attempt, outer_e)
                if attempt == max_attempts:
                    logger.critical("Outer setup failed permanently.")
                time.sleep(10)

        return []

    def _scrape_date(self, session, date_str, hide_finished):
        year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
        url = f"https://www.betexplorer.com/?year={year}&month={month}&day={day}"

        for attempt in range(1, 4):
            try:
                logger.info("Fetching %s (attempt %d/%d)", date_str, attempt, 3)

                fetch_ok = False
                for nav_retry in range(1, 4):
                    try:
                        if nav_retry == 1:
                            session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                        else:
                            session.page.reload(wait_until="domcontentloaded", timeout=60000)

                        html_check = session.page.content()
                        if "ERR_HTTP_RESPONSE_CODE_FAILURE" not in html_check and len(html_check) > 5000:
                            fetch_ok = True
                            logger.info("Successfully loaded %s on nav retry %d", date_str, nav_retry)
                            break
                        else:
                            logger.warning(
                                "Got bad response on nav retry %d for %s, content length: %d",
                                nav_retry, date_str, len(html_check)
                            )
                            time.sleep(5)
                    except Exception as nav_error:
                        logger.warning(
                            "Navigation error on %s (nav retry %d/%d): %s",
                            date_str, nav_retry, 4, str(nav_error)
                        )
                        time.sleep(5)
                        if nav_retry == 3:
                            logger.error("Failed to load %s after 3 navigation retries", date_str)
                            break

                if not fetch_ok:
                    logger.warning("Skipping %s attempt %d due to persistent HTTP errors", date_str, attempt)
                    if attempt < 3:
                        time.sleep(10)
                        continue
                    else:
                        return []

                try:
                    session.page.wait_for_selector(
                        'a[data-live-cell="matchlink"]',
                        state="attached",
                        timeout=30000,
                    )
                except Exception:
                    logger.warning("No match links detected after 30s, will still continue")

                session.execute_script("""
                    (function() {
                        return new Promise((resolve) => {
                            var prevHTML = document.body.innerHTML.length;
                            var hardCap = setTimeout(() => { resolve(); }, 18000);
                            var idleTimer = setTimeout(() => { clearTimeout(hardCap); resolve(); }, 4000);
                            var observer = new MutationObserver(() => {
                                var newHTML = document.body.innerHTML.length;
                                if (newHTML !== prevHTML) {
                                    prevHTML = newHTML;
                                    clearTimeout(idleTimer);
                                    idleTimer = setTimeout(() => { clearTimeout(hardCap); resolve(); }, 4000);
                                }
                            });
                            observer.observe(document.body, {
                                childList: true, subtree: true, attributes: true, characterData: true
                            });
                        });
                    })()
                """)
                time.sleep(2)

                if not hide_finished:
                    try:
                        session.page.wait_for_selector(
                            'li#sOption a#sCurrent',
                            state="visible",
                            timeout=15000,
                        )
                        clicked = session.execute_script("""
                            (function() {
                                return new Promise((resolve) => {
                                    try {
                                        var button = document.querySelector('li#sOption a#sCurrent');
                                        if (!button) { resolve(false); return; }
                                        button.click();

                                        var prevHTML = document.body.innerHTML.length;
                                        var hardCap = setTimeout(() => { observer.disconnect(); resolve(true); }, 18000);
                                        var idleTimer = setTimeout(() => { observer.disconnect(); clearTimeout(hardCap); resolve(true); }, 3000);
                                        var observer = new MutationObserver(() => {
                                            var newHTML = document.body.innerHTML.length;
                                            if (newHTML !== prevHTML) {
                                                prevHTML = newHTML;
                                                clearTimeout(idleTimer);
                                                idleTimer = setTimeout(() => { observer.disconnect(); clearTimeout(hardCap); resolve(true); }, 3000);
                                            }
                                        });
                                        observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
                                    } catch(e) { resolve(false); }
                                });
                            })()
                        """)
                        logger.debug("Hide finished button clicked: %s", clicked)
                        time.sleep(3)
                    except Exception as hide_err:
                        logger.warning("Could not hide finished matches, continuing: %s", hide_err)

                before_scroll = len(session.page.query_selector_all('a[data-live-cell="matchlink"]'))
                logger.debug("%s links before scroll: %d", date_str, before_scroll)

                # ⚠️ DO NOT MODIFY THIS SCROLL BLOCK ⚠️
                session.execute_script("""
                    (function() {
                        return new Promise((resolve) => {
                            function cycle() {
                                var maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                document.body.scrollTop = maxScroll;
                                document.documentElement.scrollTop = maxScroll;

                                var prevHeight = maxScroll;

                                var idleTimeout = setTimeout(() => {
                                    observer.disconnect();
                                    resolve();
                                }, 10000);

                                var observer = new MutationObserver(() => {
                                    var newHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                    if (newHeight > prevHeight) {
                                        clearTimeout(idleTimeout);
                                        observer.disconnect();
                                        setTimeout(cycle, 1000);
                                    }
                                });

                                observer.observe(document.body, { childList: true, subtree: true });
                            }

                            cycle();
                        });
                    })()
                """)
                time.sleep(2)

                html = session.page.content()
                if len(html) < 8000:
                    logger.warning("Page content too small (%d bytes), retrying...", len(html))
                    if attempt < 3:
                        time.sleep(5)
                        continue

                soup = BeautifulSoup(html, "html.parser")
                links = list(
                    set(
                        f"https://www.betexplorer.com{a['href']}"
                        for a in soup.find_all('a', {'data-live-cell': 'matchlink'})
                    )
                )

                if len(links) == 0:
                    logger.warning(
                        "%s attempt %d produced 0 links – retrying after cooldown",
                        date_str, attempt
                    )
                    if attempt < 3:
                        time.sleep(10)
                        continue
                    else:
                        logger.error("Date %s still 0 links after %d attempts, giving up", date_str, attempt)

                logger.debug(
                    "%s links after scroll: %d (was %d before)",
                    date_str, len(links), before_scroll,
                )
                return links

            except Exception as e:
                logger.warning("Date %s attempt %d failed: %s", date_str, attempt, e)
                if attempt == 3:
                    logger.error("Skipping %s after %d failed attempts", date_str, 3)
                    return []
                time.sleep(8)

        return []

    def _process_url_batch(self, urls: list) -> None:
        """Process a batch of URLs in a single browser session (runs in its own thread)."""
        thread_name = threading.current_thread().name
        logger.info("[%s] Starting batch of %d URLs", thread_name, len(urls))

        with browser(
            solve_cloudflare=True,
            interactive=True,
            disable_resources=False,
            headless=True
        ) as session:
            for url in urls:
                try:
                    # ---------- Step 1: Navigate with DOM ready ----------
                    try:
                        session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                    except Exception as fetch_err:
                        logger.warning("[%s] Fetch error (retrying fetch): %s", thread_name, fetch_err)
                        time.sleep(4)
                        try:
                            session.fetch(url, wait_until="domcontentloaded", timeout=60000)
                        except Exception:
                            pass

                        session.execute_script("""
(function() {
    var elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
    for (var el of elements) {
        if (el.textContent.trim().toLowerCase().includes('i accept') ||
            el.value?.toLowerCase().includes('i accept')) {
            el.click();
            break;
        }
    }

    return new Promise((resolve) => {
        function cycle() {
            var maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
            document.body.scrollTop = maxScroll;
            document.documentElement.scrollTop = maxScroll;

            var prevHeight = maxScroll;

            var idleTimeout = setTimeout(() => {
                observer.disconnect();
                resolve();
            }, 10000);

            var observer = new MutationObserver(() => {
                var newHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                if (newHeight > prevHeight) {
                    clearTimeout(idleTimeout);
                    observer.disconnect();
                    setTimeout(cycle, 1000);
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });
        }

        cycle();
    });
})()
""")

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
                        logger.warning("[%s] Odds tab menu (#bettype_menu_best) not found — odds will be empty: %s", thread_name, url)
                        continue

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    home_team = soup.select_one(".list-details__item:nth-child(1) .list-details__item__title").text.strip()
                    away_team = soup.select_one(".list-details__item:nth-child(3) .list-details__item__title").text.strip()

                    date_str = soup.select_one("#match-date").text.strip()
                    date_part = date_str.split(" - ")[0]
                    day, month, year = map(int, date_part.split("."))
                    match_date = datetime(year, month, day, 0, 0, 0)

                    odds_1 = odds_X = odds_2 = odds_btts_y = odds_btts_n = odds_dc_1x = odds_dc_12 = odds_dc_x2 = None
                    odds_ou = {}

                    try:
                        logger.info("[%s] Extracting 1x2 Odds", thread_name)
                        odds_1 = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_X = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape 1X2 odds", thread_name)

                    try:
                        logger.info("[%s] Extracting BTTS Odds", thread_name)
                        click_by_selector(session, '#bettype_menu_best li[title="Both Teams To Score"]')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_btts_y = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_btts_n = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape BTTS odds", thread_name)

                    try:
                        logger.info("[%s] Extracting DC Odds", thread_name)
                        click_by_selector(session, '#bettype_menu_best li[title="Double Chance"]')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_dc_1x = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_dc_12 = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_dc_x2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("[%s] Failed to scrape DC odds", thread_name)

                    try:
                        logger.info("[%s] Extracting Over/Under Odds", thread_name)
                        click_by_selector(session, '#bettype_menu_best li[title="Over/Under"]')
                        click_by_selector(session, '.oddsComparison__ul.bestOddsComparison li#all')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_ou = extract_match_odds_over_under(soup)
                    except Exception:
                        logger.warning("[%s] Failed to scrape O/U odds", thread_name)

                    odds = Odds(
                        home=odds_1,
                        draw=odds_X,
                        away=odds_2,
                        over_05=odds_ou.get("over_05"),
                        under_05=odds_ou.get("under_05"),
                        over_15=odds_ou.get("over_15"),
                        under_15=odds_ou.get("under_15"),
                        over_25=odds_ou.get("over_25"),
                        under_25=odds_ou.get("under_25"),
                        over_35=odds_ou.get("over_35"),
                        under_35=odds_ou.get("under_35"),
                        over_45=odds_ou.get("over_45"),
                        under_45=odds_ou.get("under_45"),
                        btts_y=odds_btts_y,
                        btts_n=odds_btts_n,
                        dc_1x=odds_dc_1x,
                        dc_12=odds_dc_12,
                        dc_x2=odds_dc_x2,
                    )
                    logger.info("[%s] %s", thread_name, odds)

                    match = Match(
                        home_team=home_team,
                        away_team=away_team,
                        datetime=match_date,
                        predictions=None,
                        odds=odds
                    )
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
            # Fast path: single browser session, no threading overhead
            self._process_url_batch(urls)
            return

        # Split URLs into roughly equal chunks — one chunk per worker
        chunk_size = max(1, len(urls) // MAX_CONCURRENCY)
        # Any remainder goes to the last chunk (not a separate tiny batch)
        chunks = [urls[i:i + chunk_size] for i in range(0, len(urls), chunk_size)]
        # If we got more chunks than workers (due to rounding), merge the tail into the last one
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


def extract_match_odds_over_under(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    result = {
        "over_05": None, "under_05": None,
        "over_15": None, "under_15": None,
        "over_25": None, "under_25": None,
        "over_35": None, "under_35": None,
        "over_45": None, "under_45": None,
    }
    handicap_map = {
        "0.50": ("over_05", "under_05"),
        "1.50": ("over_15", "under_15"),
        "2.50": ("over_25", "under_25"),
        "3.50": ("over_35", "under_35"),
        "4.50": ("over_45", "under_45"),
    }
    handicap_sections = soup.find_all("div", {"data-all-handicap": True})
    for section in handicap_sections:
        handicap = section.get("data-all-handicap")
        if handicap not in handicap_map:
            continue
        over_key, under_key = handicap_map[handicap]
        first_row = section.find("div", class_="oddsComparisonAll__rowBookie")
        if not first_row:
            continue
        odd_cells = first_row.find_all("div", attrs={"data-odd": True})
        if len(odd_cells) >= 2:
            result[over_key] = odd_cells[0].get("data-odd")
            result[under_key] = odd_cells[1].get("data-odd")

    return result


def click_by_selector(session, selector):
    """
    Click an odds tab <li> by its title attribute within #bettype_menu_best.
    Now with vastly longer timeouts.
    """
    return session.execute_script(
        f"""
        (function() {{
            return new Promise((resolve) => {{
                try {{
                    var el = document.querySelector('{selector}');
                    if (!el) {{
                        resolve(false);
                        return;
                    }}

                    el.click();

                    var prevHeight = document.documentElement.scrollHeight;
                    var prevHTML = document.body.innerHTML.length;

                    var hardCap = setTimeout(() => {{
                        observer.disconnect();
                        resolve(true);
                    }}, 30000);

                    var idleTimer = setTimeout(() => {{
                        observer.disconnect();
                        clearTimeout(hardCap);
                        resolve(true);
                    }}, 5000);

                    var observer = new MutationObserver(() => {{
                        var newHeight = document.documentElement.scrollHeight;
                        var newHTML = document.body.innerHTML.length;

                        if (newHeight !== prevHeight || newHTML !== prevHTML) {{
                            prevHeight = newHeight;
                            prevHTML = newHTML;
                            clearTimeout(idleTimer);
                            idleTimer = setTimeout(() => {{
                                observer.disconnect();
                                clearTimeout(hardCap);
                                resolve(true);
                            }}, 5000);
                        }}
                    }});

                    observer.observe(document.body, {{
                        childList: true,
                        subtree: true,
                        attributes: true,
                        characterData: true
                    }});

                }} catch(e) {{
                    resolve(false);
                }}
            }});
        }})()
        """
    )
