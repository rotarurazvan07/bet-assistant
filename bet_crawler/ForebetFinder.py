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

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
NUM_THREADS = 2


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

            # Extract match URLs
            links = soup.find_all('a', class_="tnmscn", itemprop="url")
            match_urls = list(dict.fromkeys(
                a['href'] for a in links if a.get('href')
            ))

            print(f"Found {len(match_urls)} matches to scan")
            return match_urls

        finally:
            self.web_scraper.destroy_current_thread()

    def get_matches(self):
        """Main function to scrape all matches in parallel."""
        self._scanned_matches = 0
        self._stop_logging = False

        # Get all match URLs
        matches_urls = self._get_matches_from_html(FOREBET_ALL_PREDICTIONS_URL)

        # Create a shared scraper using the 'slow' profile (Forebet is heavier)
        self.get_web_scraper(profile='slow')

        # Run worker jobs using the base helper which starts/stops progress logging
        self.run_workers(matches_urls, self._find_matches_job, num_threads=NUM_THREADS)

        print(f"Finished scanning {self._scanned_matches} matches")

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

                # Ensure full URL
                if FOREBET_URL not in match_url:
                    match_url = FOREBET_URL + match_url

                # Load page with smart retry
                html = self.web_scraper.fast_http_request(
                    match_url,
                    required_content=['itemprop="homeTeam"'],
                    min_content_length=3000
                )

                try:
                    match_html = BeautifulSoup(html, 'html.parser')

                    # Skip cup matches
                    league_btn = match_html.find("a", class_="leagpred_btn")
                    if league_btn and "Cup" in league_btn.get_text():
                        print(f"SKIPPED [{match_url}]: Cup match detected")
                        continue

                    # Only process league matches
                    # TODO : Standings up to
                    if (
                        "standings of both teams" not in html.lower()
                        and "standings up to" not in html.lower()
                    ):
                        print(f"SKIPPED [{match_url}]: Not a league match (no standings found)")
                        continue


                    # Get match datetime
                    match_datetime_elem = match_html.find('time', itemprop='startDate')
                    if not match_datetime_elem:
                        print(f"SKIPPED [{match_url}]: No datetime element found")
                        continue

                    date_elem = match_datetime_elem.find('div', class_='date_bah')
                    if not date_elem:
                        print(f"SKIPPED [{match_url}]: No date element found")
                        continue

                    match_datetime = date_elem.text.replace(' GMT', '')
                    match_datetime = datetime.strptime(match_datetime, "%d/%m/%Y %H:%M")

                    # Get team names
                    home_team_elem = match_html.find('span', itemprop="homeTeam")
                    away_team_elem = match_html.find('span', itemprop="awayTeam")

                    if not home_team_elem or not away_team_elem:
                        print(f"SKIPPED [{match_url}]: Team names not found")
                        continue

                    home_team_name = home_team_elem.get_text().strip()
                    away_team_name = away_team_elem.get_text().strip()

                    # Get league standings
                    league_standings = match_html.find_all('tr', style=" background-color: #FFD463;font-weight: bold;")
                    if len(league_standings) < 2:
                        print(f"SKIPPED [{match_url}]: Insufficient league standings data ({home_team_name} vs {away_team_name})")
                        continue

                    home_index = 0 if home_team_name in str(league_standings[0]) else 1

                    try:
                        home_team_points = int(league_standings[home_index].get_text().split('\n')[3])
                        away_team_points = int(league_standings[1 - home_index].get_text().split('\n')[3])
                    except (IndexError, ValueError) as e:
                        print(f"SKIPPED [{match_url}]: Failed to parse league points ({home_team_name} vs {away_team_name}) - {str(e)}")
                        continue

                    # Get team form
                    form_elements = match_html.find_all('div', class_="prformcont")
                    if len(form_elements) < 2:
                        print(f"SKIPPED [{match_url}]: Team form data incomplete ({home_team_name} vs {away_team_name})")
                        continue

                    home_team_form = form_elements[0].get_text()
                    away_team_form = form_elements[1].get_text()

                    # Extract statistics
                    def safe_extract(selector, attr_name=None, index=0, default=0):
                        try:
                            if attr_name:
                                elements = match_html.find_all(attr_name, selector)
                            else:
                                elements = match_html.find('table', class_=selector).find("tbody").find_all("tr")[index].find_all("td")
                            return elements if elements else []
                        except:
                            return []

                    avg_corners = safe_extract("os_bg os_others_table", index=1)
                    avg_offsides = safe_extract("os_bg os_others_table", index=4)
                    avg_gk_saves = safe_extract("os_bg os_others_table", index=6)
                    avg_yellow_card = safe_extract("os_bg os_others_table __aggresssion", index=1)
                    avg_fouls = safe_extract("os_bg os_others_table __aggresssion", index=2)
                    avg_tackles = safe_extract("os_bg os_others_table __aggresssion", index=3)
                    avg_scored = safe_extract({'data-stat': 'scr_avg'}, 'span')
                    avg_conceded = safe_extract({'data-stat': 'cnd_avg'}, 'span')
                    shots_total_avg = safe_extract({'data-stat': 'shots_total_avg'}, 'span')
                    shot_on_target = safe_extract({'data-stat': 'shots_on_target'}, 'span')
                    avg_possession = safe_extract({'data-stat': 'ball_poss'}, 'span')

                    def get_stat(elements, index, default=None):
                        try:
                            return float(elements[index].get_text().replace("%", ""))
                        except:
                            return default

                    home_team_statistics = TeamStatistics(
                        avg_corners=get_stat(avg_corners, 0),
                        avg_offsides=get_stat(avg_offsides, 0),
                        avg_gk_saves=get_stat(avg_gk_saves, 0),
                        avg_yellow_cards=get_stat(avg_yellow_card, 0),
                        avg_fouls=get_stat(avg_fouls, 0),
                        avg_tackles=get_stat(avg_tackles, 0),
                        avg_scored=get_stat(avg_scored, 0),
                        avg_conceded=get_stat(avg_conceded, 0),
                        avg_shots_on_target=round(get_stat(shots_total_avg, 0) * get_stat(shot_on_target, 0) / 100, 2) if shots_total_avg and shot_on_target else None,
                        avg_possession=avg_possession[0].get_text() if avg_possession else None
                    )

                    away_team_statistics = TeamStatistics(
                        avg_corners=get_stat(avg_corners, -1),
                        avg_offsides=get_stat(avg_offsides, -1),
                        avg_gk_saves=get_stat(avg_gk_saves, -1),
                        avg_yellow_cards=get_stat(avg_yellow_card, -1),
                        avg_fouls=get_stat(avg_fouls, -1),
                        avg_tackles=get_stat(avg_tackles, -1),
                        avg_scored=get_stat(avg_scored, -1),
                        avg_conceded=get_stat(avg_conceded, -1),
                        avg_shots_on_target=round(get_stat(shots_total_avg, -1) * get_stat(shot_on_target, -1) / 100, 2) if shots_total_avg and shot_on_target else None,
                        avg_possession=avg_possession[-1].get_text() if avg_possession else None
                    )

                    # Create teams
                    home_team = Team(home_team_name, home_team_points, home_team_form, home_team_statistics)
                    away_team = Team(away_team_name, away_team_points, away_team_form, away_team_statistics)

                    # Get odds
                    odds=None

                    # Get H2H
                    try:
                        h2h_elem = match_html.find_all('div', class_="st_row_perc")[0]
                        h2h_home_wins = int(h2h_elem.find('div', class_="st_perc_stat winres").find('div').find_all('span')[1].get_text())
                        h2h_draws = int(h2h_elem.find('div', class_="st_perc_stat drawres").find('div').find_all('span')[1].get_text())
                        h2h_away_wins = int(h2h_elem.find('div', class_="st_perc_stat winres2").find('div').find_all('span')[1].get_text())
                        h2h_results = H2H(h2h_home_wins, h2h_draws, h2h_away_wins)
                    except:
                        h2h_results = None

                    # Get probability
                    try:
                        forebet_prob_elem = match_html.find('div', class_="rcnt tr_0").find('div', class_="fprc")
                        forebet_prob_text = ' '.join([child.get_text() for child in forebet_prob_elem.children])
                        forebet_prob_tuple = tuple(map(int, forebet_prob_text.split()))
                        forebet_probability = Probability(FOREBET_NAME, forebet_prob_tuple[0], forebet_prob_tuple[1], forebet_prob_tuple[2])
                    except Exception as e:
                        print(f"SKIPPED [{match_url}]: Failed to parse probability ({home_team_name} vs {away_team_name}) - {str(e)}")
                        continue

                    # Get score
                    try:
                        forebet_score_text = match_html.find('div', class_="rcnt tr_0").find("div", class_="ex_sc tabonly").get_text()
                        forebet_score_tuple = tuple(map(int, forebet_score_text.split('-')))
                        forebet_score = Score(FOREBET_NAME, forebet_score_tuple[0], forebet_score_tuple[1])
                    except Exception as e:
                        print(f"SKIPPED [{match_url}]: Failed to parse score prediction ({home_team_name} vs {away_team_name}) - {str(e)}")
                        continue

                    # Create tips
                    tips = []

                    # Main prediction tip
                    result = "Home Win" if forebet_score.home > forebet_score.away else "Draw" if forebet_score.home == forebet_score.away else "Away Win"
                    confidence = float(max(forebet_probability.home, forebet_probability.draw, forebet_probability.away))
                    tips.append(Tip(raw_text=result, confidence=confidence, source=FOREBET_NAME, odds=None))

                    # Over/Under 2.5
                    try:
                        uo_text = match_html.find("div", id="uo_table").find("span", class_="forepr forepr-tx").get_text()
                        uo_prob = int(match_html.find("div", id="uo_table").find("span", class_="fpr").get_text())
                        if uo_prob > 0:
                            # Forebet provides percentage probabilities (0..100); use directly as confidence
                            tips.append(Tip(raw_text=f"{uo_text} 2.5 goals", confidence=float(uo_prob), source=FOREBET_NAME, odds=None))
                    except:
                        pass

                    # BTTS
                    try:
                        btts_text = match_html.find("div", id="bts_table").find("span", class_="forepr").get_text()
                        btts_prob = int(match_html.find("div", id="bts_table").find("span", class_="fpr").get_text())
                        if btts_prob > 0:
                            tips.append(Tip(raw_text=f"BTTS {btts_text}", confidence=float(btts_prob), source=FOREBET_NAME, odds=None))
                    except:
                        pass

                    # Goal scorer
                    try:
                        scorer = match_html.find("div", id="gscr_table").find_all("div", class_="playerPred")[4].get_text()
                        scorer_prob = int(match_html.find("div", id="gscr_table").find_all("div", class_="playerPred")[0].get_text().replace("%", ''))
                        if scorer_prob > 0:
                            tips.append(Tip(raw_text=f"{scorer} to score", confidence=float(scorer_prob), source=FOREBET_NAME, odds=None))
                    except:
                        pass

                    # Corners
                    try:
                        corner_text = match_html.find("div", id="corner_table").find("span", class_="forepr forepr-tx").get_text()
                        corner_prob = int(match_html.find("div", id="corner_table").find("span", class_="fpr").get_text())
                        if corner_prob > 0:
                            tips.append(Tip(raw_text=f"{corner_text} 9.5 corners", confidence=float(corner_prob), source=FOREBET_NAME, odds=None))
                    except:
                        pass

                    # Cards
                    try:
                        card_text = match_html.find("div", id="card_table").find("span", class_="forepr").get_text()
                        card_prob = int(match_html.find("div", id="card_table").find("span", class_="fpr").get_text())
                        if card_prob > 0:
                            tips.append(Tip(raw_text=f"{card_text} 4.5 cards", confidence=float(card_prob), source=FOREBET_NAME, odds=None))
                    except:
                        pass

                    # Create match statistics
                    match_predictions = MatchPredictions(
                        scores=[forebet_score],
                        probabilities=[forebet_probability],
                        tips=tips
                    )

                    # Create match
                    match_to_add = Match(
                        home_team=home_team,
                        away_team=away_team,
                        datetime=match_datetime,
                        predictions=match_predictions,
                        h2h=h2h_results,
                        odds=odds
                    )

                    # Successfully added to database (use wrapper to apply
                    # standard skip/date checks before invoking the callback)
                    self.add_match(match_to_add)

                except Exception as e:
                    print(f"SKIPPED [{match_url}]: Unexpected error during parsing - {str(e)}")
                    continue

        finally:
            # Clean up this thread's browser
            self.destroy_scraper_thread()