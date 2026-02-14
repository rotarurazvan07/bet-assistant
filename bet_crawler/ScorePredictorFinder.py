import os
import random
import re
import threading
import time
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

SCOREPREDICTOR_URL = "https://scorepredictor.net/"
SCOREPREDICTOR_NAME = "ScorePredictor"
NUM_THREADS = 1
EXCLUDED = [
    "index.php?section=football&season=ChampionsLeague",
    "index.php?section=football&season=EuropaLeague",
    "index.php?section=football&season=ConferenceLeague",
    "#"
]

class ScorePredictorFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_leagues = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_leagues_urls(self):
        try:
            self.get_web_scraper(profile='fast')
            html = self.web_scraper.fast_http_request(SCOREPREDICTOR_URL + "index.php?section=football")
            soup = BeautifulSoup(html, 'html.parser')

            league_urls = []
            league_divs = soup.find(class_="block_categories").find_all('a')[3:]
            league_urls += [(SCOREPREDICTOR_URL + a.get('href')) for a in league_divs if a.get('href') not in EXCLUDED]

            print(str(len(league_urls))+" leagues to scrape")
            return league_urls
        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches_urls(self):
        return self._get_leagues_urls()

    def get_matches(self, urls):
        """Main function to scrape all matches in parallel."""
        self._scanned_leagues = 0
        self._stop_logging = False

        self.get_web_scraper(profile='fast')

        # Run worker jobs using the base helper which starts/stops progress logging
        self.run_workers(urls, self._find_matches_job, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_leagues} leagues")

    def _log_progress(self, matches_urls):
        """Log scraping progress."""
        total = len(matches_urls)
        while not self._stop_logging:
            progress = (self._scanned_leagues / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_leagues}/{total} ({progress:.1f}%)")
            time.sleep(2)

    def _find_matches_job(self, leagues_urls, thread_id):
        """Worker function that processes a slice of matches."""
        try:
            for league_url in leagues_urls:
                self._scanned_leagues += 1

                html = self.web_scraper.fast_http_request(league_url)
                try:
                    soup = BeautifulSoup(html, 'html.parser')

                    if "No matches within next 5 days" in html:
                        print(f"No matches in {league_url}")
                        continue

                    entries = soup.find(class_="table_dark").find_all("tr")[1:]
                    for entry in entries:
                        date_str = entry.find_all("td")[0].get_text().strip()
                        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        day, month = map(int, date_str.split('.'))
                        candidate = datetime(today.year, month, day)
                        if candidate - today > timedelta(days=300):
                            candidate = candidate.replace(year=today.year - 1)
                        elif today - candidate > timedelta(days=300):
                            candidate = candidate.replace(year=today.year + 1)
                        match_datetime = candidate

                        # is game
                        home_team_name = entry.find_all("td")[1].get_text().strip()
                        away_team_name = entry.find_all("td")[4].get_text().strip()

                        scores = [Score(SCOREPREDICTOR_NAME, int(entry.find_all("td")[2].get_text()),
                                                             int(entry.find_all("td")[3].get_text()))]

                        match_to_add = Match(
                            home_team=home_team_name,
                            away_team=away_team_name,
                            datetime=match_datetime,
                            predictions=scores,
                            odds=None
                        )

                        self.add_match(match_to_add)

                except Exception as e:
                    print(f"Caught exception {e} while parsing {league_url}")
        finally:
            self.web_scraper.destroy_current_thread()