import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score
from bet_crawler.core.Tip import Tip

WINDRAWWIN_NAME = "windrawwin"

class WinDrawWinTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self._tip_strengths = ["Small", "Medium", "Large"]

    def get_tips(self):
        current_date = datetime.now().date()
        for i in range(9):
            formatted_date = (current_date + timedelta(days=i)).strftime("%Y%m%d")
            request_result = self.web_scraper.load_page(f'https://www.windrawwin.com/predictions/future/{formatted_date}/', time_delay=6)
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser')

                matches_anchors = html.find_all("div", class_="wttr")

                for match in matches_anchors:
                    match_name = match.find("div", class_=re.compile(r'wttd wtfixt wtlh')).find('a').get_text()
                    match_date = datetime.combine(current_date, datetime.min.time()) + timedelta(days=i)
                    score = match.find("div", class_="wttd wtsc").get_text()
                    compare_numbers = lambda text: 0 if int(text.split('-')[0]) > int(text.split('-')[1]) else (
                        1 if int(text.split('-')[0]) == int(text.split('-')[1]) else 2)
                    try:
                        tip_odds_anchors = match.find('div', class_='wtmo').find_all("div",
                                                                                     class_=re.compile(
                                                                                         r'wttd wtocell'))
                        odds = tip_odds_anchors[compare_numbers(score)].get_text()
                    except AttributeError:
                        odds = 0
                    tip = match.find("div", class_="wttd wtprd").get_text()
                    score = Score(WINDRAWWIN_NAME, int(score[0]), int(score[2]))
                    tip_strength = self._tip_strengths.index(match.find('div', class_="wttd wtstk").get_text()) + 1

                    self.add_tip_callback(match_name, match_date, tip=Tip(tip, tip_strength, WINDRAWWIN_NAME, odds), score=score)

        self.web_scraper.destroy_driver()
