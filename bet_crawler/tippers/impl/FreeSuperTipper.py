import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score
from bet_crawler.core.Tip import Tip
from bet_framework.utils import fractional_to_decimal_odds

FREE_SUPER_TIPS_URL = "https://www.freesupertips.com"
FREE_SUPER_TIPS_NAME = "freesupertips"

class FreeSuperTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        today_html = self.web_scraper.load_page(FREE_SUPER_TIPS_URL +"/predictions/", mode="request")
        tomorrow_html = self.web_scraper.load_page(FREE_SUPER_TIPS_URL + "/predictions/tomorrows-football-predictions/", mode="request")
        upcoming_html = self.web_scraper.load_page(FREE_SUPER_TIPS_URL + "/predictions/upcoming/", mode="request")

        matches_urls = self._get_urls_from_page(today_html) + \
                       self._get_urls_from_page(tomorrow_html) + \
                       self._get_urls_from_page(upcoming_html)

        return matches_urls

    def _get_urls_from_page(self, page_html):
        soup = BeautifulSoup(page_html, 'html.parser')
        match_table_anchor = soup.find('main', class_="Main Main--sidebar")
        return [a['href'] for a in match_table_anchor.find_all("a", class_="Prediction")]

    def get_tips(self):
        for match_url in self._get_matches_urls():
            request_result = self.web_scraper.load_page(FREE_SUPER_TIPS_URL + match_url, mode="request")
            if request_result is not None:
                match_html = BeautifulSoup(request_result, 'html.parser')
                match = match_html.find_all('div', class_="TeamForm__inner")
                # TODO - this gives IndexError
                home = match[0].get_text()
                away = match[1].get_text()
                match =  home + " - " + away

                hour_element = match_html.find('ul', class_='GameBullets').find('li').get_text()
                date_element = match_html.find('ul', class_='GameBullets').find('li').find_next_sibling(
                    'li').get_text()

                hour_element = datetime.strptime(hour_element, "%H:%M")
                hour_element = hour_element + timedelta(hours=3)
                hour_element = hour_element.strftime("%H:%M")

                current_date = datetime.now()
                date_element = date_element.replace("Today", current_date.strftime("%Y-%m-%d"))
                date_element = date_element.replace("Tomorrow",
                                                    (current_date + timedelta(days=1)).strftime("%Y-%m-%d"))

                if date_element.isnumeric():
                    if int(date_element) > current_date.day:
                        current_date = current_date.replace(day=int(date_element))
                    else:
                        try:
                            current_date = current_date.replace(day=int(date_element), month=current_date.month + 1)
                        except:
                            current_date = current_date.replace(year=current_date.year + 1, day=int(date_element), month=1)

                    date_element = str(current_date.strftime("%Y-%m-%d"))

                match_time = date_element + " - " + hour_element

                if "Expired" in match_time:
                    continue

                match_time = datetime.strptime(match_time, "%Y-%m-%d - %H:%M")

                for tip_html in match_html.findAll('div', class_="IndividualTipPrediction"):
                    tip = tip_html.find("h4").get_text()
                    # some tips contain score, get it using regex
                    score_find = re.search(r"(\d+-\d+)", tip)
                    if score_find:
                        score = score_find.group(1)  # Extract the score
                        tip = tip.replace(score, "").strip()  # Get the rest of the string
                        if home in tip:
                            score = Score(FREE_SUPER_TIPS_NAME, score.split("-")[0], score.split("-")[1])
                        elif away in tip:
                            score = Score(FREE_SUPER_TIPS_NAME, score.split("-")[1], score.split("-")[0])
                        else:
                            score = Score(FREE_SUPER_TIPS_NAME, score.split("-")[0], score.split("-")[1])
                    else:
                        score = None
                    odds = tip_html.find('div', class_='BetExpand__odds').find('span').get_text()
                    odds = fractional_to_decimal_odds(odds)
                    tip_strength = len(tip_html.findAll('span', class_="Icon-module__icon Icon-module__small "
                                                                       "Icon-module__icon-filled-star "
                                                                       "Icon-module__tertiary "
                                                                       "ConfidenceRating-module__star"))

                    self.add_tip_callback(match, match_time, tip=Tip(tip, tip_strength, FREE_SUPER_TIPS_NAME, odds), score=score)
