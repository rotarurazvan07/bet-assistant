import os
import re
import threading
import time
from datetime import datetime, date, timedelta

from bs4 import BeautifulSoup
from bs4 import Tag

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"
NUM_THREADS = os.cpu_count()
EXCLUDED = {
    "/index.php?clanek=tips&sekce=fotbal&liga=champions2&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=champions3&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=champions4&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=euro_national_league&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=southamerica&lang=en",
    "/index.php?clanek=euro-2008&liga=euro&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=africancup&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=angliezeny&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=euro2024&lang=en"
}

class VitibetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_leagues = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_leagues_urls(self):
        """Get all league URLs to scrape."""
        self.get_web_scraper(profile='fast')

        try:
            print("Loading Vitibet leagues page...")
            html = self.web_scraper.fast_http_request(
                VITIBET_URL,
                min_content_length=5000
            )

            soup = BeautifulSoup(html, 'html.parser')
            league_urls_ul = soup.find("ul", id="primarne")

            kokos_tag = league_urls_ul.find('kokos')

            # Excluded leagues
            league_urls = []
            for sibling in kokos_tag.find_next_siblings():
                if isinstance(sibling, Tag) and sibling.name == 'li':
                    link = sibling.find("a")
                    if not link:
                        continue

                    href = link.get("href", "")

                    # Skip if ANY excluded pattern is found in the href
                    if any(ex in href for ex in EXCLUDED):
                        continue

                    league_urls.append(href)
            print(f"Found {len(league_urls)} leagues to scrape")
            return league_urls

        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches(self):
        """Main function to scrape all leagues in parallel."""
        self._scanned_leagues = 0
        self._stop_logging = False

        # Get all league URLs
        league_urls = self._get_leagues_urls()

        # Create shared scraper (fast profile)
        self.get_web_scraper(profile='fast')

        # Run workers using the common helper
        self.run_workers(league_urls, self._get_matches_helper, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_leagues} leagues")

    def _log_progress(self, league_urls):
        """Log scraping progress."""
        total = len(league_urls)
        while not self._stop_logging:
            progress = (self._scanned_leagues / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_leagues}/{total} leagues ({progress:.1f}%)")
            time.sleep(2)

    def _get_matches_helper(self, league_urls, thread_id):
        """Worker function that processes a slice of leagues."""
        try:
            for league_url in league_urls:
                self._scanned_leagues += 1

                # Step 1: Fetch dates of matches for this league
                full_url = "https://www.vitibet.com/" + league_url
                html = self.web_scraper.fast_http_request(
                    full_url
                )
                try:
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract match dates
                    matches_table = soup.find("table", class_="tabulkaquick")
                    if not matches_table:
                        print(f"SKIPPED [League {league_url}]: No matches table found")
                        continue

                    match_tags = matches_table.find_all("tr")[2:]
                    for match_tag in match_tags:
                        try:
                            all_tags = match_tag.find_all("td")
                            if all_tags[5].get_text() == "?" or all_tags[7].get_text() == "?":
                                continue

                            date_str = all_tags[0].get_text()
                            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                            day, month = map(int, date_str.split('.'))
                            candidate = datetime(today.year, month, day)
                            if candidate - today > timedelta(days=300):
                                candidate = candidate.replace(year=today.year - 1)
                            elif today - candidate > timedelta(days=300):
                                candidate = candidate.replace(year=today.year + 1)
                            match_date = candidate

                            home_team = all_tags[2].get_text()
                            away_team = all_tags[3].get_text()

                            home = float(all_tags[5].get_text())
                            away = float(all_tags[7].get_text())
                            predictions = [Score(VITIBET_NAME, home, away)]

                            odds = None

                            match_to_add= Match(home_team, away_team, match_date, predictions, odds)

                            self.add_match(match_to_add)
                        except Exception as e:
                            print(f"SKIPPED [League {league_url}]: {str(e)}")
                            continue
                except Exception as e:
                    print(f"SKIPPED [League {league_url}]: {str(e)}")
                    continue
        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()