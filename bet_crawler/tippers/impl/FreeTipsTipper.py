import re
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from core.BaseTipper import BaseTipper
from core.Tip import Tip
from bet_framework.WebDriver import WebDriver

FREETIPS_URL = "https://www.freetips.com/football/fixtures/"
class FreeTipsTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self.web_driver = WebDriver()

    def _get_matches_urls(self):
        self.web_driver.driver.get(FREETIPS_URL)
        time.sleep(0.1)

        matches_urls = []

        page_html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')
        matches_urls += [a.find('a')['href'] for a in page_html.find_all("div", class_="eventNameDC Newsurls")]
        self.web_driver.driver.quit()
        time.sleep(0.4)
        self.web_driver = WebDriver()
        try:
            self.web_driver.driver.get(matches_urls[0])
        except IndexError:
            self.web_driver.driver.quit()
            return []
        time.sleep(0.1)
        page_html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')
        upcoming_matches = page_html.find_all("div", class_="news-stream-wrap")[1:]
        for upc_match in upcoming_matches:
            for event in upc_match.find_all('div', class_="news-stream-item"):
                if "Soccer" in str(event):
                    matches_urls.append(event.find("a").get('href'))

        self.web_driver.driver.quit()
        return matches_urls

    def get_tips(self):
        for match_url in self._get_matches_urls():
            self.web_driver = WebDriver()
            time.sleep(0.5)
            self.web_driver.driver.get(match_url)
            time.sleep(0.1)
            if self.web_driver.driver.page_source is not None:
                html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')

                match_name = html.find("div", class_="betTop").find('h4').get_text().replace('\n', '')
                match_date = html.find("div", class_="betTop").find('div', class_="betTiming").get('data-datezone')

                match_date = (datetime.strptime(match_date, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=3)).strftime(
                    "%Y-%m-%d - %H:%M")

                for tip_html in html.find_all("div", class_="verdictBoxItem"):
                    tip = tip_html.find("div", class_="hedTextOneVBD").get_text() + " " + tip_html.find("div",
                                                                                                        class_="hedTextOneVBD marketName").get_text()
                    tip_strength = int(
                        re.search(r'(\d+)\s+Unit', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(
                            1))
                    tip_strength = tip_strength * 2 / 5 + 1
                    odds = str(
                        re.search(r'@(\d+\.\d+)', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(1))

                    self.add_tip_callback(Tip(match_name, match_date, tip, tip_strength, "FreeTips", odds))

            self.web_driver.driver.quit()
