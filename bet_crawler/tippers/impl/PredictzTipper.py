import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score

PREDICTZ_URL = "https://www.predictz.com/predictions/"
PREDICTZ_NAME = "predictz"

class PredictzTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        request_result = self.web_scraper.load_page(PREDICTZ_URL, time_delay=1)
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            matches_urls = [a['href'] for a in html.find("div",class_="calbox").find_all('a')]
            return matches_urls

    def get_tips(self):
        current_time = datetime.now()
        for match_url in self._get_matches_urls():
            request_result = self.web_scraper.load_page(match_url)
            if request_result is not None:
                matches_html = BeautifulSoup(request_result, 'html.parser')
                for match_html in matches_html.find_all("div", class_="pttr ptcnt"):
                    match_name = match_html.find("div", class_="pttd ptgame").find("a").get_text()
                    score = match_html.find("div", class_="pttd ptprd").find("div").get_text()
                    score = re.search(r"(\d+-\d+)", score).group(1)
                    score = Score(PREDICTZ_NAME, score.split("-")[0], score.split("-")[1])
                    self.add_tip_callback(match_name, current_time, score=score)
            current_time = current_time + timedelta(days=1)
        self.web_scraper.destroy_driver()