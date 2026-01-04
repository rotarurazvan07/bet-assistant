import random
import re
import threading
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip
from bet_framework.WebScraper import WebScraper

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"
NUM_THREADS = 1


class WhoScoredFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_matches = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_matches_from_html(self):
        try:
            self.get_web_scraper(profile='fast')
            html = self.web_scraper.fast_http_request(WHOSCORED_URL + "/previews")
            soup = BeautifulSoup(html, 'html.parser')
            matches_urls = []

            matches_table_anchor = soup.find("table", class_="grid")
            matches_urls = [a['href'] for a in matches_table_anchor.find_all('a') if "matches" in a['href']]
            print(str(len(matches_urls))+" matches to scrape")
            return matches_urls
        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches(self):
        """Main function to scrape all matches in parallel."""
        self._scanned_matches = 0
        self._stop_logging = False

        # Get all match URLs
        matches_urls = self._get_matches_from_html()

        self.get_web_scraper(profile='fast')

        # Run worker jobs using the base helper which starts/stops progress logging
        self.run_workers(matches_urls, self._find_matches_job, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_matches} leagues")

    def _log_progress(self, matches_urls):
        """Log scraping progress."""
        total = len(matches_urls)
        while not self._stop_logging:
            progress = (self._scanned_matches / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_matches}/{total} ({progress:.1f}%)")
            time.sleep(2)

    def _find_matches_job(self, matches_urls, thread_id):
        """Worker function that processes a slice of matches."""
        try:
            for match_url in matches_urls:
                self._scanned_matches += 1

                html = self.web_scraper.load_page(WHOSCORED_URL + match_url)
                try:
                    soup = BeautifulSoup(html, 'html.parser')

                    home_team_name = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'home team')).get_text()
                    away_team_name = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'away team')).get_text()

                    home_team = Team(home_team_name, None, None, None)
                    away_team = Team(away_team_name, None, None, None)

                    match_time = soup.find('dt', text='Date:').find_next_sibling('dd').text + " - " + \
                                    soup.find('dt', text='Kick off:').find_next_sibling('dd').text

                    match_datetime = datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(hours=2)

                    score = soup.find("div", id="preview-prediction").find_all("span", class_="predicted-score")
                    scores = [Score(WHOSCORED_NAME, score[0].get_text(), score[1].get_text())]
                    probabilities = None
                    tips = []

                    result = "Home Win" if scores[0].home > scores[0].away else "Draw" if scores[0].home == scores[0].away else "Away Win"
                    # No detailed confidence; use high confidence (0-100)
                    confidence = 100
                    odds = None

                    tips.append(Tip(raw_text=result, confidence=confidence, source=WHOSCORED_NAME, odds=None))

                    match_predictions = MatchPredictions(scores, probabilities, tips)

                    h2h_results = None

                    match_to_add = Match(
                        home_team=home_team,
                        away_team=away_team,
                        datetime=match_datetime,
                        predictions=match_predictions,
                        h2h=h2h_results,
                        odds=odds
                    )

                    self.add_match(match_to_add)

                except Exception as e:
                    print(f"Caught exception {e} while parsing {match_url}")
        finally:
            self.web_scraper.destroy_current_thread()