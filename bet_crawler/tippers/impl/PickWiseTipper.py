import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.Tip import Tip

PICKWISE_NAME = "pickwise"

class PickWiseTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        predictions_html = self.web_scraper.load_page("https://www.pickswise.com/soccer/predictions/", mode="request")
        predictions_html = BeautifulSoup(predictions_html, 'html.parser')
        # TODO -try if exists, sometimes there are no predictions
        try:
            predictions_html = predictions_html.find("div", class_=re.compile(r'SportPredictions')).find_all("a")
            return [a['href'] for a in predictions_html]
        except:
            return []

    def get_tips(self):
        for match_url in self._get_matches_urls():
            request_result = self.web_scraper.load_page("https://www.pickswise.com" + match_url, mode="request")
            if request_result is not None:
                match_html = BeautifulSoup(request_result, 'html.parser')

                match_name = match_html.find("div", class_="PredictionHeaderInfo_titleWrapper__NW7Pn").get_text()
                match_name = match_name.split("Prediction")[0].strip()

                match_time = match_html.find("div",
                                             class_="TimeDate_timeDate__HSSoH TimeDate_timeDateCenter__Iok0U PredictionHeaderTeam_date__TYuIg")
                hour_element = match_time.find("time", class_="TimeDate_time__j7Ljy").get_text()
                match_hour = datetime.strptime(hour_element[:-6].strip(), "%H:%M") + timedelta(hours=19)

                if "Today" in str(match_time):
                    match_time = datetime.today()
                elif "Tomorrow" in str(match_time):
                    match_time = datetime.today() + timedelta(days=1)
                else:
                    match_time = datetime.strptime(match_time.find("span").get_text(), "%a %b %d")
                    match_time = match_time.replace(year=2025) # TODO - CHECK OTHER IMPLEMENTATIONS OF NEXT DATE
                match_time = match_time.replace(hour=match_hour.hour, minute=match_hour.minute)
                tip = match_html.find("div", class_="SelectionInfo_outcome__1i6jL").get_text()
                tip_strength = str(match_html.find("div", attrs={'data-testid': "ConfidenceRating"}).contents)
                tip_strength = tip_strength.count("icon-filled-star") / 2
                # TODO - fix here
                try:
                    odds = match_html.find("div", class_="DataButton_oddsAndLine__9LKbR").get_text()
                    odds = str(round(1 + (abs(int(odds)) / 100), 2))
                except:
                    odds = 0

                self.add_tip_callback(match_name, match_time, tip=Tip(tip, tip_strength, PICKWISE_NAME, odds))
        self.web_scraper.destroy_driver()