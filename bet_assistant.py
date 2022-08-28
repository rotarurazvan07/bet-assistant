"""
Bet assistant, 2022
"""
from selenium import webdriver

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"

CHROME_PATH = "ADD YOUR CHROME PATH"
CHROMEDRIVER_PATH = "ADD YOUR CHROMEDRIVER PATH"


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


if __name__ == "__main__":
    browser_driver = init_driver(CHROME_PATH, CHROMEDRIVER_PATH)
    if browser_driver is None:
        quit()
