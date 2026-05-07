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

    def get_matches_urls(self):
        urls = []
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                with browser(solve_cloudflare=True, interactive=True, disable_resources=True, headless=True) as session:
                    hide_finished = False
                    for date_str in [(date.today() + timedelta(days=i)).strftime("%Y%m%d") for i in range(6)]:
                        logger.info(f"Attempt {attempt}/{max_attempts}: Loading predictions page (Cloudflare)...")
                        session.fetch(
                            f"https://www.oddsportal.com/matches/football/{date_str}/",
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )

                        if not hide_finished:
                            session.execute_script("""
                                (function() {
                                    return new Promise((resolve) => {
                                        try {
                                            var button = document.querySelector('[data-testid="next-matches-show-finished-toggle"]');
                                            if (!button) {
                                                resolve(false);
                                                return;
                                            }

                                            button.click();

                                            var timeout = setTimeout(() => {
                                                observer.disconnect();
                                                resolve(true);
                                            }, 10000);

                                            var observer = new MutationObserver(function() {
                                                clearTimeout(timeout);
                                                timeout = setTimeout(() => {
                                                    observer.disconnect();
                                                    resolve(true);
                                                }, 1000);
                                            });

                                            observer.observe(document.body, {
                                                childList: true,
                                                subtree: true,
                                                attributes: true,
                                                characterData: true
                                            });

                                        } catch(e) {
                                            resolve(false);
                                        }
                                    });
                                })()
                            """)
                            hide_finished = True

                        session.execute_script("""
                            (function() {
                                return new Promise((resolve) => {
                                    function cycle() {
                                        // Slam to absolute bottom
                                        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });

                                        setTimeout(() => {
                                            var prevHeight = document.documentElement.scrollHeight;

                                            // Nudge up to trigger lazy load sentinel
                                            window.scrollTo({
                                                top: document.documentElement.scrollHeight - window.innerHeight - 400,
                                                behavior: 'smooth'
                                            });

                                            // Wait up to 5s for new content to appear
                                            var idleTimeout = setTimeout(() => {
                                                observer.disconnect();
                                                resolve();  // Nothing loaded — truly done
                                            }, 10000);

                                            var observer = new MutationObserver(() => {
                                                if (document.documentElement.scrollHeight > prevHeight) {
                                                    clearTimeout(idleTimeout);
                                                    observer.disconnect();
                                                    setTimeout(cycle, 300);  // New content — cycle again
                                                }
                                            });

                                            observer.observe(document.body, { childList: true, subtree: true });

                                        }, 300);  // Let instant scroll land before nudging
                                    }

                                    cycle();
                                });
                            })()
                        """)

                        html = session.page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        h2h_links = [f"https://www.oddsportal.com{a['href']}" for a in soup.find_all('a', href=True) if '/football/h2h/' in a['href']]
                        urls.extend(list(dict.fromkeys(h2h_links)))

                        logger.info(f"Found {len(list(dict.fromkeys(h2h_links)))} match URLs on {date_str}")
                logger.info(f"Total URLs found: {len(urls)}")
                return urls
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.critical("All OddsPortal scraping attempts failed.")
                time.sleep(5)

        return []

    def get_matches(self, urls) -> None:
        with browser(solve_cloudflare=True, interactive=True, disable_resources=True, headless=True) as session:
            for url in urls:
                try:
                    session.fetch(
                        url,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    home_team = soup.find('div', {'data-testid': 'game-host'}).find('p').get_text(strip=True)
                    away_team = soup.find('div', {'data-testid': 'game-guest'}).find('p').get_text(strip=True)

                    match_date = datetime.strptime(soup.find('div', {'data-testid': 'game-time-item'}). \
                                                   find_all('p')[1].get_text(strip=True).replace(',', ''), "%d %B %Y"). \
                                                   replace(hour=0, minute=0, second=0)

                    # Extract 1X2 odds
                    odds_1x2 = click_and_extract_odds(session, "1X2", extract_match_odds_1x2)

                    # Extract Over/Under odds
                    odds_ou = click_and_extract_odds(session, "Over/Under", extract_match_odds_over_under)

                    # Extract Both Teams to Score odds
                    odds_btts = click_and_extract_odds(session, "Both Teams to Score", extract_match_odds_btts)

                    # Extract Double Chance odds
                    odds_dc = click_and_extract_odds(session, "Double Chance", extract_match_odds_double_chance)

                    # Create Odds object with defensive defaults
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

                except Exception as e:
                    logger.error(f"SKIPPED: Parse error - {e}")

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

    Args:
        session: Browser session
        tab_name: Name of the tab to click (e.g., "1X2", "Over/Under")
        extractor_func: Function that takes soup and returns odds dict

    Returns:
        Dictionary of extracted odds
    """
    try:
        if click_div_by_text(session, tab_name):
            logger.info(f"Clicked {tab_name} tab")
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
                    }}, 10000);

                    var idleTimer = setTimeout(() => {{
                        observer.disconnect();
                        clearTimeout(hardCap);
                        resolve(true);
                    }}, 1000);

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
                            }}, 1000);
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
