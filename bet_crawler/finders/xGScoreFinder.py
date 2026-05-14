import re
from datetime import datetime

from scrape_kit import browser, get_logger, Page

from bet_framework.core.Match import Match, Odds, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

XGSCORE_URL = "https://xgscore.io/predictions/correct-score"
XGSCORE_NAME = "xgscore"


class xGScoreFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Load predictions page, execute JS to expand, then parse."""
        try:
            with browser(solve_cloudflare=True, headless=True) as session:
                logger.info("Loading xGScore predictions page...")
                session.fetch(XGSCORE_URL)

                # Use the new session.click instead of manual execute_script for 'Week' button
                if session.click(".mat-button-toggle-label-content", text="Week", idle_ms=5000):
                    logger.info("Successfully switched to Week view")
                else:
                    logger.warning("Could not find 'Week' button")

                page = Page.from_html(session.page.content())
                
                # Find match anchors
                matches_anchors = page.find(".xgs-category-forecast-fixture")
                urls = []
                for anchor in matches_anchors:
                    link = anchor.find("a.xgs-category-forecast-fixture_teams")
                    if link and link.attr("href"):
                        urls.append("https://xgscore.io" + link.attr("href"))
                
                logger.info(f"Found {len(urls)} xGScore matches.")
                return list(set(urls))
        except Exception as e:
            logger.error(f"Failed to discover xGScore matches: {e}")
            return []

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            # 1. Team Names
            teams = page.find(".xgs-game-header_team-name")
            if len(teams) < 2:
                return
            home_team = teams[0].text().strip()
            away_team = teams[1].text().strip()

            # 2. Date
            date_tag = page.find(".xgs-game-header_datetime")
            if date_tag:
                date_str = date_tag[0].text().strip()
                # Regex match format like "May 15, 2026"
                match = re.search(r"[A-Z][a-z]+ \d+, \d+", date_str)
                if match:
                    match_datetime = datetime.strptime(match.group(), "%B %d, %Y").replace(hour=0, minute=0)
                else:
                    match_datetime = datetime.now().replace(hour=0, minute=0)
            else:
                return

            # 3. Correct Score Prediction
            html = page.raw_html
            score_match = re.search(r"Correct Score:\s*(\d+)-(\d+)", html)
            if score_match:
                home_p, away_p = score_match.groups()
                predictions = [Score(XGSCORE_NAME, float(home_p), float(away_p))]
            else:
                return

            # 4. Odds
            odds = self._extract_odds(page)

            self.add_match(Match(home_team, away_team, match_datetime, predictions, odds))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")

    def _extract_odds(self, page: Page) -> Odds | None:
        try:
            odds_elements = page.find("xgs-odds")
            if len(odds_elements) < 2:
                return None

            # xGScore usually has multiple odds blocks; index 1 is often Double Chance
            dc_element = odds_elements[1]
            html = dc_element.raw_html
            
            # Map labels to field names
            labels = {"1x": "dc_1x", "12": "dc_12", "x2": "dc_x2"}
            odds_data = {}

            for label, field_name in labels.items():
                pattern = rf'>{label}</span>.*?text-sm-tiny[^>]*>\s*([0-9.]+)\s*<'
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        odds_data[field_name] = float(match.group(1))
                    except:
                        continue

            if not odds_data:
                return None
                
            return Odds(**odds_data)
        except Exception:
            return None
