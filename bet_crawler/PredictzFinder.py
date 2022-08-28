import os
import random
import re
import threading
import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip
from bet_framework.WebScraper import WebScraper

PREDICTZ_URL = "https://www.predictz.com/"
PREDICTZ_NAME = "predictz"
NUM_THREADS = os.cpu_count()

EXCLUDED = [
    "https://www.predictz.com/predictions/england/community-shield/",
    "https://www.predictz.com/predictions/england/fa-cup/",
    "https://www.predictz.com/predictions/england/efl-cup/",
    "https://www.predictz.com/predictions/england/womens-super-league/",
    "https://www.predictz.com/predictions/scotland/scottish-cup/",
    "https://www.predictz.com/predictions/scotland/scottish-league-cup/",
    "https://www.predictz.com/predictions/spain/copa-del-rey/",
    "https://www.predictz.com/predictions/spain/supercopa-de-espana/",
    "https://www.predictz.com/predictions/germany/dfb-pokal/",
    "https://www.predictz.com/predictions/italy/coppa-italia/",
    "https://www.predictz.com/predictions/france/coupe-de-france/",
    "https://www.predictz.com/predictions/france/coupe-de-la-ligue/",
    "https://www.predictz.com/predictions/brazil/copa-do-brasil/",
    "https://www.predictz.com/predictions/usa/leagues-cup/"
]

class PredictzFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_leagues = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_matches_from_html(self):
        try:
            self.get_web_scraper(profile='fast')
            html = self.web_scraper.fast_http_request(PREDICTZ_URL)
            soup = BeautifulSoup(html, 'html.parser')

            league_urls = []
            league_divs = soup.find(class_="dd nav-select").find_all('optgroup')[6:]
            for league_div in league_divs:
                league_urls += [league.get('value') for league in league_div.find_all('option') \
                                if league.get('value') not in EXCLUDED]


            print(str(len(league_urls))+" leagues to scrape")
            return league_urls
        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches(self):
        """Main function to scrape all matches in parallel."""
        self._scanned_leagues = 0
        self._stop_logging = False

        # Get all match URLs
        leagues_urls = self._get_matches_from_html()

        self.get_web_scraper(profile='fast')

        # Run worker jobs using the base helper which starts/stops progress logging
        self.run_workers(leagues_urls, self._find_matches_job, num_threads=NUM_THREADS)

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

                    if "This could be due to games currently in play, tips being formulated, or there might not be any future games for this competition." in html:
                        continue

                    entries = soup.find_all(class_="pzcnth")
                    for entry in entries:
                        # is date
                        if entry.find('h2'):
                            date_str = entry.find('h2').get_text()
                            clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str).replace(',', '')
                            match_datetime = next(dt for y in range(datetime.now().year - 1, datetime.now().year + 2) for dt in [datetime.strptime(f"{clean} {y}", "%A %B %d %Y")] if dt.strftime('%A') in date_str)
                        else:
                            # is game
                            home_team_name = entry.find(class_="fixt").get_text().split(" vs ")[0]
                            away_team_name = entry.find(class_="fixt").get_text().split(" vs ")[1]

                            home_team = Team(home_team_name, None, None, None)
                            away_team = Team(away_team_name, None, None, None)

                            scores = [Score(PREDICTZ_NAME, int(entry.find("td").get_text()[-3:].split("-")[0]),
                                                          int(entry.find("td").get_text()[-3:].split("-")[1]))]
                            probabilities = None
                            tips = []

                            result = "Home Win" if scores[0].home > scores[0].away else "Draw" if scores[0].home == scores[0].away else "Away Win"
                            # No detailed confidence; use high confidence (0-100)
                            confidence = 100

                            try:
                                odds = Odds(
                                    home=float(soup.find_all(class_='odds')[0].get_text()),
                                    draw=float(soup.find_all(class_='odds')[1].get_text()),
                                    away=float(soup.find_all(class_='odds')[2].get_text()),
                                    over=0.0,
                                    under=0.0,
                                    btts_y=0.0,
                                    btts_n=0.0
                                )
                            except (AttributeError, IndexError) as e:
                                odds = None

                            tips.append(Tip(raw_text=result, confidence=confidence, source=PREDICTZ_NAME, odds=None))

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
                    print(f"Caught exception {e} while parsing {league_url}")
        finally:
            self.web_scraper.destroy_current_thread()