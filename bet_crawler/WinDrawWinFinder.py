import os
import re
from datetime import datetime, timedelta
import threading
import time

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
NUM_THREADS = os.cpu_count()

class WinDrawWinFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)

    def _get_league_urls(self):
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

            league_trs = rows = (all_trs := soup.find('div', class_='widetable').find_all('tr'))[next(i for i, r in enumerate(all_trs) if "European Leagues" in r.text) + 1:]
            for league_tr in league_trs:
                href_anc = league_tr.find_all('a')
                if href_anc:
                    league_urls.append(href_anc[-1]['href'])
            print(f"Found {len(league_urls)} leagues to scrape")
            return league_urls

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
        league_urls = self._get_league_urls()

        # Create shared scraper and run workers using the base helper
        self.get_web_scraper(profile='fast')
        self.run_workers(league_urls, self._find_matches_job, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_matches} matches")

    def _find_matches_job(self, league_urls, thread_id):
        """Worker function that processes a slice of matches."""
        try:
            for league_url in league_urls:
                self._scanned_matches += 1

                current_date = None
                html = self.web_scraper.fast_http_request(
                    league_url
                )
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    matches_divs = soup.find('div', class_='wdwtablest mb30')
                    if matches_divs is None:
                        print(f"SKIPPED [{league_url}]: No matches")
                        continue
                    matches_divs = matches_divs.contents[2:]
                    for match_div in matches_divs:
                        try:
                            if match_div.has_attr('class') and 'wttrdt' in match_div['class']:
                                date_str = re.sub(r'(?<=\d)(st|nd|rd|th)', '', match_div.get_text()).replace("Today, ", "").replace("Tomorrow, ", "")
                                current_date = datetime.strptime(date_str, "%A, %B %d, %Y")
                                continue

                            match_inner_divs = match_div.contents[:-1]

                            home_team = match_inner_divs[0].find("div").get_text()
                            away_team = match_inner_divs[1].find("div").get_text()

                            home = float(match_inner_divs[-1].get_text().split("-")[0])
                            away = float(match_inner_divs[-1].get_text().split("-")[1])
                            predictions = [Score(WINDRAWWIN_NAME, home, away)]

                            mo_tag = match_div.find('div', class_="wtmo")
                            ou_tag = match_div.find('div', class_="wtou")
                            bt_tag = match_div.find('div', class_="wtbt")
                            odds = Odds(
                                home=float(mo_tag.contents[1].get_text()) if mo_tag is not None else None,
                                draw=float(mo_tag.contents[2].get_text()) if mo_tag is not None else None,
                                away=float(mo_tag.contents[3].get_text()) if mo_tag is not None else None,
                                over=float(ou_tag.contents[1].get_text()) if ou_tag is not None else None,
                                under=float(ou_tag.contents[2].get_text()) if ou_tag is not None else None,
                                btts_y=float(bt_tag.contents[1].get_text()) if bt_tag is not None else None,
                                btts_n=float(bt_tag.contents[2].get_text()) if bt_tag is not None else None
                            )

                            match_to_add= Match(home_team, away_team, current_date, predictions, odds)

                            self.add_match(match_to_add)

                        except Exception as e:
                            print(f"SKIPPED [{league_url}]: Unexpected error during parsing - {str(e)}")
                            continue
                except Exception as e:
                    print(f"SKIPPED [{league_url}]: Unexpected error during parsing - {str(e)}")
                    continue
        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()