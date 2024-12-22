import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_framework.WebDriver import WebDriver
from core.BaseTipper import BaseTipper
from core.Tip import Tip

FOREBET_TOP_VALUES_URL = "https://www.forebet.com/en/top-football-tips-and-predictions"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_URL = "https://www.forebet.com"


class ForebetTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)
        self.web_driver = WebDriver()

    def get_tips(self):
        self.web_driver.driver.get(FOREBET_TOP_VALUES_URL)
        time.sleep(0.5)
        request_result = self.web_driver.driver.page_source
        self.web_driver.driver.quit()
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser').find('div', class_="schema")

            for match_html in html.find_all('div', class_="rcnt tr_0") + html.find_all('div', class_="rcnt tr_1"):
                match_name = match_html.find('meta')['content']
                match_date = match_html.find('span', class_="date_bah").get_text()
                match_date = (datetime.strptime(match_date, "%d/%m/%Y %H:%M") + timedelta(hours=1)).strftime(
                    "%Y-%m-%d - %H:%M")
                tip = match_html.find('span', class_="forepr").get_text()
                if tip == "1": tip = "Home Win"
                if tip == "X": tip = "Draw"
                if tip == "2": tip = "Away Win"
                # Get match odds
                try:
                    odds = float(match_html.find('span', class_="lscrsp").get_text())
                except:
                    odds = "N/A"

                tip_strength = (int(match_html.find('span', class_="fpr").get_text()) / 100) * 2 + 1

                self.add_tip_callback(Tip(tip, tip_strength, "Forebet", odds),match_name, match_date)
