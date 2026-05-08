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

ODDSPORTAL_URL = ""
ODDSPORTAL_NAME = "oddsportal"
MAX_CONCURRENCY = 1


class OddsPortalFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    # ------------------------------------------------------------------
    # Fortified URL scraper
    # ------------------------------------------------------------------
    def get_matches_urls(self):
        urls = []
        max_attempts = 3               # increased for CI
        for attempt in range(1, max_attempts + 1):
            try:
                # CI‑friendly browser arguments (remove if not supported)
                browser_kwargs = {
                    "solve_cloudflare": True,
                    "interactive": True,
                    "disable_resources": False,
                    "headless": True,
                }
                try:
                    browser_kwargs["browser_args"] = [
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-setuid-sandbox",
                    ]
                except Exception:
                    pass

                with browser(**browser_kwargs) as session:
                    # Give browser & Cloudflare solving a moment
                    time.sleep(3)

                    hide_finished = False
                    for date_str in [(date.today() + timedelta(days=i)).strftime("%Y%m%d") for i in range(6)]:
                        url = f"https://www.oddsportal.com/matches/football/{date_str}/"

                        # Up to 3 attempts per date
                        for fetch_attempt in range(1, 4):
                            try:
                                logger.info(f"Fetching {date_str} (attempt {fetch_attempt})")

                                # ------------------------------------------------------------------
                                # 1. Navigate with DOM content loaded
                                # ------------------------------------------------------------------
                                try:
                                    session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                                except Exception as fetch_error:
                                    logger.warning(f"Fetch had issue: {fetch_error}, continuing anyway")
                                    time.sleep(5)
                                    # Reload once if fetch failed
                                    try:
                                        session.page.reload(wait_until="domcontentloaded", timeout=60000)
                                    except Exception:
                                        pass

                                # ------------------------------------------------------------------
                                # 2. Wait for at least one match link to appear
                                # ------------------------------------------------------------------
                                try:
                                    session.page.wait_for_selector(
                                        'a[href*="/football/h2h/"]',
                                        state="attached",
                                        timeout=30000,
                                    )
                                except Exception:
                                    logger.warning("No h2h links found after 30s, still continuing")

                                # ------------------------------------------------------------------
                                # 3. Let the page fully settle (mutation observer, longer caps)
                                # ------------------------------------------------------------------
                                session.execute_script("""
                                    (function() {
                                        return new Promise((resolve) => {
                                            var prevHTML = document.body.innerHTML.length;
                                            var hardCap = setTimeout(() => { resolve(); }, 20000);   // was 10s
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
                                time.sleep(2)  # extra settle

                                # ------------------------------------------------------------------
                                # 4. Hide finished matches (first date only)
                                # ------------------------------------------------------------------
                                if not hide_finished:
                                    # Wait for the toggle to be visible
                                    try:
                                        session.page.wait_for_selector(
                                            '[data-testid="next-matches-show-finished-toggle"]',
                                            state="visible",
                                            timeout=15000,
                                        )
                                    except Exception:
                                        logger.debug("Hide finished toggle not visible, trying anyway")

                                    clicked = session.execute_script("""
                                        (function() {
                                            return new Promise((resolve) => {
                                                try {
                                                    var button = document.querySelector('[data-testid="next-matches-show-finished-toggle"]');
                                                    if (!button) { resolve(false); return; }
                                                    button.click();

                                                    var prevHTML = document.body.innerHTML.length;
                                                    var hardCap = setTimeout(() => { observer.disconnect(); resolve(true); }, 30000);
                                                    var idleTimer = setTimeout(() => { observer.disconnect(); clearTimeout(hardCap); resolve(true); }, 5000);
                                                    var observer = new MutationObserver(() => {
                                                        var newHTML = document.body.innerHTML.length;
                                                        if (newHTML !== prevHTML) {
                                                            prevHTML = newHTML;
                                                            clearTimeout(idleTimer);
                                                            idleTimer = setTimeout(() => { observer.disconnect(); clearTimeout(hardCap); resolve(true); }, 5000);
                                                        }
                                                    });
                                                    observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
                                                } catch(e) { resolve(false); }
                                            });
                                        })()
                                    """)
                                    logger.debug(f"Hide finished button clicked: {clicked}")
                                    if clicked:
                                        hide_finished = True
                                    time.sleep(3)   # extra wait for re-render

                                # ------------------------------------------------------------------
                                # 5. The WORKING SCROLL LOGIC – DO NOT MODIFY
                                # ------------------------------------------------------------------
                                before_scroll = len(session.page.query_selector_all('a[href*="/football/h2h/"]'))
                                logger.debug(f"{date_str} h2h links before scroll: {before_scroll}")

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
                                                }, 8000);

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
                                # Give DOM a final breather
                                time.sleep(3)

                                # ------------------------------------------------------------------
                                # 6. Extract and verify
                                # ------------------------------------------------------------------
                                html = session.page.content()

                                if len(html) < 8000:   # raised threshold
                                    logger.warning(f"Page content too small ({len(html)} bytes), retrying...")
                                    if fetch_attempt < 3:
                                        time.sleep(5)
                                        continue

                                soup = BeautifulSoup(html, "html.parser")

                                h2h_links = [f"https://www.oddsportal.com{a['href']}"
                                            for a in soup.find_all('a', href=True)
                                            if '/football/h2h/' in a['href']]

                                # Deduplicate while preserving order
                                h2h_links = list(dict.fromkeys(h2h_links))

                                after_scroll = len(h2h_links)
                                logger.debug(f"{date_str} h2h links after scroll: {after_scroll} (was {before_scroll} before)")

                                urls.extend(h2h_links)
                                logger.info(f"Found {len(h2h_links)} match URLs on {date_str} (total: {len(urls)})")

                                # Successfully processed this date → break fetch retry loop
                                break

                            except Exception as e:
                                logger.warning(f"Date {date_str} fetch attempt {fetch_attempt} failed: {e}")
                                if fetch_attempt == 3:
                                    logger.error(f"Skipping {date_str} after 3 failed attempts")
                                time.sleep(8)   # longer cooldown

                logger.info(f"Total URLs found: {len(urls)}")
                return list(set(urls))  # final dedup across all dates

            except Exception as e:
                logger.error(f"Outer attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.critical("All OddsPortal scraping attempts failed.")
                time.sleep(10)

        return []

    # ------------------------------------------------------------------
    # Fortified match detail scraper
    # ------------------------------------------------------------------
    def get_matches(self, urls) -> None:
        # CI‑friendly browser arguments (remove if not supported)
        browser_kwargs = {
            "solve_cloudflare": True,
            "interactive": True,
            "disable_resources": False,
            "headless": True,
        }
        try:
            browser_kwargs["browser_args"] = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ]
        except Exception:
            pass

        with browser(**browser_kwargs) as session:
            time.sleep(3)

            for idx, url in enumerate(urls):
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        logger.info(f"Processing {idx+1}/{len(urls)}: {url} (attempt {attempt})")

                        # ---------- Navigate ----------
                        try:
                            session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                        except Exception as fetch_err:
                            logger.warning(f"Fetch error (continuing): {fetch_err}")
                            time.sleep(4)
                            try:
                                session.fetch(url, wait_until="domcontentloaded", timeout=60000)  # ← was page.reload()
                            except Exception:
                                pass

                        # ---------- Wait for critical elements ----------
                        try:
                            session.page.wait_for_selector('[data-testid="game-host"]', state="attached", timeout=30000)
                            session.page.wait_for_selector('[data-testid="game-guest"]', state="attached", timeout=30000)
                            session.page.wait_for_selector('[data-testid="game-time-item"]', state="attached", timeout=30000)
                        except Exception:
                            logger.warning("Critical selectors not found, still trying")

                        # Extra settling time
                        time.sleep(3)

                        # ---------- Extract basic info ----------
                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        home_team = self._safe_text(soup, '[data-testid="game-host"] p')
                        away_team = self._safe_text(soup, '[data-testid="game-guest"] p')

                        if not home_team or not away_team:
                            logger.warning("Team names missing, retrying...")
                            if attempt < max_attempts:
                                time.sleep(5)
                                continue
                            logger.error("Skipping URL after exhausting retries")
                            break

                        # Parse date defensively
                        try:
                            date_raw = soup.find('div', {'data-testid': 'game-time-item'}).find_all('p')[1].get_text(strip=True).replace(',', '')
                            match_date = datetime.strptime(date_raw, "%d %B %Y").replace(hour=0, minute=0, second=0)
                        except Exception:
                            logger.warning("Date parse failed, using today")
                            match_date = datetime.today().replace(hour=0, minute=0, second=0)

                        # ---------- Extract odds with robust clicks ----------
                        odds_1x2 = click_and_extract_odds(session, "1X2", extract_match_odds_1x2)
                        odds_ou = click_and_extract_odds(session, "Over/Under", extract_match_odds_over_under)
                        odds_btts = click_and_extract_odds(session, "Both Teams to Score", extract_match_odds_btts)
                        odds_dc = click_and_extract_odds(session, "Double Chance", extract_match_odds_double_chance)

                        # Create Odds object
                        odds = Odds(
                            home=odds_1x2.get('home'),
                            draw=odds_1x2.get('draw'),
                            away=odds_1x2.get('away'),
                            over_05=odds_ou.get('over_05'),
                            under_05=odds_ou.get('under_05'),
                            over_15=odds_ou.get('over_15'),
                            under_15=odds_ou.get('under_15'),
                            over_25=odds_ou.get('over_25'),
                            under_25=odds_ou.get('under_25'),
                            over_35=odds_ou.get('over_35'),
                            under_35=odds_ou.get('under_35'),
                            over_45=odds_ou.get('over_45'),
                            under_45=odds_ou.get('under_45'),
                            btts_y=odds_btts.get('btts_yes'),
                            btts_n=odds_btts.get('btts_no'),
                            dc_1x=odds_dc.get('dc_1x'),
                            dc_12=odds_dc.get('dc_12'),
                            dc_x2=odds_dc.get('dc_x2'),
                        )
                        logger.info(f"Extracted odds for {home_team} vs {away_team} on {match_date.strftime('%Y-%m-%d')}: {odds}")
                        self.add_match(Match(home_team, away_team, match_date, predictions=None, odds=odds))

                        break   # success → next URL

                    except Exception as e:
                        logger.warning(f"URL {url} attempt {attempt} failed: {e}")
                        if attempt == max_attempts:
                            logger.error(f"Skipping {url} after {max_attempts} attempts")
                        time.sleep(10)

    # ------------------------------------------------------------------
    # Helper: safe text extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_text(soup, selector, default=""):
        try:
            el = soup.select_one(selector)
            return el.text.strip() if el else default
        except Exception:
            return default

# ------------------------------------------------------------------
# Odds extraction functions (unchanged logic, just called with waits)
# ------------------------------------------------------------------
def safe_find_odds(element, odds_type: str = 'standard') -> Optional[str]:
    """
    Safely extract odds from a BeautifulSoup element

    Args:
        element: BeautifulSoup element (Tag)
        odds_type: 'standard' for a tags with odds-link class, 'over-under' for p tags

    Returns:
        Odds value as string or None
    """
    try:
        if not element:
            return None

        if odds_type == 'over-under':
            odds_text = element.find('p').get_text(strip=True) if element.find('p') else None
        else:
            odds_link = element.find('a', class_='odds-link')
            if not odds_link:
                return None
            odds_text = odds_link.get_text(strip=True)

        # Filter out invalid odds
        if odds_text and odds_text != '-' and odds_text.strip():
            return odds_text
        return None
    except Exception as e:
        logger.debug(f"Error extracting odds: {e}")
        return None

def extract_match_odds_1x2(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract 1X2 odds from the first bookmaker"""
    result = {'home': None, 'draw': None, 'away': None}
    try:
        first_bookmaker = soup.find('div', {'data-testid': 'over-under-expanded-row'})
        if not first_bookmaker:
            return result

        odds_cells = first_bookmaker.find_all('div', {'data-testid': 'odd-container'})

        if len(odds_cells) > 0:
            result['home'] = safe_find_odds(odds_cells[0], 'standard')
        if len(odds_cells) > 1:
            result['draw'] = safe_find_odds(odds_cells[1], 'standard')
        if len(odds_cells) > 2:
            result['away'] = safe_find_odds(odds_cells[2], 'standard')
    except Exception as e:
        logger.warning(f"Failed to extract 1X2 odds: {e}")
    return result

def extract_match_odds_btts(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract Both Teams to Score odds from the first bookmaker"""
    result = {'btts_yes': None, 'btts_no': None}
    try:
        first_bookmaker = soup.find('div', {'data-testid': 'over-under-expanded-row'})
        if not first_bookmaker:
            return result

        odds_cells = first_bookmaker.find_all('div', {'data-testid': 'odd-container'})

        if len(odds_cells) > 0:
            result['btts_yes'] = safe_find_odds(odds_cells[0], 'standard')
        if len(odds_cells) > 1:
            result['btts_no'] = safe_find_odds(odds_cells[1], 'standard')
    except Exception as e:
        logger.warning(f"Failed to extract BTTS odds: {e}")
    return result

def extract_match_odds_double_chance(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract Double Chance odds from the first bookmaker"""
    result = {'dc_1x': None, 'dc_12': None, 'dc_x2': None}
    try:
        first_bookmaker = soup.find('div', {'data-testid': 'over-under-expanded-row'})
        if not first_bookmaker:
            return result

        odds_cells = first_bookmaker.find_all('div', {'data-testid': 'odd-container'})

        if len(odds_cells) > 0:
            result['dc_1x'] = safe_find_odds(odds_cells[0], 'standard')
        if len(odds_cells) > 1:
            result['dc_12'] = safe_find_odds(odds_cells[1], 'standard')
        if len(odds_cells) > 2:
            result['dc_x2'] = safe_find_odds(odds_cells[2], 'standard')
    except Exception as e:
        logger.warning(f"Failed to extract Double Chance odds: {e}")
    return result

def extract_match_odds_over_under(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract Over/Under odds for all lines"""
    result = {
        'over_05': None, 'under_05': None,
        'over_15': None, 'under_15': None,
        'over_25': None, 'under_25': None,
        'over_35': None, 'under_35': None,
        'over_45': None, 'under_45': None
    }

    try:
        rows = soup.find_all('div', {'data-testid': 'over-under-collapsed-row'})

        for row in rows:
            try:
                name_div = row.find('div', {'data-testid': 'over-under-collapsed-option-box'})
                if not name_div:
                    continue

                name_text = name_div.get_text(strip=True)
                odd_containers = row.find_all('div', {'data-testid': 'odd-container-default'})

                if len(odd_containers) >= 2:
                    over_odd = safe_find_odds(odd_containers[0], 'over-under')
                    under_odd = safe_find_odds(odd_containers[1], 'over-under')

                    if '+0.5' in name_text:
                        result['over_05'], result['under_05'] = over_odd, under_odd
                    elif '+1.5' in name_text:
                        result['over_15'], result['under_15'] = over_odd, under_odd
                    elif '+2.5' in name_text:
                        result['over_25'], result['under_25'] = over_odd, under_odd
                    elif '+3.5' in name_text:
                        result['over_35'], result['under_35'] = over_odd, under_odd
                    elif '+4.5' in name_text:
                        result['over_45'], result['under_45'] = over_odd, under_odd
            except Exception as e:
                logger.debug(f"Error processing over/under row: {e}")
                continue
    except Exception as e:
        logger.warning(f"Failed to extract Over/Under odds: {e}")

    return result

def click_and_extract_odds(session, tab_name: str, extractor_func) -> Dict[str, Optional[str]]:
    """
    Generic function to click a tab and extract odds
    """
    try:
        if click_div_by_text(session, tab_name):
            logger.info(f"Clicked {tab_name} tab")
            time.sleep(3)   # was missing; allow rendering
            html = session.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            return extractor_func(soup)
        else:
            logger.warning(f"Could not click {tab_name} tab")
            return {}
    except Exception as e:
        logger.error(f"Error extracting odds from {tab_name} tab: {e}")
        return {}

def click_div_by_text(session, text):
    """
    Click a div whose text content exactly matches the given text.
    Now with CI‑grade timeouts.
    """
    return session.execute_script(f"""
        (function() {{
            return new Promise((resolve) => {{
                try {{
                    var el = Array.from(document.querySelectorAll('div')).find(div => div.textContent.trim() === '{text}');
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
                    }}, 30000);   // was 10s

                    var idleTimer = setTimeout(() => {{
                        observer.disconnect();
                        clearTimeout(hardCap);
                        resolve(true);
                    }}, 5000);    // was 1s

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
    """)