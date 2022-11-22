import os
import threading
import time
from datetime import datetime, timedelta

import requests
import xlsxwriter
from bs4 import BeautifulSoup
from src.utils import CURRENT_TIME, init_driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

WHO_SCORED_URL = "https://www.whoscored.com"
FREE_SUPER_TIPS_URL = "https://www.freesupertips.com"
INFOGOL_TODAY_URL = "https://www.infogol.net/en/matches/today"
INFOGOL_TOMORROW_URL = "https://www.infogol.net/en/matches/fixtures/tomorrow"
FOREBET_TOP_VALUES_URL = "https://www.forebet.com/en/top-football-tips-and-predictions"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_URL = "https://www.forebet.com"

class Tip:
    def __init__(self, match_name, tip, confidence, source="", odds=0):
        self.match_name = match_name
        self.tip = tip
        self.confidence = confidence
        self.odds = odds
        self.source = source

    def get_tip_data(self):
        return [self.match_name, self.tip, self.confidence, self.source, self.odds]


class Tipper:
    def get_tips(self):
        tippers = [self.BttsTipper(), self.WhoScoredTipper(), self.FreeSuperTipper(), self.InfogolTipper(), self.ForebetTipper()]
        return [item for sublist in [tip.get_tips() for tip in tippers] for item in sublist]

    class WhoScoredTipper():
        def __init__(self):
            self.driver = None
            self.tip_strengths = ["Likely", "Very Likely", "Extremely Likely"]

        def _get_matches_urls(self):
            self.driver.get(WHO_SCORED_URL)
            time.sleep(2)
            html = BeautifulSoup(self.driver.page_source, 'html.parser')
            return [a['href'] for a in html.find_all('a', class_="match-link rc preview")]

        def get_tips(self):
            tips = []
            self.driver = init_driver()
            for match_url in self._get_matches_urls():
                self.driver.get(WHO_SCORED_URL + match_url)
                match_html = BeautifulSoup(self.driver.page_source, 'html.parser')
                fixture = match_url.split("-")
                match_name = fixture[-2] + " vs " + fixture[-1]
                side_box = match_html.find('table', class_="grid teamcharacter")
                try:
                    for tip_html in side_box.findAll('tr'):
                        tip = tip_html.get_text().strip()
                        tip_strength = self.tip_strengths.index(tip_html.find('span')['title'].strip()) + 1
                        tips.append(Tip(match_name, tip, tip_strength, "WhoScored"))
                except AttributeError:
                    continue
            self.driver.close()
            return tips

    class FreeSuperTipper():
        def _get_matches_urls(self):
            page_html = requests.get(FREE_SUPER_TIPS_URL, timeout=1000).text
            html = BeautifulSoup(page_html, 'html.parser')
            html = html.find('main', class_="Main Main--sidebar")
            return [a['href'] for a in html.findAll("a", class_="Link-module__link "
                                                                "EventShortcutCarouselCard"
                                                                "-module__eventShortcutCarouselCard global-module__card "
                                                                "EventShortcutCarouselCard-module__edges")]

        def get_tips(self):
            tips = []
            for match_url in self._get_matches_urls():
                print(FREE_SUPER_TIPS_URL + match_url)
                r = requests.get(FREE_SUPER_TIPS_URL + match_url, timeout=1000)
                match_html = BeautifulSoup(r.text, 'html.parser')
                match = match_html.find('div', class_="PageIntro").get_text().rsplit(' ', 1)[0]
                for tip_html in match_html.findAll('div', class_="IndividualTipPrediction"):
                    tip = tip_html.find("h4").get_text()
                    tip_strength = len(tip_html.findAll('span', class_="Icon-module__icon Icon-module__small "
                                                                       "Icon-module__icon-filled-star "
                                                                       "Icon-module__tertiary "
                                                                       "ConfidenceRating-module__star"))
                    tips.append(Tip(match, tip, tip_strength, "FreeSuperTips"))
            return tips

    class InfogolTipper():
        def __init__(self):
            self.driver = None

        def get_tips(self):
            tips = []
            for infogol_page in [INFOGOL_TODAY_URL, INFOGOL_TOMORROW_URL]:
                self.driver = init_driver()
                self.driver.get(infogol_page)
                html = BeautifulSoup(self.driver.page_source, 'html.parser')
                self.driver.close()
                html = html.find_all('div', class_="match-header")
                for match in html:
                    try:
                        fixture = match.findAll("td", class_="match-text ng-binding")
                        match_name = fixture[0].get_text() + " vs " + fixture[1].get_text()
                        verdict = match.find('div', class_="verdict-tip-rating-container")
                        tip = verdict.find('span').get_text()
                        tip_strength = 3 * len(verdict.findAll('span', class_="ball-rating-ball ng-scope")) / 5
                        tips.append(Tip(match_name, tip, tip_strength, "Infogol"))
                    except AttributeError:
                        continue
            return tips

    class ForebetTipper():
        def get_tips(self):
            tips = []
            page_html = requests.get(FOREBET_TOP_VALUES_URL, timeout=1000).text
            html = BeautifulSoup(page_html, 'html.parser').find('div', class_="schema")

            for match_html in html.find_all('div', class_="rcnt tr_0") + html.find_all('div', class_="rcnt tr_1"):
                match_name = match_html.find('meta')['content']
                tip = match_html.find('span', class_="forepr").get_text()
                tip_strength = 3 * int(match_html.find('span', class_="fpr").get_text()) / 100
                tips.append(Tip(match_name, tip, tip_strength, "Forebet"))
            return tips

    class BttsTipper():
        def __init__(self):
            self.driver = None
            self.tips = []

        def get_tips(self):
            self.driver = init_driver()
            self.driver.get(FOREBET_ALL_PREDICTIONS_URL)

            # Press the "Show more" button at the bottom of the page by running the script it is executing
            for i in range(11, 30):
                self.driver.execute_script("ltodrows(\"1x2\"," + str(i) + ",\"\");")
                time.sleep(1)
            html = BeautifulSoup(self.driver.page_source, 'html.parser')
            matches_urls = [a['href'] for a in html.find_all('a', class_="tnmscn", itemprop="url")]
            self.driver.close()

            threads = []
            for i in range(4):
                lower_bound = int(i * len(matches_urls) / 4)
                upper_bound = int((i + 1) * len(matches_urls) / 4)
                match_list = matches_urls[lower_bound:upper_bound]
                threads.append(threading.Thread(target=self._find_value_matches, args=(match_list,)))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            return self.tips

        def _find_value_matches(self, match_list):
            for match_url in match_list:
                if FOREBET_URL not in match_url:
                    match_url = FOREBET_URL + match_url

                # Get Fixture html source
                try:
                    r = requests.get(match_url, timeout=1000) \
                        if FOREBET_URL in match_url else requests.get(FOREBET_URL + match_url, timeout=1000)
                except requests.exceptions.RequestException:
                    print("Request error")
                    continue
                match_html = BeautifulSoup(r.text, 'html.parser')

                match_datetime = datetime.strptime(
                    match_html.find('div', class_="date_bah").get_text().strip().rsplit(' ', 1)[0],
                    "%d/%m/%Y %H:%M") + timedelta(hours=1)

                # Skip finished matches
                if match_datetime > CURRENT_TIME:
                    # Both teams at least 10 games played each
                    if int(match_html.find('span', class_="ov_pl_a").get_text()) > 10 and \
                            int(match_html.find('span', class_="ov_pl_h").get_text()) > 10:
                        percs = match_html.find_all('div', class_="ov_group")[-1]

                        home_perc = float(percs.find('div', class_="ov_col_1").find_all('span', class_="ov_left")[1].get_text().strip().strip('%'))
                        away_perc = float(percs.find('div', class_="ov_col_2").find_all('span', class_="ov_left")[1].get_text().strip().strip('%'))

                        if (home_perc + away_perc) / 2 > 90.0:
                            home_team_name = match_html.find('span', itemprop="homeTeam").get_text().strip()
                            away_team_name = match_html.find('span', itemprop="awayTeam").get_text().strip()
                            print(match_url + " " + str((home_perc + away_perc) / 2))
                            self.tips.append(Tip(home_team_name + " vs " + away_team_name, "BTTS", 3 * ((home_perc + away_perc) / 2 / 100)))
                        if (home_perc + away_perc) / 2 < 35.0:
                            home_team_name = match_html.find('span', itemprop="homeTeam").get_text().strip()
                            away_team_name = match_html.find('span', itemprop="awayTeam").get_text().strip()
                            print(match_url + " " + str((home_perc + away_perc) / 2))
                            self.tips.append(Tip(home_team_name + " vs " + away_team_name, "BTTS NO", 3 * ((home_perc + away_perc) / 2 / 100)))


def export_tips(tips_list):
    # If folder doesn't exist, then create it.
    if not os.path.isdir("output"):
        os.makedirs("output")
    # Create an Excel spreadsheet in the directory where the script is called
    workbook = xlsxwriter.Workbook('output/Tips-' + str(CURRENT_TIME.date()) +
                                   "_" + str(CURRENT_TIME.time().hour) +
                                   "-" + str(CURRENT_TIME.time().minute) + '.xlsx')
    worksheet = workbook.add_worksheet()
    headers = ["Match", "Tip", "Confidence (out of 3)", "Source", "Odds"]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)

    tips_list.sort(key=lambda x: (-x.confidence, x.match_name))

    for tip_no, tip in enumerate(tips_list):
        for column, data in enumerate(tip.get_tip_data()):
            worksheet.write(tip_no + 1, column, data)

    workbook.close()
