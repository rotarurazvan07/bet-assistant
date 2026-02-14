import random
import re
import threading
import time
from datetime import datetime, timedelta

from DrissionPage import ChromiumOptions, ChromiumPage
from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"
NUM_THREADS = 1

options = ChromiumOptions()
options.set_argument('--headless=new')
# 2. Spoof a real User-Agent (Cloudflare blocks the default 'HeadlessChrome' one)
options.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 3. Critical arguments for stability and stealth
options.set_argument('--no-sandbox')  # Required for root/CI environments
options.set_argument('--disable-gpu') # Reduces resource usage
options.set_argument('--disable-dev-shm-usage') # Prevents memory crashes in Docker/Linux
options.set_argument('--window-size=1920,1080') # Mimics a real monitor

class WhoScoredFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_matches = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_matches_from_html(self):
        page = ChromiumPage(options)
        page.get(WHOSCORED_URL + "/previews")
        page.wait.load_start()
        soup = BeautifulSoup(page.html, 'html.parser')
        matches_urls = []

        matches_table_anchor = soup.find("table", class_="grid")
        matches_urls = [(WHOSCORED_URL + a['href']) for a in matches_table_anchor.find_all('a') if "matches" in a['href']]
        print(str(len(matches_urls))+" matches to scrape")
        page.quit()
        return matches_urls

    def get_matches_urls(self):
        return self._get_matches_from_html()

    def get_matches(self, urls):
        """Main function to scrape all matches in parallel."""
        self._scanned_matches = 0
        self._stop_logging = False

        # Run worker jobs using the base helper which starts/stops progress logging
        self.run_workers(urls, self._find_matches_job, num_threads=NUM_THREADS)

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
            page = ChromiumPage(options)
            for match_url in matches_urls:
                self._scanned_matches += 1
                page.get(match_url)
                page.wait.load_start()
                try:
                    soup = BeautifulSoup(page.html, 'html.parser')

                    home_team_name = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'home team')).get_text()
                    away_team_name = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'away team')).get_text()

                    match_time = soup.find('dt', text='Date:').find_next_sibling('dd').text + " - " + \
                                    soup.find('dt', text='Kick off:').find_next_sibling('dd').text

                    match_datetime = datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(hours=2)

                    score = soup.find("div", id="preview-prediction").find_all("span", class_="predicted-score")
                    scores = [Score(WHOSCORED_NAME, score[0].get_text(), score[1].get_text())]

                    match_to_add = Match(
                        home_team=home_team_name,
                        away_team=away_team_name,
                        datetime=match_datetime,
                        predictions=scores,
                        odds=None
                    )

                    self.add_match(match_to_add)

                except Exception as e:
                    print(f"Caught exception {e} while parsing {match_url}")
        finally:
            page.quit()