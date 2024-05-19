import re
import threading
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from src.WebDriver import make_request, WebDriver
from src.utils import fractional_to_decimal_odds

WHO_SCORED_URL = "https://www.whoscored.com"
FREE_SUPER_TIPS_URL = "https://www.freesupertips.com"
INFOGOL_TODAY_URL = "https://www.infogol.net/en/matches/today"
INFOGOL_TOMORROW_URL = "https://www.infogol.net/en/matches/fixtures/tomorrow"
FOREBET_TOP_VALUES_URL = "https://www.forebet.com/en/top-football-tips-and-predictions"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_URL = "https://www.forebet.com"


class Tip:
    def __init__(self, match_name, match_time, tip, confidence, source="", odds=0):
        self.match_name = match_name
        self.match_time = match_time
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source

    def get_tip_data(self):
        return [self.match_name, self.match_time, self.tip, self.confidence, self.source, self.odds]


class Tipper:
    def __init__(self):
        self.tips = []
        self.execution = 0
        self._searched_tips = 0
        self._tips_to_search = 0

    def get_tips(self):
        self.tips = []
        self._searched_tips = 0

        tippers = [self.WhoScoredTipper(self), self.ForebetTipper(self), self.FreeSuperTipper(self), self.WinDrawWinTipper(self)]
        self._tips_to_search = len(tippers)

        threads = []
        for i in range(len(tippers)):
            threads.append(threading.Thread(target=self._get_tips_helper, args=(tippers[i],)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.execution = 0

    def _get_tips_helper(self, tipper_obj):
        tipper_obj.get_tips()
        self._searched_tips += 1

    class WhoScoredTipper:
        def __init__(self, tipper):
            self.web_driver = WebDriver()
            self.tipper = tipper
            self._tip_strengths = ["Likely", "Very Likely", "Extremely Likely"]

        def _get_matches_urls(self):
            request_result = make_request(WHO_SCORED_URL + "/Previews")
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser')
                matches_table_anchor = html.find("table", class_="grid")
                matches_urls = [a['href'] for a in matches_table_anchor.find_all('a') if "Matches" in a['href']]
                return matches_urls

        def get_tips(self):
            for match_url in self._get_matches_urls():
                self.web_driver.driver.get(WHO_SCORED_URL + match_url)
                request_result = self.web_driver.driver.page_source
                if request_result is not None:
                    match_html = BeautifulSoup(request_result, 'html.parser')

                    home_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                        r'home team')).get_text()
                    away_team = match_html.find('div', class_='teams-score-info').find("span", class_=re.compile(
                        r'away team')).get_text()
                    match_name = home_team + " - " + away_team

                    match_time = match_html.find('dt', text='Date:').find_next_sibling('dd').text + " - " + \
                                 match_html.find('dt', text='Kick off:').find_next_sibling('dd').text

                    match_time = (datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(hours=2)).strftime("%Y-%m-%d - %H:%M")

                    side_box = match_html.find('table', class_="grid teamcharacter")
                    try:
                        for tip_html in side_box.findAll('tr'):
                            tip = tip_html.get_text().strip()
                            tip_strength = self._tip_strengths.index(tip_html.find('span')['title'].strip()) + 1
                            self.tipper.tips.append(Tip(match_name, match_time, tip, tip_strength, "WhoScored"))
                    except AttributeError:
                        continue
            self.web_driver.driver.close()

    class FreeSuperTipper:
        def __init__(self, tipper):
            self.tipper = tipper

        def _get_matches_urls(self):
            today_html = make_request("https://www.freesupertips.com/predictions/")
            tomorrow_html = make_request("https://www.freesupertips.com/predictions/tomorrows-football-predictions/")
            upcoming_html = make_request("https://www.freesupertips.com/predictions/upcoming/")

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
                request_result = make_request(FREE_SUPER_TIPS_URL + match_url)
                if request_result is not None:
                    match_html = BeautifulSoup(request_result, 'html.parser')
                    match = match_html.find_all('div', class_="TeamForm__inner")
                    match = match[0].get_text() + " - " + match[1].get_text()

                    hour_element = match_html.find('ul', class_='GameBullets').find('li').get_text()
                    date_element = match_html.find('ul', class_='GameBullets').find('li').find_next_sibling('li').get_text()

                    hour_element = datetime.strptime(hour_element, "%H:%M")
                    hour_element = hour_element + timedelta(hours=3)
                    hour_element = hour_element.strftime("%H:%M")

                    current_date = datetime.now()
                    date_element = date_element.replace("Today", current_date.strftime("%Y-%m-%d"))
                    date_element = date_element.replace("Tomorrow", (current_date + timedelta(days=1)).strftime("%Y-%m-%d"))
                    if date_element.isnumeric():
                        if int(date_element) > current_date.day:
                            current_date = current_date.replace(day=int(date_element))
                        else:
                            current_date = current_date.replace(day=int(date_element), month=current_date.month+1)
                        date_element = str(current_date.strftime("%Y-%m-%d"))

                    match_time = date_element + " - " + hour_element
                    for tip_html in match_html.findAll('div', class_="IndividualTipPrediction"):
                        tip = tip_html.find("h4").get_text()
                        odds = tip_html.find('div', class_='BetExpand__odds').find('span').get_text()
                        odds = fractional_to_decimal_odds(odds)
                        tip_strength = len(tip_html.findAll('span', class_="Icon-module__icon Icon-module__small "
                                                                           "Icon-module__icon-filled-star "
                                                                           "Icon-module__tertiary "
                                                                           "ConfidenceRating-module__star"))
                        self.tipper.tips.append(Tip(match, match_time, tip, tip_strength, "FreeSuperTips", odds))

    class ForebetTipper:
        def __init__(self, tipper):
            self.tipper = tipper

        def get_tips(self):
            request_result = make_request(FOREBET_TOP_VALUES_URL)
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser').find('div', class_="schema")

                for match_html in html.find_all('div', class_="rcnt tr_0") + html.find_all('div', class_="rcnt tr_1"):
                    match_name = match_html.find('meta')['content']
                    match_date = match_html.find('span', class_="date_bah").get_text()
                    match_date = (datetime.strptime(match_date, "%d/%m/%Y %H:%M") + timedelta(hours=1)).strftime("%Y-%m-%d - %H:%M")
                    tip = match_html.find('span', class_="forepr").get_text()
                    # Get match odds
                    try:
                        odds = float(match_html.find('span', class_="lscrsp").get_text())
                    except:
                        odds = 0

                    tip_strength = 3 * int(match_html.find('span', class_="fpr").get_text()) / 100
                    self.tipper.tips.append(Tip(match_name, match_date, tip, tip_strength, "Forebet", odds))

    class WinDrawWinTipper:
        def __init__(self, tipper):
            self.tipper = tipper
            self._tip_strengths = ["Small", "Medium", "Large"]

        # TODO - some entries are doubled
        # TODO - needs checking
        def get_tips(self):
            current_date = datetime.now().date()
            for i in range(9):
                web_driver = WebDriver()
                formatted_date = (current_date + timedelta(days=i)).strftime("%Y%m%d")
                print(formatted_date)
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
                        tip_strength = self._tip_strengths.index(match.find('div', class_="wttd wtstk").get_text()) + 1
                        odds = 0
                        self.tipper.tips.append(Tip(match_name, match_date, tip, tip_strength, "WinDrawWin", odds))
                web_driver.driver.close()

    # TODO -