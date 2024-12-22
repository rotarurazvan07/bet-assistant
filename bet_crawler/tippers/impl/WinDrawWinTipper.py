import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_framework.WebDriver import WebDriver
from core.BaseTipper import BaseTipper
from core.Tip import Tip


class WinDrawWinTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self._tip_strengths = ["Small", "Medium", "Large"]

    def get_tips(self):
        current_date = datetime.now().date()
        for i in range(9):
            web_driver = WebDriver()
            formatted_date = (current_date + timedelta(days=i)).strftime("%Y%m%d")
            web_driver.driver.get(f'https://www.windrawwin.com/predictions/future/{formatted_date}/')
            request_result = web_driver.driver.page_source
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser')

                matches_anchors = html.find_all("div", class_="wttr")
                matches_anchors += html.find_all("div", class_="wttr altrowd")

                for match in matches_anchors:
                    match_name = match.find("div", class_=re.compile(r'wttd wtfixt wtlh')).find('a').get_text()
                    match_date = (current_date + timedelta(days=i)).strftime("%Y-%m-%d - 23:59")
                    tip = match.find("div", class_="wttd wtsc").get_text()
                    compare_numbers = lambda text: 0 if int(text.split('-')[0]) > int(text.split('-')[1]) else (
                        1 if int(text.split('-')[0]) == int(text.split('-')[1]) else 2)
                    try:
                        tip_odds_anchors = match.find('div', class_='wtmo').find_all("div",
                                                                                     class_=re.compile(
                                                                                         r'wttd wtocell'))
                        odds = tip_odds_anchors[compare_numbers(tip)].get_text()
                    except AttributeError:
                        odds = "N/A"
                    tip = match.find("div", class_="wttd wtprd").get_text() + " " + tip
                    tip_strength = self._tip_strengths.index(match.find('div', class_="wttd wtstk").get_text()) + 1
                    self.add_tip_callback(Tip(tip, tip_strength, "WinDrawWin", odds),match_name, match_date)

            web_driver.driver.quit()
