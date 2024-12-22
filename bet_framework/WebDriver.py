import asyncio
import sys

import aiohttp
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

cookies = {
    "PHPSESSID": "b776eec421db92852618189a451a4c4b",
}
headers = {
     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
}

CHROME_PATH = "C:/Users/Administrator/Downloads/chrome-win64/chrome.exe"
CHROMEDRIVER_PATH = "chromedriver.exe"


class WebDriver:
    def __init__(self, chrome_path=CHROME_PATH):
        self.chrome_path = chrome_path
        self.driver = self.init_driver()

    def init_driver(self):
        options = webdriver.ChromeOptions()
        options.binary_location = self.chrome_path
        options.add_argument('--ignore-certificate-errors')
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')  # Last I checked this was necessary.
        # options.add_experimental_option("detach", True)

        try:
            driver = webdriver.Chrome(service=Service(), options=options)
        except WebDriverException:
            print("Wrong paths!")
            sys.exit()

        return driver


async def _make_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, cookies=cookies, headers=headers, ssl=False) as resp:
            return await resp.text()


def make_request(url):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response_text = loop.run_until_complete(_make_request(url))
    loop.close()
    return response_text
