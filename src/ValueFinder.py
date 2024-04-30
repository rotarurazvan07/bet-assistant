import os
import threading
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from src.Match import Match
from src.Team import Team
from src.WebDriver import WebDriver, make_request
from src.utils import CURRENT_TIME, log

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"

MATCH_VALUE_THRESHOLD = 20
NUM_THREADS = 4


class ValueFinder:
    def __init__(self):
        self.web_driver = WebDriver()
        self.matches_urls = self._get_matches_from_html(FOREBET_ALL_PREDICTIONS_URL)
        self.matches = []
        self._scanned_matches = 0

    def _get_matches_from_html(self, url):
        self.web_driver.driver.get(url)
        time.sleep(1)
        # Press the "Show more" button at the bottom of the page by running the script it is executing
        for i in range(11, 12): #30
            self.web_driver.driver.execute_script("ltodrows(\"1x2\"," + str(i) + ",\"\");")
            time.sleep(1)

        html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')
        self.web_driver.driver.close()

        return [a['href'] for a in html.find_all('a', class_="tnmscn", itemprop="url")]

    def find_value_matches(self):
        info_thread = threading.Thread(target=self._log_progress)
        info_thread.start()

        threads = []
        for i in range(NUM_THREADS):
            matches_urls_slice = self.matches_urls[int(i*len(self.matches_urls)/NUM_THREADS):
                                                   int((i+1)*len(self.matches_urls)/NUM_THREADS)]
            threads.append(threading.Thread(target=self._find_value_matches_job, args=(matches_urls_slice,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        info_thread.do_run = False
        info_thread.join()

        return self.matches

    def _log_progress(self):
        while getattr(threading.current_thread(), "do_run", True):
            os.system('cls')
            print("Scanning match " + str(self._scanned_matches) + " out of " + str(len(self.matches_urls)))
            print("Saved " + str(len(self.matches)) + " matches")
            time.sleep(1)

    def _find_value_matches_job(self, matches_urls):
        for match_url in matches_urls:
            self._scanned_matches += 1

            # Get Fixture html source
            match_url = match_url if FOREBET_URL in match_url else FOREBET_URL + match_url
            request_result = make_request(match_url)

            if request_result is not None:
                page_html = request_result
                match_html = BeautifulSoup(page_html, 'html.parser')

                try:
                    # We only look for matches in leagues
                    if "Standings of both teams" in page_html:
                        match_datetime = match_html.find('time', itemprop='startDate').find('div', class_='date_bah').text.replace(' GMT', '')
                        match_datetime = datetime.strptime(match_datetime, "%d/%m/%Y %H:%M") + timedelta(hours=1)
                        # Skip finished matches
                        if match_datetime > CURRENT_TIME:
                            # Get teams names
                            home_team_name = match_html.find('span', itemprop="homeTeam").get_text().strip()
                            away_team_name = match_html.find('span', itemprop="awayTeam").get_text().strip()

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

                            # Create Team objects for home and away
                            home_team = Team(home_team_name, home_team_points, home_team_form)
                            away_team = Team(away_team_name, away_team_points, away_team_form)

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
                                h2h_results = (h2h_home_wins, h2h_draws, h2h_away_wins)
                            except:
                                h2h_results = (0, 0, 0)

                            forebet_probability = ' '.join([child.get_text() for child in
                                                            match_html.find('div', class_="rcnt tr_0").
                                                           find('div', class_="fprc").children])
                            forebet_score = match_html.find_all('div', class_="ex_sc tabonly")[-1].get_text()

                            self.matches.append(Match(home_team, away_team, match_datetime,
                                                      forebet_score, forebet_probability,
                                                      h2h_results))
                except Exception as e:
                    print("error: " + str(e))
                    continue
