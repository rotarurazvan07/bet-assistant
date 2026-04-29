import re
from scrape_kit import browser, get_logger

logger = get_logger(__name__)

import time
from datetime import datetime
from scrape_kit import ScrapeMode, fetch, scrape
from bs4 import BeautifulSoup
import json
from bet_framework.core.Match import *
from dataclasses import fields
from .BaseMatchFinder import BaseMatchFinder

XGSCORE_URL = "https://xgscore.io/predictions/correct-score"
XGSCORE_NAME = "xgscore"
MAX_CONCURRENCY = 3


class xGScoreFinder(BaseMatchFinder):
    # For interactive browsing finders, TIMEZONE should be set to the server's local timezone
    # Use dynamic detection to get the actual local timezone of the computer running this code
    # TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        """Load predictions page, execute JS to expand, then parse."""
        html = None
        with browser(solve_cloudflare=True, interactive=True) as session:
            logger.info("Loading predictions page...")
            session.fetch(XGSCORE_URL)
            session.wait_for_selector("mat-button-toggle-group", timeout=15000)

            logger.info("Clicking on Week view.")

            try:
                clicked = session.execute_script("""
                    (function() {
                        const buttons = Array.from(document.querySelectorAll('.mat-button-toggle-label-content'));
                        const weekBtn = buttons.find(el => el.textContent.trim() === 'Week');
                        if (weekBtn) {
                            weekBtn.scrollIntoView({behavior: 'smooth', block: 'center'});
                            weekBtn.click();
                            return true;
                        }
                        return false;
                    })()
                """)
                if clicked:
                    logger.info("Successfully switched to Week view")
                    # Wait for the content to reload/update
                    time.sleep(5)
                else:
                    logger.info("Could not find 'Week' button.")
            except Exception as e:
                logger.info(f"Click error: {e}")

            html = session.page.content()

        if html:
            matches_urls = []
            soup= BeautifulSoup(html, "html.parser")
            matches_anchors= soup.find_all("div", class_="xgs-category-forecast-fixture")
            for anchor in matches_anchors:
                matches_urls.append("https://xgscore.io" + anchor.find("a", class_="xgs-category-forecast-fixture_teams").get("href"))
            logger.info(f"Found {len(matches_urls)} matches.")
            return matches_urls

    def get_matches(self, urls=None) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        try:
            home_team=soup.find_all("strong", class_="xgs-game-header_team-name")[0].get_text().strip()
            away_team=soup.find_all("strong", class_="xgs-game-header_team-name")[1].get_text().strip()

            try:
                date_str = soup.find("div", class_="xgs-game-header_datetime").get_text().strip()
                match_datetime = datetime.strptime(re.search(r"[A-Z][a-z]+ \d+, \d+", date_str).group(), "%B %d, %Y").replace(hour=0, minute=0)
            except Exception as e:
                logger.error(f"Match finished")
                return

            home, away = re.search(r"Correct Score:\s*(\d+)-(\d+)", html).groups()

            predictions = [Score(XGSCORE_NAME,home,away)]

            # Extract odds from the HTML div elements
            odds = self._extract_odds_from_html(soup)

            self.add_match(Match(home_team, away_team, match_datetime, predictions, odds))

        except Exception as e:
            logger.error(f"SKIPPED: Parse error - {e}")

    def _extract_odds_from_html(self, soup):
        """Extract bookmaker odds from HTML and return a safe Odds object."""
        # 1. Initialize data with default values from the dataclass fields
        # This prevents missing fields from causing issues later.
        init_data = {f.name: f.default for f in fields(Odds)}

        try:
            odds_elements = soup.find_all('xgs-odds')

            if len(odds_elements) >= 2:
                # 2. Get the raw dictionary from the helper
                parsed_data = self._parse_odds_from_element(odds_elements[1])

                if parsed_data:
                    # 3. Update our safe defaults with the parsed values
                    init_data.update(parsed_data)

            # 4. Create the object in one shot
            return Odds(**init_data)

        except Exception as e:
            logger.error(f"Error extracting odds: {e}")
            # Return a "safe" default object if everything crashes
            return None

    def _parse_odds_from_element(self, element):
        """Regex helper that returns a dictionary mapped to field names."""
        element_str = str(element)

        # Map regex labels to dataclass field names
        labels = {"1x": "dc_1x", "12": "dc_12", "x2": "dc_x2"}
        found_data = {}

        for label, field_name in labels.items():
            pattern = rf'class="[^"]*odds-cell_label[^>]*>{label}</span>.*?class="[^"]*text-sm-tiny[^>]*>\s*([0-9.]+)\s*</span>'
            match = re.search(pattern, element_str, re.DOTALL)
            if match:
                try:
                    found_data[field_name] = float(match.group(1))
                except (ValueError, TypeError):
                    continue

        return found_data