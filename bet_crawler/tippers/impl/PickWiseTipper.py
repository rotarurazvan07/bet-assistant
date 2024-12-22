import re
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.WebDriver import make_request
from core.BaseTipper import BaseTipper
from core.Tip import Tip


class PickWiseTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        predictions_html = make_request("https://www.pickswise.com/soccer/predictions/")
        predictions_html = BeautifulSoup(predictions_html, 'html.parser')
        # TODO -try if exists, sometimes there are no predictions
        try:
            predictions_html = predictions_html.find("div", class_=re.compile(r'SportPredictions')).find_all("a")
            return [a['href'] for a in predictions_html]
        except:
            return []

    def get_tips(self):
        for match_url in self._get_matches_urls():
            request_result = make_request("https://www.pickswise.com" + match_url)
            if request_result is not None:
                match_html = BeautifulSoup(request_result, 'html.parser')

                match_name = match_html.find("div", class_="PredictionHeaderInfo_titleWrapper__NW7Pn").get_text()
                match_name = match_name.split("Prediction")[0].strip()

                match_time = match_html.find("div",
                                             class_="TimeDate_timeDate__HSSoH TimeDate_timeDateCenter__Iok0U PredictionHeaderTeam_date__TYuIg").get_text()
                if "Today" in match_time:
                    match_time = datetime.today()
                    # TODO - get hour also
                    #  date is bad
                else:
                    match_time = datetime.today()

                match_time = match_time.strftime("%Y-%m-%d - %H:%M")

                tip = match_html.find("div", class_="SelectionInfo_outcome__1i6jL").get_text()
                tip_strength = str(match_html.find("div", attrs={'data-testid': "ConfidenceRating"}).contents)
                tip_strength = tip_strength.count("icon-filled-star") / 2
                # TODO - fix here
                try:
                    odds = match_html.find("div", class_="DataButton_oddsAndLine__9LKbR").get_text()
                    odds = str(round(1 + (abs(int(odds)) / 100), 2))
                except:
                    odds = "N/A"

                self.add_tip_callback(Tip(tip, tip_strength, "PickWise", odds),match_name, match_time)
