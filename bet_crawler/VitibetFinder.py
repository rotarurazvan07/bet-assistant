import os
import re
import threading
import time
from datetime import datetime, date, timedelta

from bs4 import BeautifulSoup
from bs4 import Tag

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip
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

                    date_rows = matches_table.find_all("tr")[2:]
                    dates = []
                    for row in date_rows:
                        first_td = row.find("td")
                        if first_td:
                            dates.append(first_td.get_text().strip())

                    if len(dates) == 0:
                        print(f"SKIPPED [League {league_url}]: No matches found")
                        continue

                    # Step 2: Process each match in the league
                    analysis_url_template = league_url.replace("tips", "analyzy") + "&tab=1&zap=%s"

                    for index, date_str in enumerate(dates):
                        match_url = "https://www.vitibet.com" + analysis_url_template % (index+1)
                        match_html = self.web_scraper.fast_http_request(
                            match_url
                        )
                        try:
                            # Check for end of matches
                            if "? : ?" in match_html or "#N/A : #N/A" in match_html:
                                break


                            match_soup = BeautifulSoup(match_html, 'html.parser')

                            # Extract team names
                            team_cells = match_soup.find_all("td", class_="bunkamuzstvo")
                            if len(team_cells) < 2:
                                print(f"SKIPPED [Match {match_url}]: Missing team cells")
                                continue

                            home_team_name = team_cells[0].get_text().replace("\n", '').strip()
                            away_team_name = team_cells[1].get_text().replace("\n", '').strip()

                            if not home_team_name or not away_team_name:
                                print(f"SKIPPED [Match {match_url}]: Empty team name")
                                continue

                            # Extract team forms
                            home_team_form = ""
                            away_team_form = ""
                            form_tables = match_soup.find_all("table", class_="malypismonasedym")

                            if len(form_tables) >= 2:
                                for form_table in form_tables[-2:]:
                                    form_rows = form_table.find_all("tr")[:3]
                                    for result_row in form_rows:
                                        cells = result_row.find_all("td")
                                        if len(cells) >= 4:
                                            # Home team result
                                            home_style = cells[1].get("style", "")
                                            if "color:red" in home_style:
                                                home_team_form += "L"
                                            elif "color:green" in home_style:
                                                home_team_form += "W"
                                            else:
                                                home_team_form += "D"

                                            # Away team result
                                            away_style = cells[3].get("style", "")
                                            if "color:red" in away_style:
                                                away_team_form += "L"
                                            elif "color:green" in away_style:
                                                away_team_form += "W"
                                            else:
                                                away_team_form += "D"

                            # Extract league points
                            home_team_league_points = 0
                            away_team_league_points = 0

                            standings_table = match_soup.find("table", class_="tabulkaquick")
                            if standings_table:
                                for team_row in standings_table.find_all("tr"):
                                    row_text = str(team_row)
                                    points_cells = team_row.find_all("td", class_="cisloporadi")

                                    if points_cells and home_team_name in row_text:
                                        try:
                                            home_team_league_points = int(points_cells[-1].get_text().strip())
                                        except:
                                            pass
                                    elif points_cells and away_team_name in row_text:
                                        try:
                                            away_team_league_points = int(points_cells[-1].get_text().strip())
                                        except:
                                            pass

                            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                            day, month = map(int, date_str.split('.'))
                            candidate = datetime(today.year, month, day)
                            if candidate - today > timedelta(days=300):
                                candidate = candidate.replace(year=today.year - 1)
                            elif today - candidate > timedelta(days=300):
                                candidate = candidate.replace(year=today.year + 1)
                            match_date = candidate

                            # Extract predicted score
                            score_cell = match_soup.find("td", class_="bunkatip")
                            if not score_cell:
                                print(f"SKIPPED [Match {match_url}]: No score prediction found")
                                continue

                            score_text = score_cell.get_text().strip()
                            try:
                                score_parts = score_text.split(":")
                                score = Score(
                                    VITIBET_NAME,
                                    int(score_parts[0].strip()),
                                    int(score_parts[1].strip())
                                )
                            except:
                                print(f"SKIPPED [Match {match_url}]: Failed to parse score '{score_text}'")
                                continue

                            # Extract probabilities
                            prob_cells = match_soup.find_all("td", class_="indexapravdepodobnost")
                            if len(prob_cells) < 6:
                                print(f"SKIPPED [Match {match_url}]: Insufficient probability data")
                                continue

                            try:
                                probabilities = [int(td.get_text().replace(" %", '').strip()) for td in prob_cells[3:6]]
                                probability = Probability(VITIBET_NAME, probabilities[0], probabilities[1], probabilities[2])
                            except:
                                print(f"SKIPPED [Match {match_url}]: Failed to parse probabilities")
                                continue

                            # Create tip
                            result = "Home Win" if score.home > score.away else "Draw" if score.home == score.away else "Away Win"
                            # Use max probability directly as 0-100 confidence
                            confidence = float(max(probability.home, probability.draw, probability.away))
                            tip = Tip(raw_text=result, confidence=confidence, source=VITIBET_NAME, odds=None)

                            # Create match
                            match_to_add = Match(
                                home_team=Team(home_team_name, home_team_league_points, home_team_form, None),
                                away_team=Team(away_team_name, away_team_league_points, away_team_form, None),
                                datetime=match_date,
                                predictions=MatchPredictions(
                                    scores=[score],
                                    probabilities=[probability],
                                    tips=[tip]
                                ),
                                h2h=None,
                                odds=None
                            )

                            self.add_match(match_to_add)
                        except Exception as e:
                            print(f"SKIPPED [Match {match_url}]: Error parsing - {str(e)}")
                            continue
                except Exception as e:
                    print(f"SKIPPED [League {league_url}]: {str(e)}")
                    continue
        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()