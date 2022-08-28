"""
Bet assistant, 2022
"""
from datetime import datetime, timedelta
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"

CHROME_PATH = "ADD YOUR CHROME PATH"
CHROMEDRIVER_PATH = "ADD YOUR CHROMEDRIVER PATH"

current_time = datetime.now()


class Team:
    def __init__(self, name, league_points, form):
        self.name = name
        self.league_points = league_points
        self.form = form


class Match:
    def __init__(self, home_team, away_team, match_datetime,
                 forebet_prediction, forebet_score):
        self.home_team = home_team
        self.away_team = away_team
        self.match_datetime = match_datetime
        self.forebet_prediction = forebet_prediction
        self.forebet_score = forebet_score


def init_driver(chrome_path, chromedriver_path):
    options = webdriver.ChromeOptions()
    options.binary_location = chrome_path
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
    except WebDriverException:
        print("Wrong paths!")
        return None

    return driver


def get_all_matches_html(url, driver):
    driver.get(url)
    time.sleep(5)

    # Press the "Show more" button at the bottom of the page by running the script it is executing
    for i in range(11, 30):
        driver.execute_script("ltodrows(\"1x2\"," + str(i) + ",\"\");")
        time.sleep(1)

    html = BeautifulSoup(driver.page_source, 'html.parser')
    driver.close()

    return html


def get_matches_from_html(html):
    matches = []

    # For every fixture, extract the referenced URL in order to extract information on teams
    matches_urls = [a['href'] for a in html.find_all('a', class_="tnmscn", itemprop="url")]

    for match_url in matches_urls:
        # Get Fixture html source
        try:
            r = requests.get(match_url) if FOREBET_URL in match_url else requests.get(FOREBET_URL + match_url)
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
                if match_datetime > current_time:
                    # Get teams names
                    home_team_name = match_html.find('span', itemprop="homeTeam").get_text().strip()
                    away_team_name = match_html.find('span', itemprop="awayTeam").get_text().strip()

                    # Get league points
                    home_index = 0 if home_team_name in str(
                        match_html.find_all('tr', style=" background-color: #FFD463;font-weight: bold;")[0]) \
                        else 1
                    league_standings = match_html.find_all('tr', style=" background-color: #FFD463;font-weight: bold;")
                    home_team_points = int(league_standings[home_index].get_text().split('\n')[3])
                    away_team_points = int(league_standings[not home_index].get_text().split('\n')[3])

                    # Get teams form
                    home_team_form = match_html.find_all('div', class_="prformcont")[0].get_text()
                    away_team_form = match_html.find_all('div', class_="prformcont")[1].get_text()

                    # Create Team objects for home and away
                    home_team = Team(home_team_name, home_team_points, home_team_form)
                    away_team = Team(away_team_name, away_team_points, away_team_form)

                    print(home_team.name + " vs " + away_team.name)
        except Exception as e:
            print("error: " + str(e))
            continue

    return matches


if __name__ == "__main__":
    browser_driver = init_driver(CHROME_PATH, CHROMEDRIVER_PATH)
    if browser_driver is None:
        quit()
    matches_html = get_all_matches_html(FOREBET_ALL_PREDICTIONS_URL, browser_driver)
    matches_list = get_matches_from_html(matches_html)
