import re
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from core.BaseTipper import BaseTipper
from core.Tip import Tip
from bet_framework.WebDriver import WebDriver

WHO_SCORED_URL = "https://www.whoscored.com"

class WhoScoredTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self.web_driver = WebDriver()
        self._tip_strengths = ["Likely", "Very Likely", "Extremely Likely"]

    def _get_matches_urls(self):
        self.web_driver.driver.get(WHO_SCORED_URL + "/Previews")
        time.sleep(5)
        request_result = self.web_driver.driver.page_source
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            matches_table_anchor = html.find("table", class_="grid")
            matches_urls = [a['href'] for a in matches_table_anchor.find_all('a') if "Matches" in a['href']]
            return matches_urls

    def get_tips(self):
        for match_url in self._get_matches_urls():
            self.web_driver.driver.get(WHO_SCORED_URL + match_url)
            time.sleep(0.1)
            request_result = self.web_driver.driver.page_source
            if request_result is not None:
                match_html = BeautifulSoup(request_result, 'html.parser')

                home_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                    r'home team')).get_text()
                away_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                    r'away team')).get_text()
                match_name = home_team + " - " + away_team

                match_time = match_html.find('dt', text='Date:').find_next_sibling('dd').text + " - " + \
                             match_html.find('dt', text='Kick off:').find_next_sibling('dd').text

                match_time = (datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(
                    hours=2)).strftime("%Y-%m-%d - %H:%M")

                side_box = match_html.find('table', class_="grid teamcharacter")
                try:
                    for tip_html in side_box.findAll('tr'):
                        tip = tip_html.get_text().strip()
                        tip_strength = self._tip_strengths.index(tip_html.find('span')['title'].strip()) + 1
                        self.add_tip_callback(Tip(match_name, match_time, tip, tip_strength, "WhoScored"))
                except AttributeError:
                    continue

        self.web_driver.driver.quit()







