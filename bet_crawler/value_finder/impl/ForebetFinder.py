import re
import threading
import time
from datetime import datetime
from re import match

from bs4 import BeautifulSoup

from bet_crawler.core.BaseValueFinder import BaseValueFinder
from bet_crawler.core.Match import Match
from bet_crawler.core.MatchStatistics import MatchStatistics, Score, Probability, H2H
from bet_crawler.core.Team import Team, TeamStatistics
from bet_crawler.core.Tip import Tip
from bet_framework.utils import CURRENT_TIME

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"

NUM_THREADS = 6

# TODO - rework like tips
class ForebetFinder(BaseValueFinder):
    def __init__(self, add_value_match_callback):
        super().__init__(add_value_match_callback)
        self._scanned_matches = 0

    def _get_matches_from_html(self, url):
        self.web_scraper.load_page(url, mode="driver")
        time.sleep(1)
        # Press the "Show more" button at the bottom of the page by running the script it is executing
        for i in range(11, 30):
            self.web_scraper.custom_call("execute_script", "ltodrows(\"1x2\"," + str(i) + ",\"\");")
            time.sleep(1)

        html = BeautifulSoup(self.web_scraper.get_current_page(), 'html.parser')
        self.web_scraper.destroy_driver()

        return list(set([a['href'] for a in html.find_all('a', class_="tnmscn", itemprop="url")]))

    def get_value_matches(self):
        self._scanned_matches = 0
        matches_urls = self._get_matches_from_html(FOREBET_ALL_PREDICTIONS_URL)
        self.web_scraper.init_multi_drivers(NUM_THREADS)

        info_thread = threading.Thread(target=self._log_progress, args=(matches_urls,))
        info_thread.start()

        threads = []
        for i in range(NUM_THREADS):
            matches_urls_slice = matches_urls[int(i * len(matches_urls) / NUM_THREADS):
                                              int((i + 1) * len(matches_urls) / NUM_THREADS)]
            threads.append(threading.Thread(target=self._find_value_matches_job, args=(matches_urls_slice, i)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        info_thread.do_run = False
        info_thread.join()

    def _log_progress(self, matches_urls):
        while getattr(threading.current_thread(), "do_run", True):
            print("Scanning match " + str(self._scanned_matches) + " out of " + str(len(matches_urls)))
            time.sleep(1)

    # TODO - some entries are doubled
    def _find_value_matches_job(self, matches_urls, driver_index):
        for match_url in matches_urls:
            self._scanned_matches += 1

            # Get Fixture html source
            match_url = match_url if FOREBET_URL in match_url else FOREBET_URL + match_url
            request_result = self.web_scraper.load_page(match_url, time_delay=0.1, driver_index=driver_index)

            if request_result is not None:
                page_html = request_result
                try:
                    match_html = BeautifulSoup(page_html, 'html.parser')
                    if "Cup" in match_html.find("a", class_="leagpred_btn").get_text():
                        continue  # cup match
                    # We only look for matches in leagues
                    if "Standings of both teams" in page_html:
                        match_datetime = match_html.find('time', itemprop='startDate').find('div',
                                                                                            class_='date_bah').text.replace(
                            ' GMT', '')
                        match_datetime = datetime.strptime(match_datetime, "%d/%m/%Y %H:%M")
                        # Skip finished matches
                        if match_datetime > CURRENT_TIME:
                            # Get teams names
                            home_team_name = match_html.find('span', itemprop="homeTeam").get_text().strip()
                            away_team_name = match_html.find('span', itemprop="awayTeam").get_text().strip()

                            # No U or W games
                            if re.search(r"\bU\d{2}s?\b", home_team_name) or \
                                re.search(r"\bU\d{2}s?\b", away_team_name) or \
                                re.search(r"\bW\b", home_team_name) or \
                                re.search(r"\bW\b", away_team_name) or \
                                re.search(r"\bII\b", home_team_name) or \
                                re.search(r"\bII\b", away_team_name) or \
                                re.search(r"\bIII\b", home_team_name) or \
                                re.search(r"\bIII\b", away_team_name) or \
                                re.search(r"\bB\b", home_team_name) or \
                                re.search(r"\bB\b", away_team_name) or \
                                re.search(r"\bC\b", home_team_name) or \
                                re.search(r"\bC\b", away_team_name):
                                print(f"Skipped {home_team_name} vs {away_team_name}")
                                continue

                            # Get league points
                            home_index = 0 if home_team_name in str(
                                match_html.find_all('tr', style=" background-color: #FFD463;font-weight: bold;")[0]) \
                                else 1
                            league_standings = match_html.find_all('tr',
                                                                   style=" background-color: #FFD463;font-weight: bold;")
                            home_team_points = int(league_standings[home_index].get_text().split('\n')[3])
                            away_team_points = int(league_standings[not home_index].get_text().split('\n')[3])

                            # Get teams form
                            # TODO - change form to home / away form
                            home_team_form = match_html.find_all('div', class_="prformcont")[0].get_text()
                            away_team_form = match_html.find_all('div', class_="prformcont")[1].get_text()

                            avg_corners_html = match_html.find('table', class_="os_bg os_others_table").find("tbody").find_all("tr")[1].find_all("td")
                            avg_offsides_html = match_html.find('table', class_="os_bg os_others_table").find("tbody").find_all("tr")[4].find_all("td")
                            avg_gk_saves_html = match_html.find('table', class_="os_bg os_others_table").find("tbody").find_all("tr")[6].find_all("td")
                            avg_yellow_card_html = match_html.find('table', class_="os_bg os_others_table __aggresssion").find("tbody").find_all("tr")[1].find_all("td")
                            avg_fouls_html = match_html.find('table', class_="os_bg os_others_table __aggresssion").find("tbody").find_all("tr")[2].find_all("td")
                            avg_tackles_html = match_html.find('table', class_="os_bg os_others_table __aggresssion").find("tbody").find_all("tr")[3].find_all("td")
                            avg_scored_html = match_html.find_all("span", {'data-stat': 'scr_avg'})
                            avg_conceded_html = match_html.find_all("span", {'data-stat': 'cnd_avg'})
                            shots_total_avg_html = match_html.find_all("span", {'data-stat': 'shots_total_avg'})
                            shot_on_target_html = match_html.find_all("span", {'data-stat': 'shots_on_target'})
                            avg_possession_html = match_html.find_all("span", {'data-stat': 'ball_poss'})

                            home_team_statistics = TeamStatistics(
                                avg_corners=float(avg_corners_html[0].get_text()) if avg_corners_html else 0,
                                avg_offsides=float(avg_offsides_html[0].get_text()) if avg_offsides_html else 0,
                                avg_gk_saves=float(avg_gk_saves_html[0].get_text()) if avg_gk_saves_html else 0,
                                avg_yellow_cards=float(avg_yellow_card_html[0].get_text()) if avg_yellow_card_html else 0,
                                avg_fouls=float(avg_fouls_html[0].get_text()) if avg_fouls_html else 0,
                                avg_tackles=float(avg_tackles_html[0].get_text()) if avg_tackles_html else 0,
                                avg_scored=float(avg_scored_html[0].get_text()) if avg_scored_html else 0,
                                avg_conceded=float(avg_conceded_html[0].get_text()) if avg_conceded_html else 0,
                                avg_shots_on_target=round(float(shots_total_avg_html[0].get_text()) * float(shot_on_target_html[0].get_text().replace("%",'')) / 100
                                                    if shots_total_avg_html and shot_on_target_html else 0, 2),
                                avg_possession=avg_possession_html[0].get_text() if avg_possession_html else "0"
                            )
                            away_team_statistics = TeamStatistics(
                                avg_corners=float(avg_corners_html[-1].get_text()) if avg_corners_html else 0,
                                avg_offsides=float(avg_offsides_html[-1].get_text()) if avg_offsides_html else 0,
                                avg_gk_saves=float(avg_gk_saves_html[-1].get_text()) if avg_gk_saves_html else 0,
                                avg_yellow_cards=float(avg_yellow_card_html[-1].get_text()) if avg_yellow_card_html else 0,
                                avg_fouls=float(avg_fouls_html[-1].get_text()) if avg_fouls_html else 0,
                                avg_tackles=float(avg_tackles_html[-1].get_text()) if avg_tackles_html else 0,
                                avg_scored=float(avg_scored_html[-1].get_text()) if avg_scored_html else 0,
                                avg_conceded=float(avg_conceded_html[-1].get_text()) if avg_conceded_html else 0,
                                avg_shots_on_target=round(float(shots_total_avg_html[-1].get_text()) * float(shot_on_target_html[-1].get_text().replace("%", '')) / 100
                                                    if shots_total_avg_html and shot_on_target_html else 0, 2),
                                avg_possession=avg_possession_html[-1].get_text() if avg_possession_html else "0"
                            )

                            # Create Team objects for home and away
                            home_team = Team(home_team_name, home_team_points, home_team_form, home_team_statistics)
                            away_team = Team(away_team_name, away_team_points, away_team_form, away_team_statistics)

                            # TODO - try getting external odds
                            try:
                                odds = float(
                                    match_html.find('div', class_="rcnt tr_0").find('span', class_="lscrsp").get_text())
                            except:
                                odds = 0

                            # calculate h2h_bias as points difference between them
                            try:
                                h2h_results = match_html.find_all('div', class_="st_row_perc")[0]
                                h2h_home_wins = int(
                                    h2h_results.find('div', class_="st_perc_stat winres").find('div').find_all('span')[
                                        1].get_text())
                                h2h_draws = int(
                                    h2h_results.find('div', class_="st_perc_stat drawres").find('div').find_all('span')[
                                        1].get_text())
                                h2h_away_wins = int(
                                    h2h_results.find('div', class_="st_perc_stat winres2").find('div').find_all('span')[
                                        1].get_text())
                                h2h_results = H2H(h2h_home_wins, h2h_draws, h2h_away_wins)
                            except:
                                h2h_results = H2H(0, 0, 0)

                            forebet_probability = ' '.join([child.get_text() for child in
                                                            match_html.find('div', class_="rcnt tr_0").
                                                           find('div', class_="fprc").children])
                            forebet_probability = tuple(map(int, forebet_probability.split()))
                            forebet_probability = Probability(FOREBET_NAME, forebet_probability[0], forebet_probability[1], forebet_probability[2])

                            forebet_score = match_html.find('div', class_="rcnt tr_0").find("div", class_="ex_sc tabonly").get_text()
                            forebet_score = tuple(map(int, forebet_score.split('-')))
                            forebet_score = Score(FOREBET_NAME, forebet_score[0], forebet_score[1])

                            tips = []
                            tips.append(Tip(
                                "Home Win" if forebet_score.home > forebet_score.away else
                                "Draw" if forebet_score.home == forebet_score.away else
                                "Away Win",
                                ((int(max(forebet_probability.home, forebet_probability.draw, forebet_probability.away))  - 33) / 67) * 2 + 1,
                                FOREBET_NAME,
                                odds
                            ))
                            try:
                                tips.append(Tip(
                                    match_html.find("div", id="uo_table").find("span", class_="forepr forepr-tx").get_text() + " 2.5 goals",
                                    ((int(match_html.find("div", id="uo_table").find("span", class_="fpr").get_text()) - 50) / 50) * 2 + 1,
                                    FOREBET_NAME,
                                    0
                                ))
                            except AttributeError:
                                pass
                            try:
                                tips.append(Tip(
                                    "BTTS " + match_html.find("div", id="bts_table").find("span", class_="forepr").get_text(),
                                    ((int(match_html.find("div", id="bts_table").find("span", class_="fpr").get_text()) - 50) / 50) * 2 + 1,
                                    FOREBET_NAME,
                                    0
                                ))
                            except AttributeError:
                                pass
                            try:
                                tips.append(Tip(
                                    match_html.find("div", id="gscr_table").find_all("div", class_="playerPred")[4].get_text() + " to score",
                                    (int(match_html.find("div", id="gscr_table").find_all("div", class_="playerPred")[0].get_text().replace("%",'')) / 100) * 2 + 1,
                                    FOREBET_NAME,
                                    0
                                ))
                            except AttributeError and IndexError:
                                pass
                            try:
                                tips.append(Tip(
                                    match_html.find("div", id="corner_table").find("span", class_="forepr forepr-tx").get_text() + " 9.5 corners",
                                    ((int(match_html.find("div", id="corner_table").find("span", class_="fpr").get_text()) - 50) / 50) * 2 + 1,
                                    FOREBET_NAME,
                                    0
                                ))
                            except AttributeError:
                                pass
                            try:
                                tips.append(Tip(
                                    match_html.find("div", id="card_table").find("span", class_="forepr").get_text() + " 4.5 cards",
                                    ((int(match_html.find("div", id="card_table").find("span", class_="fpr").get_text()) - 50) / 50) * 2 + 1,
                                    FOREBET_NAME,
                                    0
                                ))
                            except AttributeError:
                                pass
                            match_statistics_to_add = MatchStatistics(
                                scores = [forebet_score],
                                probabilities = [forebet_probability],
                                h2h = h2h_results,
                                odds = odds,
                                tips = tips
                            )

                            match_to_add = Match(
                                home_team = home_team,
                                away_team = away_team,
                                datetime = match_datetime,
                                statistics = match_statistics_to_add
                            )

                            self.add_value_match_callback(match_to_add)

                except Exception as e:
                    print(f"error on {match_url}: " + str(e))
                    continue
        self.web_scraper.destroy_driver(driver_index)