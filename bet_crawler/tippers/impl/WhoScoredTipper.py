import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium.common import TimeoutException

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score
from bet_crawler.core.Tip import Tip

WHO_SCORED_URL = "https://www.whoscored.com"
WHO_SCORED_NAME = "whoscored"

class WhoScoredTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self._tip_strengths = ["Likely", "Very Likely", "Extremely Likely"]

    def _get_matches_urls(self):
        try:
            request_result = self.web_scraper.load_page(WHO_SCORED_URL + "/Previews", time_delay=5)
        except TimeoutException:
            request_result = self.web_scraper.get_current_page()
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            matches_table_anchor = html.find("table", class_="grid")
            matches_urls = [a['href'] for a in matches_table_anchor.find_all('a') if "Matches" in a['href']]
            return matches_urls

    def get_tips(self):
        for match_url in self._get_matches_urls():
            try:
                request_result = self.web_scraper.load_page(WHO_SCORED_URL + match_url, time_delay=5)
            except TimeoutException:
                request_result = self.web_scraper.get_current_page()
            if request_result is not None:
                match_html = BeautifulSoup(request_result, 'html.parser')

                home_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                    r'home team')).get_text()
                away_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                    r'away team')).get_text()
                match_name = home_team + " - " + away_team

                match_time = match_html.find('dt', text='Date:').find_next_sibling('dd').text + " - " + \
                             match_html.find('dt', text='Kick off:').find_next_sibling('dd').text

                match_time = datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(hours=2)

                side_box = match_html.find('table', class_="grid teamcharacter")

                score = match_html.find("div", id="preview-prediction").find_all("span", class_="predicted-score")
                score = Score(WHO_SCORED_NAME, score[0].get_text(), score[1].get_text())
                try:
                    for tip_html in side_box.findAll('tr'):
                        tip = tip_html.get_text().strip()
                        tip_strength = self._tip_strengths.index(tip_html.find('span')['title'].strip()) + 1
                        self.add_tip_callback(match_name, match_time, tip=Tip(tip, tip_strength, WHO_SCORED_NAME), score=score)
                except AttributeError:
                    continue

        self.web_scraper.destroy_driver()







