import os
import random
import re
import threading
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
NUM_THREADS = 1


class ForebetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_matches = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_matches_from_html(self, url):
        """Get all match URLs from the main predictions page."""
        self.get_web_scraper(profile='slow')

        try:
            print("Loading predictions page...")
            # Wait for the match table to load
            self.web_scraper.load_page(
                url,
                additional_wait=2.0,  # Extra wait after page loads
                required_content=['All football predictions'],
            )

            # Click "Show more" buttons
            print("Loading more matches...")
            for i in range(11, 30):
                try:
                    self.web_scraper.execute_script(f'ltodrows("1x2", {i}, "");')
                    time.sleep(2)
                except Exception as e:
                    print(f"Error loading more matches at index {i}: {e}")
                    break

            # Get HTML and parse
            html_content = self.web_scraper.get_current_page()
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract match anchors to parse directly
            all_matches_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")

            print(f"Found {len(all_matches_anchors)} matches to scan")
            return all_matches_anchors

        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches_urls(self):
        return [FOREBET_URL]

    def get_matches(self, urls):
        """Main function to scrape all matches in parallel."""
        self._scanned_matches = 0
        self._stop_logging = False
        matches_anchors = self._get_matches_from_html(FOREBET_ALL_PREDICTIONS_URL)
        self.run_workers(matches_anchors, self._find_matches_job, num_threads=NUM_THREADS)
        print(f"Finished scanning {self._scanned_matches} matches")

    def _log_progress(self, matches_anchors):
        """Log scraping progress."""
        total = len(matches_anchors)
        while not self._stop_logging:
            progress = (self._scanned_matches / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_matches}/{total} ({progress:.1f}%)")
            time.sleep(2)

    def _find_matches_job(self, matches_anchors, thread_id):
        """Worker function that processes a slice of matches."""
        try:
            for match_anchor in matches_anchors:
                self._scanned_matches += 1

                try:
                    home_team = match_anchor.find("div", class_="tnms").find("span", class_="homeTeam").get_text()
                    away_team = match_anchor.find("div", class_="tnms").find("span", class_="awayTeam").get_text()

                    # 1. Ignore finished and ongoing matches
                    if match_anchor.find("div", class_="scoreLnk").get_text().strip() != "":
                        print(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                        continue # match ongoing

                    match_date = match_anchor.find("span", class_="date_bah").get_text()
                    match_date = datetime.strptime(match_date, "%d/%m/%Y %H:%M") + timedelta(hours=7)

                    home = float(match_anchor.find("div", class_="ex_sc").get_text().split("-")[0])
                    away = float(match_anchor.find("div", class_="ex_sc").get_text().split("-")[1])
                    predictions = [Score(FOREBET_NAME, home, away)]

                    # TODO - possible more odds under the other prediction tabs
                    odds_tags = [odd.get_text() for odd in match_anchor.find("div", class_="haodd").find_all("span")]
                    odds = Odds(
                        home=float(odds_tags[0]) if (odds_tags[0] is not None and odds_tags[0] != " - " and odds_tags[0] != "") else None,
                        draw=float(odds_tags[1]) if (odds_tags[1] is not None and odds_tags[1] != " - " and odds_tags[1] != "") else None,
                        away=float(odds_tags[2]) if (odds_tags[2] is not None and odds_tags[2] != " - " and odds_tags[2] != "") else None,
                        over=None,
                        under=None,
                        btts_y=None,
                        btts_n=None
                    )

                    match_to_add= Match(home_team, away_team, match_date, predictions, odds)

                    self.add_match(match_to_add)

                except Exception as e:
                    print(f"SKIPPED [{home_team} vs {away_team}]: Unexpected error during parsing - {str(e)}")
                    continue

        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()