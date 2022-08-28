"""
Bet assistant, 2022
"""
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"

CHROME_PATH = "ADD YOUR CHROME PATH"
CHROMEDRIVER_PATH = "ADD YOUR CHROMEDRIVER PATH"


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


if __name__ == "__main__":
    browser_driver = init_driver(CHROME_PATH, CHROMEDRIVER_PATH)
    if browser_driver is None:
        quit()
    matches_html = get_all_matches_html(FOREBET_ALL_PREDICTIONS_URL, browser_driver)
