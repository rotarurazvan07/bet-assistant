from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.WebDriver import make_request
from core.BaseTipper import BaseTipper
from core.Tip import Tip

FOOTYSTATS_URL = "https://footystats.org/predictions/mathematical"

class FootyStatsTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def get_tips(self):
        request_result = make_request(FOOTYSTATS_URL)
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')

            for match_html in html.find_all('li', class_="fixture-item"):
                match_name = match_html.find('div', class_="match-name").find("a").get_text()
                match_date = match_html.find('div', class_="match-time").get_text()
                match_date = datetime.strptime(match_date, "%A %B %d").replace(year=2024).strftime(
                    "%Y-%m-%d - 23:59")
                tip_anchor = match_html.find("ul", class_="bet-items").find("li").contents[0].strip()
                tip = tip_anchor.split('%')[1].strip()

                tip_strength = (int(tip_anchor.split('%')[0].strip()) / 100) * 2 + 1
                try:
                    odds = float(
                        match_html.find("ul", class_="bet-items").find_all("li")[1].get_text().replace('Real Odds',
                                                                                                       ''))
                except:
                    odds = "N/A"

                self.add_tip_callback(Tip(tip, tip_strength, "FootyStats", odds),match_name,match_date)
