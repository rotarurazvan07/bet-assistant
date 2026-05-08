from scrape_kit import browser, get_logger
import time
logger = get_logger(__name__)
from datetime import date, timedelta
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

BETEXPLORER_URL = ""
BETEXPLORER_NAME = "betexplorer"
MAX_CONCURRENCY = 1


class BetExplorerFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        urls = []
        max_attempts = 3                   # one extra top‑level attempt
        for attempt in range(1, max_attempts + 1):
            try:
                # Attempt to pass them; if the helper doesn't support it, remove
                try:
                    with browser(
                        solve_cloudflare=True,
                        interactive=True,
                        disable_resources=False,
                        headless=True
                    ) as session:
                        # Give the browser a moment after Cloudflare solving
                        time.sleep(3)

                        hide_finished = False
                        for date_str in [
                            (date.today() + timedelta(days=i)).strftime("%Y%m%d")
                            for i in range(7)
                        ]:
                            date_urls = self._scrape_date(
                                session, date_str, hide_finished
                            )
                            if not hide_finished and date_urls:   # only mark True once it actually worked
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
                    time.sleep(10)          # longer cooldown between whole sessions

            except Exception as outer_e:
                logger.exception("Outer setup error attempt %d: %s", attempt, outer_e)
                if attempt == max_attempts:
                    logger.critical("Outer setup failed permanently.")
                time.sleep(10)

        return []

    # ------------------------------------------------------------------
    # Private scraper for a single date – heavily fortified
    # ------------------------------------------------------------------
    def _scrape_date(self, session, date_str, hide_finished):
        year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
        url = f"https://www.betexplorer.com/?year={year}&month={month}&day={day}"

        # Two inner attempts per date (network hiccups, slow CI)
        for attempt in range(1, 4):          # now up to 3
            try:
                logger.info(
                    "Fetching %s (attempt %d/%d)", date_str, attempt, 3
                )

                # ---------- Step 1: Navigate with DOM-ready wait (with retries) ----------
                fetch_ok = False
                for nav_retry in range(1, 4):  # Up to 3 navigation retries
                    try:
                        if nav_retry == 1:
                            session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                        else:
                            # On retries, do a full reload
                            session.page.reload(wait_until="domcontentloaded", timeout=60000)

                        # Check if we got an error page by looking at the HTML
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
                        error_str = str(nav_error)
                        logger.warning(
                            "Navigation error on %s (nav retry %d/%d): %s",
                            date_str, nav_retry, 4, error_str
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
                        return []  # Give up on this date

                # ---------- Step 2: Wait for meaningful content to appear ----------
                # Wait until at least one match link is present (up to 30s)
                try:
                    session.page.wait_for_selector(
                        'a[data-live-cell="matchlink"]',
                        state="attached",
                        timeout=30000,
                    )
                except Exception:
                    logger.warning(
                        "No match links detected after 30s, will still continue"
                    )

                # ---------- Step 3: Let page fully settle ----------
                # (your original mutation observer, but with more relaxed hard cap)
                session.execute_script("""
                    (function() {
                        return new Promise((resolve) => {
                            var prevHTML = document.body.innerHTML.length;
                            var hardCap = setTimeout(() => { resolve(); }, 18000);   // was 8s
                            var idleTimer = setTimeout(() => { clearTimeout(hardCap); resolve(); }, 4000);  // was 2s
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
                # safety nap after settle (CI machines can be absurdly slow)
                time.sleep(2)

                # ---------- Step 4: Hide finished matches (only first date) ----------
                if not hide_finished:
                    # Wait for the button to become clickable
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
                                        var idleTimer = setTimeout(() => { observer.disconnect(); clearTimeout(hardCap); resolve(true); }, 3000);  // was 1s
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
                        time.sleep(3)       # extra wait for UI re‑render
                    except Exception as hide_err:
                        logger.warning("Could not hide finished matches, continuing: %s", hide_err)

                # ---------- Step 5: The working scroll logic (unchanged) ----------
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
                # Give the DOM a final breather
                time.sleep(2)

                # ---------- Step 6: Retrieve page source and verify size ----------
                html = session.page.content()
                if len(html) < 8000:   # raised from 5000 – CI might load slower
                    logger.warning(
                        "Page content too small (%d bytes), retrying...", len(html)
                    )
                    if attempt < 3:
                        time.sleep(5)
                        continue

                # ---------- Step 7: Parse and return links ----------
                soup = BeautifulSoup(html, "html.parser")
                links = list(
                    set(
                        f"https://www.betexplorer.com{a['href']}"
                        for a in soup.find_all('a', {'data-live-cell': 'matchlink'})
                    )
                )

                # >>> ADD THIS RETRY LOGIC <<<
                if len(links) == 0:
                    logger.warning(
                        "%s attempt %d produced 0 links – retrying after cooldown",
                        date_str, attempt
                    )
                    if attempt < 3:
                        time.sleep(10)          # longer before retry
                        continue                 # try again from the top of the loop
                    else:
                        logger.error(
                            "Date %s still 0 links after %d attempts, giving up",
                            date_str, attempt
                        )
                # >>> END OF ADDITION <<<

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
                time.sleep(8)   # longer cooldown between retries on the same date

        return []

    def get_matches(self, urls) -> None:
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
                        logger.warning("Fetch error (retrying fetch): %s", fetch_err)
                        time.sleep(4)
                        try:
                            session.fetch(url, wait_until="domcontentloaded", timeout=60000)
                        except Exception:
                            pass
                    
                        session.execute_script("""
    (function() {
        // Click "I Accept" button (case-insensitive)
        var elements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]');
        for (var el of elements) {
            if (el.textContent.trim().toLowerCase().includes('i accept') || 
                el.value?.toLowerCase().includes('i accept')) {
                el.click();
                break;
            }
        }

        // Wait for content to settle
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
                        logger.warning("Critical selectors not found, still trying")
                        continue

                    try:
                        session.page.wait_for_selector("#bettype_menu_best", state="attached", timeout=30000)
                        logger.debug("Odds tab menu found")
                    except Exception:
                        logger.warning("Odds tab menu (#bettype_menu_best) not found — odds will be empty")
                        continue

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    home_team = soup.select_one(".list-details__item:nth-child(1) .list-details__item__title").text.strip()
                    away_team = soup.select_one(".list-details__item:nth-child(3) .list-details__item__title").text.strip()

                    date_str = soup.select_one("#match-date").text.strip()
                    date_part = date_str.split(" - ")[0]  # "11.05.2026"
                    day, month, year = map(int, date_part.split("."))
                    match_date = datetime(year, month, day, 0, 0, 0)

                    odds_1 = odds_X = odds_2 = odds_btts_y = odds_btts_n = odds_dc_1x = odds_dc_12 = odds_dc_x2 = None
                    try:
                        logger.info("Extracting 1x2 Odds")
                        odds_1 = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_X = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("Failed to scrape 1X2 odds")

                    try:
                        logger.info("Extracting BTTS Odds")

                        click_by_selector(session, '#bettype_menu_best li[title="Both Teams To Score"]')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_btts_y = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_btts_n = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                    except Exception:
                        logger.warning("Failed to scrape BTTS odds")

                    try:
                        logger.info("Extracting DC Odds")
                        click_by_selector(session, '#bettype_menu_best li[title="Double Chance"]')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_dc_1x = soup.find_all("div", class_="oddsComparisonAll__average_text")[0].text.strip()
                        odds_dc_12 = soup.find_all("div", class_="oddsComparisonAll__average_text")[1].text.strip()
                        odds_dc_x2 = soup.find_all("div", class_="oddsComparisonAll__average_text")[2].text.strip()
                    except Exception:
                        logger.warning("Failed to scrape DC odds")

                    try:
                        logger.info("Extracting Over/Under Odds")
                        click_by_selector(session, '#bettype_menu_best li[title="Over/Under"]')
                        click_by_selector(session, '.oddsComparison__ul.bestOddsComparison li#all')
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        odds_ou = extract_match_odds_over_under(soup)
                    except Exception:
                        logger.warning("Failed to scrape O/U odds")

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
                    logger.info(odds)
                    self.add_match(
                        Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_date,
                            predictions=None,
                            odds=odds
                        )
                    )
                except Exception as e:
                    logger.error(f"Error parsing {url} {str(e)}")
                    continue

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
                    }}, 30000);   // 30s hard cap (was 10s)

                    var idleTimer = setTimeout(() => {{
                        observer.disconnect();
                        clearTimeout(hardCap);
                        resolve(true);
                    }}, 5000);    // 5s idle (was 1s)

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
