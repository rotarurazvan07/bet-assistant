import os
import threading
import time
import requests
import xlsxwriter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from src.utils import CURRENT_TIME, init_driver

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"

MATCH_VALUE_THRESHOLD = 20
NUM_THREADS = 4


class Team:
    def __init__(self, name, league_points, form):
        self.name = name
        self.league_points = league_points
        self.form = form

    # Team value is represented by an integer by adding
    # the league points and the obtained points minus the losses
    # in the last 6 matches (recent form)
    def get_team_value(self):
        form_value = 3 * self.form.count("W") + 1 * self.form.count("D") - 3 * self.form.count("L")
        return form_value + self.league_points


class Match:
    def __init__(self, home_team, away_team, match_datetime, match_value,
                 forebet_prediction, forebet_score):
        self.home_team = home_team
        self.away_team = away_team
        self.match_datetime = match_datetime
        self.match_value = match_value
        self.forebet_prediction = forebet_prediction
        self.forebet_score = forebet_score

    # return match data in list form to be written in the Excel file
    def get_match_data(self):
        return [self.home_team.name, self.away_team.name, str(self.match_datetime.date()),
                str(self.match_datetime.time()),
                self.home_team.league_points, self.away_team.league_points,
                self.home_team.form, self.away_team.form,
                self.match_value,
                self.forebet_prediction, self.forebet_score]


class ValueFinder:
    def __init__(self):
        self.driver = init_driver()
        self.matches_urls = []  # list of urls of matches from forebet
        self.value_matches = []  # list of Match object based on value criteria
        self._scanned_matches = 0

    def _get_matches_from_html(self, url):
        self.driver.get(url)
        time.sleep(5)

        # Press the "Show more" button at the bottom of the page by running the script it is executing
        for i in range(11, 30):
            self.driver.execute_script("ltodrows(\"1x2\"," + str(i) + ",\"\");")
            time.sleep(1)

        html = BeautifulSoup(self.driver.page_source, 'html.parser')
        self.driver.close()

        self.matches_urls = [a['href'] for a in html.find_all('a', class_="tnmscn", itemprop="url")]

    def _info_log(self):
        t = threading.current_thread()
        time_counter = 0
        while getattr(t, "do_run", True):
            os.system('cls')
            time_counter += 1
            print("Scanning match " + str(self._scanned_matches) + " out of " + str(len(self.matches_urls)))
            print("Found " + str(len(self.value_matches)) + " value matches")
            time.sleep(1)
        print("Elapsed time: " + str(time_counter) + " seconds")

    def _find_value_matches(self, matches_urls):
        for match_url in matches_urls:
            self._scanned_matches += 1

            # Get Fixture html source
            try:
                r = requests.get(match_url, timeout=1000) \
                    if FOREBET_URL in match_url else requests.get(FOREBET_URL + match_url, timeout=1000)
            except requests.exceptions.RequestException:
                print("Request error")
                continue

            match_html = BeautifulSoup(r.text, 'html.parser')

            try:
                # We only look for matches in leagues
                if "Standings" in r.text:
                    match_datetime = datetime.strptime(
                        match_html.find('div', class_="date_bah").get_text().strip().rsplit(' ', 1)[0],
                        "%d/%m/%Y %H:%M") + timedelta(hours=1)
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
                        home_team_form = match_html.find_all('div', class_="prformcont")[0].get_text()
                        away_team_form = match_html.find_all('div', class_="prformcont")[1].get_text()

                        # Create Team objects for home and away
                        home_team = Team(home_team_name, home_team_points, home_team_form)
                        away_team = Team(away_team_name, away_team_points, away_team_form)

                        # calculate h2h_bias as points difference between them
                        h2h_results = match_html.find_all('div', class_="st_row_perc")[0]
                        h2h_home_wins = int(h2h_results.find('div', class_="st_perc_stat winres").find('div').find_all('span')[1].get_text())
                        h2h_away_wins = int(h2h_results.find('div', class_="st_perc_stat winres2").find('div').find_all('span')[1].get_text())
                        h2h_bias = 3 * (h2h_home_wins - h2h_away_wins)

                        # Calculate the difference of value between teams and add bias
                        # positive bias means home advantage on h2h, negative otherwise
                        if h2h_bias <= 0:
                            match_value = abs(home_team.get_team_value() - (-h2h_bias + away_team.get_team_value()))
                        else:
                            match_value = abs((h2h_bias + home_team.get_team_value()) - away_team.get_team_value())

                        # Add Match object to list only if higher value than MATCH_VALUE_THRESHOLD
                        if match_value > MATCH_VALUE_THRESHOLD:
                            forebet_prediction = ' '.join([child.get_text() for child in
                                                           match_html.find('div', class_="rcnt tr_0").
                                                          find('div', class_="fprc").children])
                            forebet_score = match_html.find_all('div', class_="ex_sc tabonly")[-1].get_text()
                            self.value_matches.append(Match(home_team, away_team, match_datetime, match_value,
                                                            forebet_prediction, forebet_score))
            except Exception as e:
                print("error: " + str(e))
                continue

    def get_values(self, log=True):
        self._get_matches_from_html(FOREBET_ALL_PREDICTIONS_URL)

        threads = []

        logging_thread = threading.Thread(target=self._info_log)
        if log:
            logging_thread.start()

        for i in range(NUM_THREADS):
            lower_bound = int(i * len(self.matches_urls) / NUM_THREADS)
            upper_bound = int((i + 1) * len(self.matches_urls) / NUM_THREADS)
            match_list = self.matches_urls[lower_bound:upper_bound]
            threads.append(threading.Thread(target=self._find_value_matches, args=(match_list,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        if log:
            logging_thread.do_run = False
            logging_thread.join()

        return self.value_matches


def export_matches(match_list):
    # If folder doesn't exist, then create it.
    if not os.path.isdir("output"):
        os.makedirs("output")
    # Create an Excel spreadsheet in the directory where the script is called
    workbook = xlsxwriter.Workbook('output/Values-' + str(CURRENT_TIME.date()) +
                                   "_" + str(CURRENT_TIME.time().hour) +
                                   "-" + str(CURRENT_TIME.time().minute) + '.xlsx')
    worksheet = workbook.add_worksheet()
    headers = ["Home", "Away", "Day", "Hour", "Home Points", "Away Points", "Home Form", "Away Form",
               "Match Value", "1x2 % Prediction", "Forebet Score"]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)

    match_list.sort(key=lambda x: x.match_value, reverse=True)

    for match_no, match in enumerate(match_list):
        for column, data in enumerate(match.get_match_data()):
            worksheet.write(match_no + 1, column, data)

    workbook.close()
