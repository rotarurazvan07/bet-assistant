from scrape_kit import browser, get_logger

logger = get_logger(__name__)

import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
MAX_CONCURRENCY = 1


class ForebetFinder(BaseMatchFinder):
    """Forebet uses interactive browser (JS execution to load more matches).
    get_matches overrides the standard flow since it needs a live session.
    """

    TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        # TODO : Can use the Countries list on the left to align with other crawlers
        return [FOREBET_URL]

    def get_matches(self, urls=None) -> None:
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
                    logger.info(f"Attempt {attempt}/{max_attempts}: Loading predictions page (Cloudflare)...")
                    session.fetch(
                        FOREBET_ALL_PREDICTIONS_URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    logger.info("Expanding matches via content-aware approach...")

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

                    session.execute_script("""
                        var btn = document.querySelector('button.fc-cta-consent');
                        if (btn) btn.click();
                    """)

                    time.sleep(2)
                    session.execute_script("""
                        (function() {
                            return new Promise((resolve) => {
                                var totalClicks = 0;
                                var maxClicks = 50;
                                var lastKnownHeight = 0;
                                var sameHeightCount = 0;

                                function isElementVisible(el) {
                                    if (!el) return false;
                                    var style = window.getComputedStyle(el);
                                    return style.display !== 'none' &&
                                        style.visibility !== 'hidden' &&
                                        style.opacity !== '0' &&
                                        el.offsetWidth > 0 &&
                                        el.offsetHeight > 0;
                                }

                                function scrollAndClick() {
                                    // Scroll to bottom
                                    var maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                    document.body.scrollTop = maxScroll;
                                    document.documentElement.scrollTop = maxScroll;

                                    var prevHeight = maxScroll;

                                    var idleTimeout = setTimeout(() => {
                                        tryClickMore();
                                    }, 3000);

                                    var observer = new MutationObserver(() => {
                                        var newHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                        if (newHeight > prevHeight) {
                                            prevHeight = newHeight;
                                            clearTimeout(idleTimeout);
                                            observer.disconnect();
                                            setTimeout(scrollAndClick, 1000);
                                        }
                                    });

                                    observer.observe(document.body, {
                                        childList: true,
                                        subtree: true,
                                        attributes: true,
                                        characterData: true
                                    });

                                    setTimeout(() => {
                                        observer.disconnect();
                                    }, 3000);
                                }

                                function tryClickMore() {
                                    // Check if page height hasn't changed (infinite loop detection)
                                    var currentHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                    if (currentHeight === lastKnownHeight) {
                                        sameHeightCount++;
                                        if (sameHeightCount >= 3) {
                                            console.log('Page height unchanged 3 times, stopping');
                                            resolve();
                                            return;
                                        }
                                    } else {
                                        sameHeightCount = 0;
                                        lastKnownHeight = currentHeight;
                                    }

                                    totalClicks++;

                                    // Find VISIBLE "More" button
                                    var moreButton = document.querySelector('span[onclick*="ltodrows"]');

                                    // Check if it's visible
                                    if (!moreButton || !isElementVisible(moreButton)) {
                                        // Try alternative selectors
                                        var allSpans = document.querySelectorAll('span');
                                        for (var i = 0; i < allSpans.length; i++) {
                                            if (allSpans[i].textContent.trim() === 'More' && isElementVisible(allSpans[i])) {
                                                moreButton = allSpans[i];
                                                break;
                                            }
                                        }
                                    }

                                    // Stop conditions
                                    if (!moreButton || !isElementVisible(moreButton)) {
                                        console.log('More button not found or not visible, stopping');
                                        resolve();
                                        return;
                                    }

                                    if (totalClicks > maxClicks) {
                                        console.log('Max clicks reached, stopping');
                                        resolve();
                                        return;
                                    }

                                    console.log('Clicking More button (click #' + totalClicks + ')');

                                    // Click the button
                                    moreButton.click();

                                    // Wait for content to load
                                    var prevHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);

                                    var loadTimeout = setTimeout(() => {
                                        var newHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                        if (newHeight > prevHeight) {
                                            scrollAndClick();
                                        } else {
                                            resolve();
                                        }
                                    }, 5000);

                                    var clickObserver = new MutationObserver(() => {
                                        var newHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                                        if (newHeight > prevHeight) {
                                            clearTimeout(loadTimeout);
                                            clickObserver.disconnect();
                                            setTimeout(scrollAndClick, 1000);
                                        }
                                    });

                                    clickObserver.observe(document.body, {
                                        childList: true,
                                        subtree: true,
                                        attributes: true,
                                        characterData: true
                                    });

                                    setTimeout(() => {
                                        clickObserver.disconnect();
                                    }, 5000);
                                }

                                // Start the process
                                scrollAndClick();
                            });
                        })()
                    """)

                    count_script = '(function(){ return document.querySelectorAll("div.ex_sc.tabonly").length; })()'
                    logger.info(f"Final match count : {session.execute_script(count_script)}")

                    html = session.page.content()
                    self._parse_page(FOREBET_ALL_PREDICTIONS_URL, html)
                    return

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.error("All Forebet scraping attempts failed.")
                time.sleep(5)

    def _parse_page(self, url, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        all_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")
        logger.info(f"Found {len(all_anchors)} matches to scan")

        for anchor in all_anchors:
            try:
                home_team = anchor.find("div", class_="tnms").find("span", class_="homeTeam").get_text()
                away_team = anchor.find("div", class_="tnms").find("span", class_="awayTeam").get_text()

                if anchor.find("div", class_="scoreLnk").get_text().strip():
                    logger.info(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date = anchor.find("span", class_="date_bah").get_text()
                match_date = datetime.strptime(match_date, "%d/%m/%Y %H:%M")

                home = float(anchor.find("div", class_="ex_sc").get_text().split("-")[0])
                away = float(anchor.find("div", class_="ex_sc").get_text().split("-")[1])
                predictions = [Score(FOREBET_NAME, home, away)]

                odds_tags = [o.get_text() for o in anchor.find("div", class_="haodd").find_all("span")]
                odds = Odds(
                    home=float(odds_tags[0]) if odds_tags[0] not in ("", " - ") else None,
                    draw=float(odds_tags[1]) if odds_tags[1] not in ("", " - ") else None,
                    away=float(odds_tags[2]) if odds_tags[2] not in ("", " - ") else None,
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error - {e}")
