import os
import re
from datetime import datetime, timedelta
import threading
import time

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip
from bet_framework.WebScraper import WebScraper

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
TIP_STRENGTHS = ["Small", "Medium", "Large"]
NUM_THREADS = os.cpu_count()

class WinDrawWinFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)

    def _get_matches_urls(self):
        """Get all league URLs to scrape."""
        self.get_web_scraper(profile='fast')

        try:
            print("Loading WinDrawWin leagues page...")
            html = self.web_scraper.fast_http_request(
                WINDRAWWIN_URL
            )

            if not html:
                print("Failed to load leagues page")
                return []

            soup = BeautifulSoup(html, 'html.parser')

            league_urls = []
            matches_urls = []

            league_trs = rows = (all_trs := soup.find('div', class_='widetable').find_all('tr'))[next(i for i, r in enumerate(all_trs) if "European Leagues" in r.text) + 1:]
            for league_tr in league_trs:
                href_anc = league_tr.find_all('a')
                if href_anc:
                    league_urls.append(href_anc[-1]['href'])
            print(f"Found {len(league_urls)} leagues to scrape")

            for league_url in league_urls:
                html = self.web_scraper.fast_http_request(
                    league_url
                )
                if not html:
                    print("Failed to load {league_url}")

                soup = BeautifulSoup(html, 'html.parser')

                try:
                    matches_divs = soup.find('div', class_='wdwtablest mb30').find_all('div', class_='wttr')
                except:
                    continue # No matches in league
                for match_div in matches_divs:
                    matches_urls.append(match_div.find('a', class_='wtdesklnk')['href'])

            matches_urls = list(set(matches_urls))
            print(f"Found {len(matches_urls)} matches to scrape")
            return matches_urls

        finally:
            self.web_scraper.destroy_current_thread()

    def _log_progress(self, matches_urls):
        """Log scraping progress."""
        total = len(matches_urls)
        while not self._stop_logging:
            progress = (self._scanned_matches / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_matches}/{total} matches ({progress:.1f}%)")
            time.sleep(2)

    def get_matches(self):
        """Main function to scrape all matches in parallel."""
        self._scanned_matches = 0
        self._stop_logging = False

        # Get all match URLs
        matches_urls = self._get_matches_urls()

        # Create shared scraper and run workers using the base helper
        self.get_web_scraper(profile='fast')
        self.run_workers(matches_urls, self._find_matches_job, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_matches} matches")

    def _find_matches_job(self, matches_urls, thread_id):
        """Worker function that processes a slice of matches."""
        try:
            for match_url in matches_urls:
                self._scanned_matches += 1

                html = self.web_scraper.fast_http_request(
                    match_url
                )
                try:
                    soup = BeautifulSoup(html, 'html.parser')


                    home_team_name = soup.find('div', class_='tnrow').find_all('span')[0].get_text()
                    away_team_name = soup.find('div', class_='tnrow').find_all('span')[1].get_text()

                    date_str = soup.find(class_='headlinetext').get_text()
                    match_datetime = datetime.strptime(re.sub(r'(\d+)(st|nd|rd|th)', r'\1', " ".join(date_str.split(',')[-2:])).strip(), "%B %d %Y")

                    home_stats_div = soup.find_all('div', class_='fstath')
                    away_stats_div = soup.find_all('div', class_='fstata')
                    home_team_league_points = 3 * int(home_stats_div[2].get_text()) + int(home_stats_div[3].get_text())
                    away_team_league_points = 3 * int(away_stats_div[2].get_text()) + int(away_stats_div[3].get_text())

                    home_team_form = soup.find(class_='wtl5contllg').get_text(strip=True)
                    away_team_form = soup.find(class_='wtl5contrlg').get_text(strip=True)

                    home_team = Team(home_team_name, home_team_league_points, home_team_form, None)
                    away_team = Team(away_team_name, away_team_league_points, away_team_form, None)


                    scores= [Score(WINDRAWWIN_NAME, soup.find(class_='tbtd2 w100p featurescore').get_text()[0], soup.find(class_='tbtd2 w100p featurescore').get_text()[-1])]
                    probabilities = [Probability(WINDRAWWIN_NAME,
                                                 soup.find_all(class_='tbtd talc p9 w20p')[0].get_text().replace("%",''),
                                                 soup.find_all(class_='tbtd talc p9 w20p')[1].get_text().replace("%",''),
                                                 soup.find_all(class_='tbtd talc p9 w20p')[2].get_text().replace("%",''))]
                    tips = []

                    result = "Home Win" if scores[0].home > scores[0].away else "Draw" if scores[0].home == scores[0].away else "Away Win"
                    # Map strength (Small/Medium/Large) to 0-100 confidence
                    tip_text = soup.find(class_='tbtd2 w100p featuretip').get_text().lower()
                    strength_index = next((i for i, s in enumerate(TIP_STRENGTHS) if s.lower() in tip_text), None)
                    if strength_index is None:
                        confidence = 50
                    else:
                        confidence = int(round(((strength_index + 1) / len(TIP_STRENGTHS)) * 100))

                    try:
                        odds = Odds(
                            home=float(soup.find_all(class_='w20p tbtdodds')[0].get_text()),
                            draw=float(soup.find_all(class_='w20p tbtdodds')[1].get_text()),
                            away=float(soup.find_all(class_='w20p tbtdodds')[2].get_text()),
                            over=float(soup.find_all(class_='w30p tbtdodds')[2].get_text()),
                            under=float(soup.find_all(class_='w30p tbtdodds')[3].get_text()),
                            btts_y=float(soup.find_all(class_='w30p tbtdodds')[0].get_text()),
                            btts_n=float(soup.find_all(class_='w30p tbtdodds')[1].get_text())
                        )
                    except (AttributeError, IndexError) as e:
                        odds = None

                    tips.append(Tip(raw_text=result, confidence=confidence, source=WINDRAWWIN_NAME, odds=None))

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

                    # Successfully added to database
                    self.add_match(match_to_add)

                except Exception as e:
                    print(f"SKIPPED [{match_url}]: Unexpected error during parsing - {str(e)}")
                    continue
        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()