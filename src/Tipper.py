import re
import threading
import time
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
    def __init__(self, match_name, match_time, tip, confidence, source="", odds="N/A"):
        self.match_name = match_name
        self.match_time = match_time
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source


class Tipper:
    def __init__(self, db_manager):
        self.execution = 0
        self._searched_tips = 0
        self._tips_to_search = 0
        self.db_manager = db_manager

    def get_tips(self):
        self._searched_tips = 0

        tippers = [
                   self.WhoScoredTipper(self),
                   self.FreeSuperTipper(self),
                   self.ForebetTipper(self),
                   self.WinDrawWinTipper(self),
                   self.FootyStatsTipper(self),
                   self.PickWiseTipper(self),
                   self.FreeTipsTipper(self),
                   self.OLBGTipper(self)
                   ]
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
            self.web_driver.driver.get(WHO_SCORED_URL + "/Previews")
            time.sleep(5)
            request_result = self.web_driver.driver.page_source
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser')
                matches_table_anchor = html.find("table", class_="grid")
                matches_urls = [a['href'] for a in matches_table_anchor.find_all('a') if "Matches" in a['href']]
                return matches_urls

        def get_tips(self):
            for match_url in self._get_matches_urls():
                self.web_driver.driver.get(WHO_SCORED_URL + match_url)
                time.sleep(0.1)
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

                    match_time = (datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(
                        hours=2)).strftime("%Y-%m-%d - %H:%M")

                    side_box = match_html.find('table', class_="grid teamcharacter")
                    try:
                        for tip_html in side_box.findAll('tr'):
                            tip = tip_html.get_text().strip()
                            tip_strength = self._tip_strengths.index(tip_html.find('span')['title'].strip()) + 1
                            self.tipper.db_manager.add_or_update_match(
                                Tip(match_name, match_time, tip, tip_strength, "WhoScored"))
                    except AttributeError:
                        continue

            self.web_driver.driver.quit()

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
                            current_date = current_date.replace(day=int(date_element), month=current_date.month + 1)
                        date_element = str(current_date.strftime("%Y-%m-%d"))

                    match_time = date_element + " - " + hour_element

                    if "Expired" in match_time:
                        continue

                    for tip_html in match_html.findAll('div', class_="IndividualTipPrediction"):
                        tip = tip_html.find("h4").get_text()
                        odds = tip_html.find('div', class_='BetExpand__odds').find('span').get_text()
                        odds = fractional_to_decimal_odds(odds)
                        tip_strength = len(tip_html.findAll('span', class_="Icon-module__icon Icon-module__small "
                                                                           "Icon-module__icon-filled-star "
                                                                           "Icon-module__tertiary "
                                                                           "ConfidenceRating-module__star"))
                        self.tipper.db_manager.add_or_update_match(
                            Tip(match, match_time, tip, tip_strength, "FreeSuperTips", odds))

    class ForebetTipper:
        def __init__(self, tipper):
            self.web_driver = WebDriver()
            self.tipper = tipper

        def get_tips(self):
            self.web_driver.driver.get(FOREBET_TOP_VALUES_URL)
            time.sleep(0.5)
            request_result = self.web_driver.driver.page_source
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

                    self.tipper.db_manager.add_or_update_match(
                        Tip(match_name, match_date, tip, tip_strength, "Forebet", odds))
            self.web_driver.driver.quit()

    class OLBGTipper:
        def __init__(self, tipper):
            self.tipper = tipper

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
                    self.tipper.db_manager.add_or_update_match(
                        Tip(match_name, match_date, tip, tip_strength, "OLBG", odds))

    class WinDrawWinTipper:
        def __init__(self, tipper):
            self.tipper = tipper
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
                        self.tipper.db_manager.add_or_update_match(
                            Tip(match_name, match_date, tip, tip_strength, "WinDrawWin", odds))

                web_driver.driver.quit()

    class FreeTipsTipper:
        def __init__(self, tipper):
            self.tipper = tipper
            self.web_driver = WebDriver()

        def _get_matches_urls(self):
            self.web_driver.driver.get("https://www.freetips.com/football/fixtures/")
            time.sleep(0.1)

            matches_urls = []

            page_html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')
            matches_urls += [a.find('a')['href'] for a in page_html.find_all("div", class_="eventNameDC Newsurls")]
            self.web_driver.driver.quit()
            time.sleep(0.4)
            self.web_driver = WebDriver()
            try:
                self.web_driver.driver.get(matches_urls[0])
            except IndexError:
                self.web_driver.driver.quit()
                return []
            time.sleep(0.1)
            page_html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')
            upcoming_matches = page_html.find_all("div", class_="news-stream-wrap")[1:]
            for upc_match in upcoming_matches:
                for event in upc_match.find_all('div', class_="news-stream-item"):
                    if "Soccer" in str(event):
                        matches_urls.append(event.find("a").get('href'))

            self.web_driver.driver.quit()
            return matches_urls

        def get_tips(self):
            for match_url in self._get_matches_urls():
                self.web_driver = WebDriver()
                time.sleep(0.5)
                self.web_driver.driver.get(match_url)
                time.sleep(0.1)
                if self.web_driver.driver.page_source is not None:
                    html = BeautifulSoup(self.web_driver.driver.page_source, 'html.parser')

                    match_name = html.find("div", class_="betTop").find('h4').get_text().replace('\n', '')
                    match_date = html.find("div", class_="betTop").find('div', class_="betTiming").get('data-datezone')

                    match_date = (datetime.strptime(match_date, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=3)).strftime(
                        "%Y-%m-%d - %H:%M")

                    for tip_html in html.find_all("div", class_="verdictBoxItem"):
                        tip = tip_html.find("div", class_="hedTextOneVBD").get_text() + " " + tip_html.find("div",
                                                                                                            class_="hedTextOneVBD marketName").get_text()
                        tip_strength = int(
                            re.search(r'(\d+)\s+Unit', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(
                                1))
                        tip_strength = tip_strength * 2 / 5 + 1
                        odds = str(
                            re.search(r'@(\d+\.\d+)', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(1))

                        self.tipper.db_manager.add_or_update_match(
                            Tip(match_name, match_date, tip, tip_strength, "FreeTips", odds))
                self.web_driver.driver.quit()

    class FootyStatsTipper:
        def __init__(self, tipper):
            self.tipper = tipper

        def get_tips(self):
            request_result = make_request("https://footystats.org/predictions/mathematical")
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

                    self.tipper.db_manager.add_or_update_match(
                        Tip(match_name, match_date, tip, tip_strength, "FootyStats", odds))

    class PickWiseTipper:
        def __init__(self, tipper):
            self.tipper = tipper

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
                    self.tipper.db_manager.add_or_update_match(
                        Tip(match_name, match_time, tip, tip_strength, "PickWise", odds))
