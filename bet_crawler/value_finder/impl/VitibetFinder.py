import re
import threading
import time
from datetime import datetime, date

from bs4 import BeautifulSoup
from bs4 import Tag

from bet_crawler.core.BaseValueFinder import BaseValueFinder
from bet_crawler.core.Match import Match
from bet_crawler.core.MatchStatistics import Score, MatchStatistics, Probability
from bet_crawler.core.Team import Team
from bet_crawler.core.Tip import Tip

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"

NUM_THREADS = 6

class VitibetFinder(BaseValueFinder):
    def __init__(self, add_value_match_callback):
        super().__init__(add_value_match_callback)
        self._scanned_leagues = 0
        self._leagues_to_scan = 0

    def _get_leagues_urls(self):
        request_result =  self.web_scraper.load_page(VITIBET_URL, mode="request")
        if request_result is not None:
            html = BeautifulSoup(request_result, 'html.parser')
            league_urls = html.find("ul", id="primarne")

            kokos_tag = league_urls.find('kokos')
            matches_urls = []
            for sibling in kokos_tag.find_next_siblings():
                if isinstance(sibling, Tag) and sibling.name == 'li':
                    if sibling.find("a")['href'] not in ["/index.php?clanek=tips&sekce=fotbal&liga=champions2&lang=en",
                                                         "/index.php?clanek=tips&sekce=fotbal&liga=champions3&lang=en",
                                                         "/index.php?clanek=tips&sekce=fotbal&liga=champions4&lang=en",
                                                         "/index.php?clanek=tips&sekce=fotbal&liga=euro_national_league&lang=en",
                                                         "/index.php?clanek=tips&sekce=fotbal&liga=southamerica&lang=en"]:
                       matches_urls.append(sibling.find("a")['href'])
            return matches_urls

    def get_value_matches(self):
        self._scanned_leagues = 0
        self._leagues_to_scan = 0
        league_urls = self._get_leagues_urls()
        self._leagues_to_scan = len(league_urls)

        info_thread = threading.Thread(target=self._log_progress, args=(league_urls,))
        info_thread.start()

        threads = []
        for i in range(NUM_THREADS):
            league_urls_slice = league_urls[int(i * len(league_urls) / NUM_THREADS):
                                              int((i + 1) * len(league_urls) / NUM_THREADS)]
            threads.append(threading.Thread(target=self._get_value_matches_helper, args=(league_urls_slice,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        info_thread.do_run = False
        info_thread.join()

    def _log_progress(self, league_urls):
        while getattr(threading.current_thread(), "do_run", True):
            print("Scanning league " + str(self._scanned_leagues) + " out of " + str(len(league_urls)))
            time.sleep(1)

    def _get_value_matches_helper(self, league_urls):
        for league_url in league_urls:
            self._scanned_leagues += 1
            # 1. fetch dates of matches
            request_result = self.web_scraper.load_page("https://www.vitibet.com/" + league_url, mode="request")
            if request_result is None:
                continue
            request_result = BeautifulSoup(request_result, 'html.parser')
            dates = [td.find("td").get_text() for td in request_result.find("table", class_="tabulkaquick").find_all("tr")[2:-1]]
            if len(dates) == 0:
                continue # No matches
            # 2. go through matches one by one
            current_match_index = 0
            league_url = league_url.replace("tips", "analyzy") + "&tab=1&zap=%s"
            while True:
                current_match_index += 1
                request_result = self.web_scraper.load_page("https://www.vitibet.com" + league_url % current_match_index, mode="request")
                if request_result is not None:
                    if "? : ?" in request_result or \
                       "#N/A : #N/A" in request_result: # break condition , no more matches
                        break
                    request_result = BeautifulSoup(request_result, 'html.parser')

                    home_team_name = request_result.find_all("td", class_="bunkamuzstvo")[0].get_text().replace("\n", '')
                    away_team_name = request_result.find_all("td", class_="bunkamuzstvo")[1].get_text().replace("\n", '')
                    if home_team_name == "" or away_team_name == "":
                        continue # missing name in one of the teams

                    # No U or W games
                    if re.search(r"\bU\d{2}s?\b", home_team_name) or \
                        re.search(r"\bU\d{2}s?\b", away_team_name) or \
                        re.search(r"\bW\b", home_team_name) or \
                        re.search(r"\bW\b", away_team_name) or \
                        re.search(r"\bII\b", home_team_name) or \
                        re.search(r"\bII\b", away_team_name) or \
                        re.search(r"\bB\b", home_team_name) or \
                        re.search(r"\bB\b", away_team_name):
                        print(f"Skipped {home_team_name} vs {away_team_name}")
                        continue

                    home_team_form = ""
                    away_team_form = ""
                    form_tables = request_result.find_all("table", class_="malypismonasedym")[-2:]
                    for form_table in form_tables:
                        for result in form_table.find_all("tr")[:3]:
                            home_team_form += "L" if result.find_all("td")[1]["style"] == "color:red" else \
                                              "W" if result.find_all("td")[1]["style"] == "color:green" else \
                                              "D"
                            away_team_form += "L" if result.find_all("td")[3]["style"] == "color:red" else \
                                              "W" if result.find_all("td")[3]["style"] == "color:green" else \
                                              "D"

                    for team_tr in request_result.find("table", class_="tabulkaquick").find_all("tr"):
                         if home_team_name in str(team_tr):
                            home_team_league_points = int(team_tr.find_all("td",class_="cisloporadi")[-1].get_text())
                         elif away_team_name in str(team_tr):
                            away_team_league_points = int(team_tr.find_all("td",class_="cisloporadi")[-1].get_text())

                    day, month = map(int, dates[current_match_index - 1].split('.'))
                    today = date.today()
                    if month < today.month or (month == today.month and day < today.day):
                        year = today.year + 1  # Next year
                    else:
                        year = today.year  # Current year
                    match_date = datetime(year, month, day)
                    score = request_result.find("td", class_="bunkatip").get_text()
                    score = Score(VITIBET_NAME, int(score.split(":")[0].strip()), int(score.split(":")[1].strip()))

                    probability = [int(td.get_text().replace(" %", '')) for td in request_result.find_all("td", class_="indexapravdepodobnost")[3:]]
                    probability=Probability(VITIBET_NAME, probability[0], probability[1],probability[2])
                    h2h_results=None
                    tip = Tip(
                        "Home Win" if score.home > score.away else
                        "Draw" if score.home == score.away else
                        "Away Win",
                        (int(max(probability.home, probability.draw, probability.away)) / 100) * 2 + 1,
                        VITIBET_NAME
                    )
                    match_to_add=Match(
                        home_team=Team(home_team_name, home_team_league_points, home_team_form, None),
                        away_team=Team(away_team_name, away_team_league_points, away_team_form, None),
                        datetime=match_date,
                        statistics=MatchStatistics(
                            scores=[score],
                            probabilities=[probability],
                            h2h=h2h_results,
                            odds=0,
                            tips=[tip]
                        )
                    )
                    self.add_value_match_callback(match_to_add)