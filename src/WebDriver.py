import sys
import requests
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent

ua = UserAgent()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'}

CHROME_PATH = "C:/Program Files/Google/Chrome Beta/Application/chrome.exe"
CHROMEDRIVER_PATH = "D:/ChromeDriver/chromedriver-win64/chromedriver.exe"


class WebDriver:
    def __init__(self, chrome_path=CHROME_PATH, chrome_webdriver_path=CHROMEDRIVER_PATH):
        self.chrome_path = chrome_path
        self.chrome_webdriver_path = chrome_webdriver_path
        self.driver = self.init_driver()

    def init_driver(self):
        options = webdriver.ChromeOptions()
        options.binary_location = self.chrome_path
        # options.add_argument('--headless')
        # options.add_argument('--disable-gpu')  # Last I checked this was necessary.
        options.add_experimental_option("detach", True)

        try:
            driver = webdriver.Chrome(service=Service(self.chrome_webdriver_path), options=options)
        except WebDriverException:
            print("Wrong paths!")
            sys.exit()

        return driver


def make_request(url):
    # Set up a session
    session = requests.Session()
    session.headers.update({'User-Agent': ua.random})
    # Now, make a request to a website
    response = session.get(url)
    response = response.text
    return response
