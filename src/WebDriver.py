import sys
import aiohttp
import asyncio
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

cookies = {
    "PHPSESSID": "93c484077209f41a462e39d68f8c1d7a"
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'}

CHROME_PATH = "C:/Program Files/Google/Chrome Beta/Application/chrome.exe"
CHROMEDRIVER_PATH = "chromedriver.exe"


class WebDriver:
    def __init__(self, chrome_path=CHROME_PATH, chrome_webdriver_path=CHROMEDRIVER_PATH):
        self.chrome_path = chrome_path
        self.chrome_webdriver_path = chrome_webdriver_path
        self.driver = self.init_driver()

    def init_driver(self):
        options = webdriver.ChromeOptions()
        options.binary_location = self.chrome_path
        options.add_argument('--ignore-certificate-errors')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # options.add_argument('--headless')
        # options.add_argument('--disable-gpu')  # Last I checked this was necessary.
        options.add_experimental_option("detach", True)

        try:
            driver = webdriver.Chrome(service=Service(self.chrome_webdriver_path), options=options)
        except WebDriverException:
            print("Wrong paths!")
            sys.exit()

        return driver


async def _make_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, cookies=cookies, headers=headers) as resp:
            return await resp.text()


def make_request(url):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response_text = loop.run_until_complete(_make_request(url))
    loop.close()
    return response_text
