from scrape_kit import get_logger

logger = get_logger(__name__)

import time
from datetime import datetime

from bs4 import BeautifulSoup

from .BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
MAX_CONCURRENCY = 1


class ForebetFinder(BaseMatchFinder):
    """Forebet uses interactive browser (JS execution to load more matches).
    get_matches overrides the standard flow since it needs a live session.
    """

    TIMEZONE = "Etc/GMT-7"

    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        # TODO : Can use the Countries list on the left to align with other crawlers
        return [FOREBET_URL]

    def get_matches(self, urls=None) -> None:
        """Load predictions page, execute JS to expand, then parse with retries."""
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                with WebScraper.browser(
                    solve_cloudflare=True, interactive=True, disable_resources=True
                ) as session:
                    logger.info(
                        f"Attempt {attempt}/{max_attempts}: Loading predictions page (Cloudflare)..."
                    )
                    # More stable wait_until strategy for heavy ad pages
                    session.fetch(
                        FOREBET_ALL_PREDICTIONS_URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    # Now wait for the actual content to appear (Cloudflare solving happens here)
                    logger.info("Solving challenges and waiting for content...")
                    session.wait_for_selector("div#body-main", timeout=60000)
                    session.wait_for_function(
                        "typeof ltodrows === 'function'", timeout=30000
                    )

                    logger.info("Expanding matches via smart-click...")
                    successful_clicks = 0
                    # Increase wait time to ensure DOM stabilizes between chunks

                    while successful_clicks < 100:
                        try:
                            # Scroll all the way to the bottom to trigger generic dynamic load listeners
                            session.execute_script(
                                "window.scrollTo(0, document.body.scrollHeight);"
                            )
                            time.sleep(2)
                            # Then scroll slightly up so the button area is definitely in view for the click
                            session.execute_script(
                                "window.scrollTo(0, document.body.scrollHeight - 300);"
                            )
                            time.sleep(1)

                            # Try multiple times to find the button if it's currently loading
                            clicked = False
                            for retry in range(3):
                                clicked = session.execute_script("""
                                    (function() {
                                        // Forebet's clickable element is typically a span inside 'mrows' or with 'ltodrows'
                                        // We prioritize the span to ensure we hit the element with the 'onclick' event
                                        var btn = document.querySelector('div#mrows span[onclick*="ltodrows"], span#ltodbtn, span[onclick*="ltodrows"], span.showmore');
                                        if (!btn) {
                                            // Fallback to searching by text if IDs/classes fail
                                            var spans = Array.from(document.querySelectorAll('span'));
                                            btn = spans.find(s => s.textContent.toLowerCase().includes('more') && s.offsetParent !== null);
                                        }

                                        if (btn && btn.offsetParent !== null) {
                                            btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                                            btn.click();
                                            return true;
                                        }
                                        return false;
                                    })()
                                """)
                                if clicked:
                                    break
                                time.sleep(2)

                            if clicked:
                                successful_clicks += 1
                                # Crucial: Wait for the NEW content to actually arrive (at least 5s for big chunks)
                                time.sleep(6)
                                rows_found = session.execute_script(
                                    "return document.querySelectorAll('div#body-main .rcnt').length;"
                                )
                                logger.info(
                                    f"Clicked expansion button ({successful_clicks}) - current matches loaded: {rows_found}"
                                )
                            else:
                                # Final check after a longer wait before giving up
                                time.sleep(3)
                                rows_found = session.execute_script(
                                    "return document.querySelectorAll('div#body-main .rcnt').length;"
                                )
                                logger.info(
                                    f"Expansion button not found after {successful_clicks} clicks. Total matches: {rows_found}"
                                )
                                break
                        except Exception as e:
                            logger.info(f"Expansion loop error: {e}")
                            break

                    html = session.page.content()
                    self._parse_page(FOREBET_ALL_PREDICTIONS_URL, html)
                    return  # Success, exit retry loop

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.critical("All Forebet scraping attempts failed.")
                time.sleep(5)

    def _parse_page(self, url, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        all_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")
        logger.info(f"Found {len(all_anchors)} matches to scan")

        for anchor in all_anchors:
            try:
                home_team = (
                    anchor.find("div", class_="tnms")
                    .find("span", class_="homeTeam")
                    .get_text()
                )
                away_team = (
                    anchor.find("div", class_="tnms")
                    .find("span", class_="awayTeam")
                    .get_text()
                )

                if anchor.find("div", class_="scoreLnk").get_text().strip():
                    logger.info(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date = anchor.find("span", class_="date_bah").get_text()
                match_date = datetime.strptime(match_date, "%d/%m/%Y %H:%M")

                home = float(
                    anchor.find("div", class_="ex_sc").get_text().split("-")[0]
                )
                away = float(
                    anchor.find("div", class_="ex_sc").get_text().split("-")[1]
                )
                predictions = [Score(FOREBET_NAME, home, away)]

                odds_tags = [
                    o.get_text()
                    for o in anchor.find("div", class_="haodd").find_all("span")
                ]
                odds = Odds(
                    home=float(odds_tags[0])
                    if odds_tags[0] not in ("", " - ")
                    else None,
                    draw=float(odds_tags[1])
                    if odds_tags[1] not in ("", " - ")
                    else None,
                    away=float(odds_tags[2])
                    if odds_tags[2] not in ("", " - ")
                    else None,
                    over=None,
                    under=None,
                    btts_y=None,
                    btts_n=None,
                )

                self.add_match(
                    Match(home_team, away_team, match_date, predictions, odds)
                )

            except Exception as e:
                logger.info(f"SKIPPED: Parse error - {e}")
