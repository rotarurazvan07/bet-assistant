import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.core.BaseTipper import BaseTipper
from bet_crawler.core.MatchStatistics import Score
from bet_crawler.core.Tip import Tip

FREETIPS_URL = "https://www.freetips.com/football/fixtures/"
FREETIPS_NAME = "freetips"

class FreeTipsTipper(BaseTipper):
    def __init__(self, add_tip_callback):
        super().__init__(add_tip_callback)

    def _get_matches_urls(self):
        request_result = self.web_scraper.load_page(FREETIPS_URL, time_delay=0.1)

        matches_urls = []

        page_html = BeautifulSoup(request_result, 'html.parser')
        matches_urls += [a.find('a')['href'] for a in page_html.find_all("div", class_="eventNameDC Newsurls")]
        # TODO - needs tweaking to look for upcoming matches, investigate
        request_result = self.web_scraper.load_page(matches_urls[0], time_delay=0.5)

        page_html = BeautifulSoup(request_result, 'html.parser')
        upcoming_matches = page_html.find_all("div", class_="news-stream-wrap")[1:]
        for upc_match in upcoming_matches:
            for event in upc_match.find_all('div', class_="news-stream-item"):
                if "Soccer" in str(event):
                    matches_urls.append(event.find("a").get('href'))

        return matches_urls

    def get_tips(self):
        for match_url in self._get_matches_urls():
            request_result = self.web_scraper.load_page(match_url, time_delay=0.5)
            if request_result is not None:
                html = BeautifulSoup(request_result, 'html.parser')

                # TODO - throws error
                match_name = html.find("div", class_="betTop").find('h4').get_text().replace('\n', '').replace('\t', '').strip()
                match_date = html.find("div", class_="betTop").find('div', class_="betTiming").get('data-datezone')

                match_date = datetime.strptime(match_date, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=3)

                for tip_html in html.find_all("div", class_="verdictBoxItem"):
                    tip = tip_html.find("div", class_="hedTextOneVBD").get_text() + " " + tip_html.find("div",
                                                                                                        class_="hedTextOneVBD marketName").get_text()
                    score_find = re.search(r"(\d+-\d+)", tip)
                    if score_find:
                        score = score_find.group(1)  # Extract the score
                        tip = tip.replace(score, "").replace("Correct Score", "").strip()  # Get the rest of the string
                        if match_name.split('v')[0].strip() in tip:
                            score = Score(FREETIPS_NAME, score.split("-")[0], score.split("-")[1])
                        elif match_name.split('v')[1].strip() in tip:
                            score = Score(FREETIPS_NAME, score.split("-")[1], score.split("-")[0])
                        else:
                            score = Score(FREETIPS_NAME, score.split("-")[0], score.split("-")[1])
                    else:
                        score = None
                    tip_strength = int(
                        re.search(r'(\d+)\s+Unit', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(
                            1))
                    tip_strength = tip_strength * 2 / 5 + 1
                    odds = str(
                        re.search(r'@(\d+\.\d+)', tip_html.find("div", class_="hedTextTwoVBD").get_text()).group(1))

                    self.add_tip_callback(match_name, match_date, tip=Tip(tip, tip_strength, FREETIPS_NAME, odds), score=score)

        self.web_scraper.destroy_driver()
