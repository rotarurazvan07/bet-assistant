import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from core.BaseTipper import BaseTipper
from core.Tip import Tip
from bet_framework.WebDriver import WebDriver
class OLBGTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def get_tips(self):
        web_driver = WebDriver()
        web_driver.driver.get("https://www.olbg.com/betting-tips/Football/1")
        last_height = web_driver.driver.execute_script("return document.body.scrollHeight")

        while True:
            web_driver.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = web_driver.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        time.sleep(0.1)
        if web_driver.driver.page_source is not None:
            html = BeautifulSoup(web_driver.driver.page_source, 'html.parser')
            web_driver.driver.quit()

            # TODO - doesnt load everything, skip tournament tab
            for match_html in html.find_all("div", class_="tip t-grd-1"):
                match_name = match_html.find("div", class_="rw evt").find("a", class_="h-rst-lnk").get_text()
                match_date = match_html.find("div", class_="rw evt").find("time").get('datetime')
                match_date = (
                        datetime.strptime(match_date[:19], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=1)).strftime(
                    "%Y-%m-%d - %H:%M")

                tip = match_html.find("div", class_="rw slct").find("a", class_="h-rst-lnk").get_text()
                tip_strength = match_html.find("div", class_="chart sm").find("div", class_="data").get_text()
                tip_strength = int(tip_strength.replace("%", '').replace(" ", ''))
                tip_strength = tip_strength * 2 / 100 + 1
                odds = match_html.find("span", class_="odd ui-odds").get("data-decimal")
                self.add_tip_callback(Tip(match_name, match_date, tip, tip_strength, "OLBG", odds))
