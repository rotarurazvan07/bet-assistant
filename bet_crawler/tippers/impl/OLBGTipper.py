import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.Tip import Tip

OLBG_NAME = "olbg"

class OLBGTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def get_tips(self):
        self.web_scraper.load_page("https://www.olbg.com/betting-tips/Football/1", mode="driver")
        last_height = self.web_scraper.custom_call("execute_script", "return document.body.scrollHeight")

        while True:
            self.web_scraper.custom_call("execute_script","window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.web_scraper.custom_call("execute_script","return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        time.sleep(0.1)
        if self.web_scraper.get_current_page() is not None:
            html = BeautifulSoup(self.web_scraper.get_current_page(), 'html.parser')

            # TODO - doesnt load everything, skip tournament tab
            for match_html in html.find_all("div", class_="tip t-grd-1"):
                match_name = match_html.find("div", class_="rw evt").find("a", class_="h-rst-lnk").get_text()
                match_date = match_html.find("div", class_="rw evt").find("time").get('datetime')
                match_date = datetime.strptime(match_date[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=1)
                tip = match_html.find("div", class_="rw slct").find("a", class_="h-rst-lnk").get_text()
                tip_strength = match_html.find("div", class_="chart sm").find("div", class_="data").get_text()
                tip_strength = int(tip_strength.replace("%", '').replace(" ", ''))
                tip_strength = tip_strength * 2 / 100 + 1
                odds = match_html.find("span", class_="odd ui-odds").get("data-decimal")
                self.add_tip_callback(match_name, match_date, tip=Tip(tip, tip_strength, OLBG_NAME, odds))
        self.web_scraper.destroy_driver()