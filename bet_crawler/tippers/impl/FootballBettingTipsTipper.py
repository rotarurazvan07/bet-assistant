import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score

FOOTBALL_BETTING_TIPS_URL = "https://footballbettingtips.org/"
FOOTBALL_BETTING_TIPS_NAME = "footballbettingtips"

class FootballBettingTipsTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        request_result = self.web_scraper.load_page(FOOTBALL_BETTING_TIPS_URL, time_delay=3)
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            matches_urls = [a.find("a")['href'] for a in html.find_all("h3")[:2]]
            return matches_urls

    def get_tips(self):
        current_time = datetime.now() + timedelta(days=1)
        for match_url in self._get_matches_urls():
            request_result = self.web_scraper.load_page(FOOTBALL_BETTING_TIPS_URL + match_url, time_delay=4)
            if request_result is not None:
                matches_html = BeautifulSoup(request_result, 'html.parser')
                # tODO - still getting just a moment
                matches_html = matches_html.find("table", class_="results").find_all("tr")
                for match_html in matches_html:
                    if match_html.find("a"):
                        match_name = match_html.find("a").get_text()
                        score = match_html.find_all("td")[-2].get_text()
                        score = re.search(r"(\d+:\d+)", score).group(1)
                        score = Score(FOOTBALL_BETTING_TIPS_NAME, score.split(":")[0], score.split(":")[1])
                        self.add_tip_callback(match_name, current_time, score=score)
            current_time = current_time - timedelta(days=1)
        self.web_scraper.destroy_driver()
