import asyncio
import time
from urllib.parse import quote

import aiohttp
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.common import TimeoutException

from bet_framework.utils import log


class WebScraper:
    def __init__(self, custom_cookies=None, custom_headers=None, retry_count=3, request_failed_keywords=None, request_retry_keywords=None):
        self.cookies = custom_cookies if custom_cookies else dict()
        self.headers = custom_headers if custom_headers else dict()
        self.request_failed_keywords = request_failed_keywords if request_failed_keywords else []
        self.request_retry_keywords = request_retry_keywords if request_retry_keywords else []
        self.retry_count = retry_count
        self._drivers = dict()

    def init_multi_drivers(self, drivers_count):
        for i in range(drivers_count):
            self._drivers[i] = self.init_driver(undetected=False)

    def destroy_driver(self, driver_index=0):
        if len(self._drivers) > 0:
            try:
                self._drivers[driver_index].quit()
                del self._drivers[driver_index]
            except IndexError:
                print("Wrong driver index")


    def get_current_page(self, driver_index=0):
        try:
            return self._drivers[driver_index].page_source
        except IndexError:
            print("Wrong driver index")

    def custom_call(self, function, *args, driver_index=0):
        """Custom call to dynamically invoke a function on the WebDriver."""
        try:
            """Custom call to dynamically invoke a function on the WebDriver."""
            if self._drivers[driver_index]:
                # Use getattr to call the function dynamically
                func = getattr(self._drivers[driver_index], function, None)
                if callable(func):
                    return func(*args)  # Call the function with provided arguments
                else:
                    raise AttributeError(f"{function} is not a valid function of the WebDriver.")
            else:
                raise Exception("Driver is not initialized.")
        except IndexError:
            print("Wrong driver index")

    def _update_cookies(self, cookies):
        for cookie in cookies:
            self.cookies.update({
                    quote(cookie['name']): cookie['value']
                }
            )

    # mode can be either "driver", "request" or "hybrid"
    # "driver" will only try with a chrome
    # "request" will only try with plain request
    # "hybrid" will try on its own with all methods to return a valid html response, also trying to defeat cloudflare
    # default is "hybrid"
    # time_delay is used on known pages that tend to load a bit because of the underlying javascript
    # preserve_driver tells to keep the driver instance saved in the WebDriver object to be REUSED
    # defaulted to True
    def load_page(self, url, time_delay=0, mode="hybrid", driver_index=0):
        # this needs to return the html, no matter how, the fastest
        try:
            html = None
            if mode == "request":
                return self._make_request(url, time_delay)
            elif mode == "driver":
                if not self._drivers:
                    self._drivers[driver_index] = self.init_driver(undetected=False)

                try:
                    self._drivers[driver_index].get(url)
                    time.sleep(time_delay)
                except TimeoutException:
                    pass
                html = self.get_current_page(driver_index)
                self._update_cookies(self._drivers[driver_index].get_cookies())
                # retry with undetected
                if any([keyword in html for keyword in self.request_failed_keywords]):
                    self.destroy_driver(driver_index)
                    self._drivers[driver_index] = self.init_driver(undetected=True)
                    try:
                        self._drivers[driver_index].get(url)
                        time.sleep(time_delay)
                    except TimeoutException:
                        pass
                    html = self.get_current_page(driver_index)
                    self._update_cookies(self._drivers[driver_index].get_cookies())
                return html
            elif mode == "hybrid":
                html = self._make_request(url, time_delay)
                if html is not None:
                    return html

                if not self._drivers:
                    self._drivers[driver_index] = self.init_driver(undetected=False)
                try:
                    self._drivers[driver_index].get(url)
                    time.sleep(time_delay)
                except TimeoutException:
                    pass
                html = self.get_current_page(driver_index)
                self._update_cookies(self._drivers[driver_index].get_cookies())
                # retry with undetected
                if any([keyword in html for keyword in self.request_failed_keywords]):
                    # replace with undetected
                    self.destroy_driver(driver_index)
                    self._drivers[driver_index] = self.init_driver(undetected=True)
                    try:
                        self._drivers[driver_index].get(url)
                        time.sleep(time_delay)
                    except TimeoutException:
                        pass
                    html = self.get_current_page(driver_index)
                    self._update_cookies(self._drivers[driver_index].get_cookies())
            # at the end, it will remain undetected unless destroy_driver is called
            return html
        except IndexError:
            print("Wrong driver index")

    async def _make_async_request(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, cookies=self.cookies, headers=self.headers, ssl=False) as resp:
                return await resp.text()

    def _make_request(self, url, time_delay):
        retry_cnt = 0
        while retry_cnt < self.retry_count:
            log(url)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response_text = loop.run_until_complete(self._make_async_request(url))
            loop.close()
            if any([keyword in response_text for keyword in self.request_retry_keywords]):
                retry_cnt += 1
                time.sleep(time_delay)
                continue
            if any([keyword in response_text for keyword in self.request_failed_keywords]):
                return None
            return response_text
        return None

    def init_driver(self, undetected):
        # TODO - add cookies and headers
        if undetected:
            options = uc.ChromeOptions()
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--incognito')
            for k,v in self.headers.items():
                options.add_argument(k + "=" + v)
            driver = uc.Chrome(options=options)
        else:
            options = webdriver.ChromeOptions()
            options.binary_location = "C:/Users/Administrator/Downloads/chrome-win64/chrome.exe"
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--enable-javascript')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--incognito')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            for k, v in self.headers.items():
                options.add_argument(k + "=" + v)
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(10) # todo - config.yaml
        return driver
