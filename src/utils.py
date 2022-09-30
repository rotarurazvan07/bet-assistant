import sys
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

CHROME_PATH = "C:/Program Files/Google/Chrome Beta/Application/chrome.exe"
CHROMEDRIVER_PATH = "chromedriver.exe"
CURRENT_TIME = datetime.now()


def init_driver(chrome_path=CHROME_PATH, chromedriver_path=CHROMEDRIVER_PATH):
    options = webdriver.ChromeOptions()
    options.binary_location = chrome_path
    # options.add_argument('--headless')
    # options.add_argument('--disable-gpu')  # Last I checked this was necessary.
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
    except WebDriverException:
        print("Wrong paths!")
        sys.exit()

    return driver
