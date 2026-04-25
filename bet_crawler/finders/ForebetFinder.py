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
                with browser(solve_cloudflare=True, interactive=True, disable_resources=True) as session:
                    logger.info(f"Attempt {attempt}/{max_attempts}: Loading predictions page (Cloudflare)...")
                    session.fetch(
                        FOREBET_ALL_PREDICTIONS_URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    logger.info("Solving challenges and waiting for content...")
                    session.wait_for_selector("div#body-main", timeout=60000)
                    session.wait_for_function("typeof ltodrows === 'function'", timeout=30000)

                    logger.info("Expanding matches via content-aware approach...")
                    time.sleep(3)

                    successful_clicks = 0
                    no_button_streak = 0
                    no_growth_streak = 0
                    max_expansions = 100
                    max_no_button_streak = 4
                    last_batch_fingerprint = None

                    while successful_clicks < max_expansions:
                        try:
                            # Capture count BEFORE the click
                            count_before = self._get_match_count(session)

                            clicked = self._click_expansion_button(session, count_before)

                            if clicked:
                                no_button_streak = 0
                                successful_clicks += 1
                                logger.info(f"Clicked expansion button ({successful_clicks}) - matches before load: {count_before}")

                                stable_count = self._wait_for_stable_count(session, count_before)
                                logger.info(f"Content stabilized at {stable_count} matches")

                                new_batch_fingerprint = self._get_last_batch_fingerprint(session, count_before)
                                if new_batch_fingerprint and new_batch_fingerprint == last_batch_fingerprint:
                                    logger.info("Last expansion is a duplicate batch — all real content loaded.")
                                    break

                                if stable_count <= count_before:
                                    no_growth_streak += 1
                                    logger.info(f"No new matches after click (streak: {no_growth_streak}/2)")
                                    if no_growth_streak >= 2:
                                        logger.info("Button saturated — all content loaded.")
                                        break
                                else:
                                    no_growth_streak = 0
                                    last_batch_fingerprint = new_batch_fingerprint

                            else:
                                no_button_streak += 1
                                no_growth_streak = 0
                                logger.info(f"Button not found (streak: {no_button_streak}/{max_no_button_streak})")
                                if no_button_streak >= max_no_button_streak:
                                    logger.info("Button consistently absent — assuming all content loaded.")
                                    break
                                time.sleep(4)

                        except Exception as e:
                            logger.warning(f"Expansion loop error on click {successful_clicks + 1}: {e}")
                            time.sleep(5)
                            break

                    time.sleep(3)
                    final_count = self._get_match_count(session)
                    logger.info(f"Final match count after {successful_clicks} clicks: {final_count}")

                    html = session.page.content()
                    self._parse_page(FOREBET_ALL_PREDICTIONS_URL, html)
                    return

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    logger.critical("All Forebet scraping attempts failed.")
                time.sleep(5)

    def _get_match_count(self, session) -> int:
        return session.execute_script(
            "(function(){ return document.querySelectorAll('div.ex_sc.tabonly').length; })()"
        )

    def _get_last_batch_fingerprint(self, session, count_before: int) -> str | None:
        return session.execute_script(f"""
            (function() {{
                var all = Array.from(document.querySelectorAll('div.ex_sc.tabonly'));
                var batch = all.slice({count_before});
                if (batch.length === 0) return null;
                var text = batch.map(function(el) {{ return el.textContent.trim(); }}).join('|');
                var hash = 0;
                for (var i = 0; i < text.length; i++) {{
                    hash = ((hash << 5) - hash) + text.charCodeAt(i);
                    hash = hash & hash;
                }}
                return '' + hash;
            }})()
        """)

    def _click_expansion_button(self, session, count_before: int) -> bool:
        """
        Try each strategy in order. After a click, poll up to 10s for the count
        to increase — necessary on slow hardware like Pi where 2s is not enough.
        """
        strategies = [
            "document.querySelector('div#mrows span')",
            "document.querySelector('span[onclick*=\"ltodrows\"]')",
            "document.getElementById('ltodbtn')",
            "document.querySelector('span.showmore')",
            """Array.from(document.querySelectorAll('span')).find(function(s) {
                return s.offsetParent !== null && s.textContent &&
                    s.textContent.trim().toLowerCase() === 'more';
            }) || null""",
        ]

        for i, strategy in enumerate(strategies):
            found = session.execute_script(f"""
                (function() {{
                    try {{
                        var el = {strategy};
                        if (!el || el.offsetParent === null) return false;
                        el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                        el.click();
                        return true;
                    }} catch(e) {{
                        return false;
                    }}
                }})()
            """)

            if not found:
                continue

            # Poll up to 10s for count to increase rather than a fixed 2s sleep
            # This handles slow Pi rendering without penalising fast machines
            for _ in range(5):
                time.sleep(2)
                count_after = self._get_match_count(session)
                if count_after > count_before:
                    logger.debug(f"Strategy {i + 1} succeeded: {count_before} -> {count_after}")
                    return True

            logger.debug(f"Strategy {i + 1} clicked but count unchanged ({count_before}) after 10s, trying next...")

        return False

    def _wait_for_stable_count(self, session, count_before: int, poll_interval: float = 2.0, stable_threshold: int = 3, timeout: float = 45.0) -> int:
        """Poll until match count stops growing."""
        stable_readings = 0
        last_count = count_before
        elapsed = 0.0

        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            current = self._get_match_count(session)
            if current > last_count:
                stable_readings = 0
                last_count = current
            else:
                stable_readings += 1
                if stable_readings >= stable_threshold:
                    return last_count

        logger.warning(f"_wait_for_stable_count timed out after {timeout}s — last seen: {last_count}")
        return last_count

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
                    over=None,
                    under=None,
                    btts_y=None,
                    btts_n=None,
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error - {e}")