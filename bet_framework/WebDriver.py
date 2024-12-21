import sys
import aiohttp
import asyncio
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

cookies = {
    "PHPSESSID": "93c484077209f41a462e39d68f8c1d7a",
    'euconsent-v2':"CQJ7wMAQJ7wMAAKA1AENBVFsAP_gAEPgAAwIKutX_G__bWlr8X73aftkeY1P9_h77sQxBhfJE-4FzLvW_JwXx2ExNA36tqIKmRIAu3TBIQNlGJDURVCgaogVryDMaEyUoTNKJ6BkiFMRM2dYCFxvm4tjeQCY5vr991dx2B-t7dr83dzyy4xHn3a5_2S0WJCdA5-tDfv9bROb-9IOd_x8v4v4_F_pE2_eT1l_tWvp7D9-cts__XW99_fff_9Pn_-uB_-_X_vf_H3gq6ASYaFRAGWRISEGgYQQIAVBWEBFAgCAABIGiAgBMGBTsDABdYSIAQAoABggBAACDIAEAAAkACEQAQAFAgAAgECgADAAgGAgAYGAAMAFgIBAACA6BimBBAIFgAkZkVCmBCEAkEBLZUIJAECCuEIRZ4BEAiJgoAAASACkAAQFgsDiSQErEggC4g2gAAIAEAggAKEUnZgCCAM2WqvBg2jK0wLB8wXPaYBkgRBGTkmAAAAA.f_gAAAAAAAAA",
    'addtl_consent':"1~43.3.9.6.9.13.6.4.15.9.5.2.11.8.1.3.2.10.33.4.15.17.2.9.20.7.20.5.20.7.2.2.1.4.40.4.14.9.3.10.8.9.6.6.9.41.5.3.1.27.1.17.10.9.1.8.6.2.8.3.4.146.65.1.17.1.18.25.35.5.18.9.7.41.2.4.18.24.4.9.6.5.2.14.25.3.2.2.8.28.8.6.3.10.4.20.2.17.10.11.1.3.22.16.2.6.8.6.11.6.5.33.11.19.28.12.1.5.2.17.9.6.40.17.4.9.15.8.7.3.12.7.2.4.1.7.12.13.22.13.2.6.8.10.1.4.15.2.4.9.4.5.4.7.13.5.15.17.4.14.10.15.2.5.6.2.2.1.2.14.7.4.8.2.9.10.18.12.13.2.18.1.1.3.1.1.9.7.2.16.5.19.8.4.8.5.4.8.4.4.2.14.2.13.4.2.6.9.6.3.2.2.3.7.3.6.10.11.9.19.8.3.3.1.2.3.9.19.26.3.10.13.4.3.4.6.3.3.3.4.1.1.6.11.4.1.11.6.1.10.13.3.2.2.4.3.2.2.7.15.7.14.4.3.4.5.4.3.2.2.5.5.3.9.7.9.1.5.3.7.10.11.1.3.1.1.2.1.3.2.6.1.12.8.1.3.1.1.2.2.7.7.1.4.3.6.1.2.1.4.1.1.4.1.1.2.1.8.1.7.4.3.3.3.5.3.15.1.15.10.28.1.2.2.12.3.4.1.6.3.4.7.1.3.1.4.1.5.3.1.3.4.1.5.2.3.1.2.2.6.2.1.2.2.2.4.1.1.1.2.2.1.1.1.1.2.1.1.1.2.2.1.1.2.1.2.1.7.1.7.1.1.1.1.2.1.4.2.1.1.9.1.6.2.1.6.2.3.2.1.1.1.2.5.2.4.1.1.2.2.1.1.7.1.2.2.1.2.1.2.3.1.1.2.4.1.1.1.6.3.6.4.5.9.1.2.3.1.4.3.2.2.3.1.1.1.1.12.1.3.1.1.2.2.1.6.3.3.5.2.7.1.1.2.5.1.9.5.1.3.1.8.4.5.1.9.1.1.1.2.1.1.1.4.2.13.1.1.3.1.2.2.3.1.2.1.1.1.2.1.3.1.1.1.1.2.4.1.5.1.2.4.3.10.2.9.7.2.2.1.3.3.1.6.1.2.5.1.1.2.6.4.2.1.200.200.100.300.400.100.100.100.400.1700.304.596.100.1000.800.500.400.200.200.500.1300.801.99.506.95.1399.1100.100.4302.1798.2100.600.200.100.800.900.100.200.700.100.800.2000.900.1100.600.400.2200.2300.400"
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
        # options.add_argument('--headless')
        # options.add_argument('--disable-gpu')  # Last I checked this was necessary.
        options.add_experimental_option("detach", True)

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
