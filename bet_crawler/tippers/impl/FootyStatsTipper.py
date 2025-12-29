from datetime import datetime

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.Tip import Tip

FOOTYSTATS_URL = "https://footystats.org/predictions/mathematical"
FOOTYSTATS_NAME = "footystats"

class FootyStatsTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def get_tips(self):
        request_result = self.web_scraper.load_page(FOOTYSTATS_URL, mode="request")
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')

            for match_html in html.find_all('li', class_="fixture-item"):
                match_name = match_html.find('div', class_="match-name").find("a").get_text()
                match_date = match_html.find('div', class_="match-time").get_text()
                match_date = datetime.strptime(match_date, "%A %B %d")
                match_date = match_date.replace(year=datetime.now().year)

                tip_anchor = match_html.find("ul", class_="bet-items").find("li").contents[0].strip()
                tip = tip_anchor.split('%')[1].strip()

                # FootyStats gives a percent like '75% Tip' — use percent directly as 0..100 confidence
                try:
                    percent = int(tip_anchor.split('%')[0].strip())
                except Exception:
                    percent = 0
                tip_strength = int(round(percent))
                try:
                    odds = float(
                        match_html.find("ul", class_="bet-items").find_all("li")[1].get_text().replace('Real Odds',
                                                                                                       ''))
                except:
                    odds = 0

                self.add_tip_callback(match_name, match_date, tip=Tip(tip, tip_strength, FOOTYSTATS_NAME, odds))
