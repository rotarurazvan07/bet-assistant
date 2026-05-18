from scrape_kit import ScrapeMode, get_logger, scrape

logger = get_logger(__name__)

from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_framework.core.leagues import *
from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
MAX_CONCURRENCY = 10

TOP_LEAGUES = {
    "https://www.forebet.com/en/predictions-europe/uefa-champions-league": CHAMPIONS_LEAGUE,
    "https://www.forebet.com/en/predictions-europe/uefa-europa-league": EUROPA_LEAGUE,
    "https://www.forebet.com/en/predictions-europe/uefa-europa-conference-league": CONFERENCE_LEAGUE,
    "https://www.forebet.com/en/football-tips-and-predictions-for-england/premier-league": PREMIER_LEAGUE,
    "https://www.forebet.com/en/football-tips-and-predictions-for-italy/serie-a": SERIE_A,
    "https://www.forebet.com/en/football-tips-and-predictions-for-spain/primera-division": LA_LIGA,
    "https://www.forebet.com/en/football-tips-and-predictions-for-germany/bundesliga": BUNDESLIGA,
    "https://www.forebet.com/en/football-tips-and-predictions-for-france/ligue1": LIGUE_1,
    "https://www.forebet.com/en/football-tips-and-predictions-for-belgium/jupiler-pro-league": JUPILER_PRO_LEAGUE,
    "https://www.forebet.com/en/football-tips-and-predictions-for-england/championship": CHAMPIONSHIP,
    "https://www.forebet.com/en/football-tips-and-predictions-for-portugal/liga-portugal": LIGA_PORTUGAL,
    "https://www.forebet.com/en/football-tips-and-predictions-for-brazil/serie-a": SERIE_A_BRAZIL,
    "https://www.forebet.com/en/football-tips-and-predictions-for-usa/mls": MLS,
    "https://www.forebet.com/en/football-tips-and-predictions-for-netherlands/eredivisie": EREDIVISIE,
    "https://www.forebet.com/en/football-tips-and-predictions-for-denmark/superliga": SUPERLIGA_DENMARK,
    "https://www.forebet.com/en/football-tips-and-predictions-for-poland/ekstraklasa": EKSTRAKLASA,
    "https://www.forebet.com/en/football-tips-and-predictions-for-argentina/liga-profesional": LIGA_PROFESIONAL,
    "https://www.forebet.com/en/football-tips-and-predictions-for-japan/j1-league": J1_LEAGUE,
    "https://www.forebet.com/en/football-tips-and-predictions-for-turkey/super-lig": SUPER_LIG,
    "https://www.forebet.com/en/football-tips-and-predictions-for-sweden/allsvenskan": ALLSVENSKAN,
    "https://www.forebet.com/en/football-predictions-for-croatia/hnl": HNL,
    "https://www.forebet.com/en/football-tips-and-predictions-for-mexico/liga-mx": LIGA_MX,
    "https://www.forebet.com/en/football-tips-and-predictions-for-spain/segunda-division": SEGUNDA_DIVISION,
    "https://www.forebet.com/en/football-tips-and-predictions-for-norway/eliteserien": ELITESERIEN,
    "https://www.forebet.com/en/football-tips-and-predictions-for-austria/bundesliga": BUNDESLIGA_AUSTRIA,
    "https://www.forebet.com/en/football-tips-and-predictions-for-switzerland/super-league": SUPER_LEAGUE_SWITZERLAND,
    "https://www.forebet.com/en/football-tips-and-predictions-for-italy/serie-b": SERIE_B,
    "https://www.forebet.com/en/football-tips-and-predictions-for-germany/2-bundesliga": BUNDESLIGA_2,
    "https://www.forebet.com/en/football-tips-and-predictions-for-france/ligue2": LIGUE_2,
    "https://www.forebet.com/en/football-tips-and-predictions-for-scotland/premiership": SCOTTISH_PREMIERSHIP,
}

ALL_LINKS = [
    "https://www.forebet.com/en/football-tips-and-predictions-for-albania",
    "https://www.forebet.com/en/tips-and-predictions-for-algeria",
    "https://www.forebet.com/en/predictions-andorra",
    "https://www.forebet.com/en/football-tips-and-predictions-for-angola",
    "https://www.forebet.com/en/antigua-and-barbuda",
    "https://www.forebet.com/en/football-tips-and-predictions-for-argentina",
    "https://www.forebet.com/en/tips-and-predictions-for-armenia",
    "https://www.forebet.com/en/predictions-aruba",
    "https://www.forebet.com/en/tips-and-predictions-for-australia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-austria",
    "https://www.forebet.com/en/tips-and-predictions-for-azerbaijan",
    "https://www.forebet.com/en/bahrain",
    "https://www.forebet.com/en/bangladesh",
    "https://www.forebet.com/en/predictions-barbados",
    "https://www.forebet.com/en/football-tips-and-predictions-for-belarus",
    "https://www.forebet.com/en/football-tips-and-predictions-for-belgium",
    "https://www.forebet.com/en/predictions-belize",
    "https://www.forebet.com/en/predictions-benin",
    "https://www.forebet.com/en/predictions-bermuda",
    "https://www.forebet.com/en/football-tips-and-predictions-for-bolivia",
    "https://www.forebet.com/en/tips-and-predictions-for-bosnia",
    "https://www.forebet.com/en/predictions-botswana",
    "https://www.forebet.com/en/football-tips-and-predictions-for-brazil",
    "https://www.forebet.com/en/football-tips-and-predictions-for-bulgaria",
    "https://www.forebet.com/en/predictions-burkina-faso",
    "https://www.forebet.com/en/predictions-burundi",
    "https://www.forebet.com/en/cambodia",
    "https://www.forebet.com/en/cameroon",
    "https://www.forebet.com/en/predictions-canada",
    "https://www.forebet.com/en/football-tips-and-predictions-for-chile",
    "https://www.forebet.com/en/football-tips-and-predictions-for-china",
    "https://www.forebet.com/en/football-tips-and-predictions-for-colombia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-costa-rica",
    "https://www.forebet.com/en/football-predictions-for-croatia",
    "https://www.forebet.com/en/predictions-cuba",
    "https://www.forebet.com/en/predictions-curacao",
    "https://www.forebet.com/en/football-tips-and-predictions-for-cyprus",
    "https://www.forebet.com/en/football-tips-and-predictions-for-czech-rep",
    "https://www.forebet.com/en/predictions-dr-congo",
    "https://www.forebet.com/en/football-tips-and-predictions-for-denmark",
    "https://www.forebet.com/en/predictions-djibouti",
    "https://www.forebet.com/en/predictions-dominican-republic",
    "https://www.forebet.com/en/football-tips-and-predictions-for-ecuador",
    "https://www.forebet.com/en/football-tips-and-predictions-for-egypt",
    "https://www.forebet.com/en/football-tips-and-predictions-for-el-salvador",
    "https://www.forebet.com/en/football-tips-and-predictions-for-england",
    "https://www.forebet.com/en/football-tips-and-predictions-for-estonia",
    "https://www.forebet.com/en/predictions-ethiopia",
    "https://www.forebet.com/en/predictions-faroe-islands",
    "https://www.forebet.com/en/predictions-fiji",
    "https://www.forebet.com/en/football-tips-and-predictions-for-finland",
    "https://www.forebet.com/en/football-tips-and-predictions-for-france",
    "https://www.forebet.com/en/predictions-gabon",
    "https://www.forebet.com/en/gambia-predictions",
    "https://www.forebet.com/en/football-tips-and-predictions-for-georgia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-germany",
    "https://www.forebet.com/en/football-tips-and-predictions-for-ghana",
    "https://www.forebet.com/en/predictions-gibraltar",
    "https://www.forebet.com/en/football-tips-and-predictions-for-greece",
    "https://www.forebet.com/en/football-tips-and-predictions-for-guatemala",
    "https://www.forebet.com/en/predictions-guinea",
    "https://www.forebet.com/en/predictions-haiti",
    "https://www.forebet.com/en/football-tips-and-predictions-for-honduras",
    "https://www.forebet.com/en/predictions-for-hong-kong",
    "https://www.forebet.com/en/football-tips-and-predictions-for-hungary",
    "https://www.forebet.com/en/football-tips-and-predictions-for-iceland",
    "https://www.forebet.com/en/football-tips-and-predictions-for-india",
    "https://www.forebet.com/en/football-tips-and-predictions-for-indonesia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-iran",
    "https://www.forebet.com/en/predictions-iraq",
    "https://www.forebet.com/en/football-tips-and-predictions-for-ireland",
    "https://www.forebet.com/en/football-tips-and-predictions-for-israel",
    "https://www.forebet.com/en/football-tips-and-predictions-for-italy",
    "https://www.forebet.com/en/predictions-ivory-coast",
    "https://www.forebet.com/en/predictions-jamaica",
    "https://www.forebet.com/en/football-tips-and-predictions-for-japan",
    "https://www.forebet.com/en/jordan",
    "https://www.forebet.com/en/football-tips-and-predictions-for-kazakhstan",
    "https://www.forebet.com/en/football-tips-and-predictions-for-kenya",
    "https://www.forebet.com/en/predictions-kosovo",
    "https://www.forebet.com/en/predictions-kuwait",
    "https://www.forebet.com/en/predictions-kyrgyzstan",
    "https://www.forebet.com/en/predictions-laos",
    "https://www.forebet.com/en/football-tips-and-predictions-for-latvia",
    "https://www.forebet.com/en/predictions-lebanon",
    "https://www.forebet.com/en/predictions-lesotho",
    "https://www.forebet.com/en/libya",
    "https://www.forebet.com/en/football-tips-and-predictions-for-lithuania",
    "https://www.forebet.com/en/predictions-for-luxembourg",
    "https://www.forebet.com/en/predictions-macau",
    "https://www.forebet.com/en/predictions-malawi",
    "https://www.forebet.com/en/predictions-malaysia",
    "https://www.forebet.com/en/predictions-mali",
    "https://www.forebet.com/en/football-tips-and-predictions-for-malta",
    "https://www.forebet.com/en/predictions-mauritania",
    "https://www.forebet.com/en/predictions-mauritius",
    "https://www.forebet.com/en/football-tips-and-predictions-for-mexico",
    "https://www.forebet.com/en/tips-and-predictions-for-moldova",
    "https://www.forebet.com/en/predictions-mongolia",
    "https://www.forebet.com/en/tips-and-predictions-for-montenegro",
    "https://www.forebet.com/en/tips-and-predictions-for-morocco",
    "https://www.forebet.com/en/predictions-mozambique",
    "https://www.forebet.com/en/predictions-myanmar",
    "https://www.forebet.com/en/predictions-nepal",
    "https://www.forebet.com/en/football-tips-and-predictions-for-netherlands",
    "https://www.forebet.com/en/football-tips-and-predictions-for-new-zealand",
    "https://www.forebet.com/en/nicaragua",
    "https://www.forebet.com/en/nigeria",
    "https://www.forebet.com/en/tips-and-predictions-for-macedonia",
    "https://www.forebet.com/en/northern-ireland",
    "https://www.forebet.com/en/football-tips-and-predictions-for-norway",
    "https://www.forebet.com/en/oman",
    "https://www.forebet.com/en/predictions-palestine",
    "https://www.forebet.com/en/predictions-for-panama",
    "https://www.forebet.com/en/football-tips-and-predictions-for-paraguay",
    "https://www.forebet.com/en/football-tips-and-predictions-for-peru",
    "https://www.forebet.com/en/predictions-philippines",
    "https://www.forebet.com/en/football-tips-and-predictions-for-poland",
    "https://www.forebet.com/en/football-tips-and-predictions-for-portugal",
    "https://www.forebet.com/en/predictions-qatar",
    "https://www.forebet.com/en/predictions-republic-of-the-congo",
    "https://www.forebet.com/en/football-tips-and-predictions-for-romania",
    "https://www.forebet.com/en/football-tips-and-predictions-for-russia",
    "https://www.forebet.com/en/predictions-rwanda",
    "https://www.forebet.com/en/san-marino",
    "https://www.forebet.com/en/football-tips-and-predictions-for-saudi-arabia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-scotland",
    "https://www.forebet.com/en/senegal",
    "https://www.forebet.com/en/football-tips-and-predictions-for-serbia",
    "https://www.forebet.com/en/sierra-leone-predictions",
    "https://www.forebet.com/en/football-tips-and-predictions-for-singapore",
    "https://www.forebet.com/en/predictions-and-tips-for-slovakia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-slovenia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-somalia",
    "https://www.forebet.com/en/football-tips-and-predictions-for-south-africa",
    "https://www.forebet.com/en/football-tips-and-predictions-for-south-korea",
    "https://www.forebet.com/en/football-tips-and-predictions-for-spain",
    "https://www.forebet.com/en/sudan",
    "https://www.forebet.com/en/football-tips-and-predictions-for-Suriname",
    "https://www.forebet.com/en/football-tips-and-predictions-for-sweden",
    "https://www.forebet.com/en/football-tips-and-predictions-for-switzerland",
    "https://www.forebet.com/en/syria",
    "https://www.forebet.com/en/predictions-taiwan",
    "https://www.forebet.com/en/predictions-tajikistan",
    "https://www.forebet.com/en/predictions-tanzania",
    "https://www.forebet.com/en/football-tips-and-predictions-for-thailand",
    "https://www.forebet.com/en/predictions-togo",
    "https://www.forebet.com/en/football-tips-and-predictions-for-trinidad-and-tobago",
    "https://www.forebet.com/en/football-tips-and-predictions-for-tunisia",
    "https://www.forebet.com/en/predictions-turkmenistan",
    "https://www.forebet.com/en/football-tips-and-predictions-for-turkey",
    "https://www.forebet.com/en/predictions-uae",
    "https://www.forebet.com/en/predictions-uganda",
    "https://www.forebet.com/en/football-tips-and-predictions-for-ukraine",
    "https://www.forebet.com/en/football-tips-and-predictions-for-usa",
    "https://www.forebet.com/en/football-tips-and-predictions-for-uruguay",
    "https://www.forebet.com/en/football-tips-and-predictions-for-Uzbekistan",
    "https://www.forebet.com/en/football-tips-and-predictions-for-venezuela",
    "https://www.forebet.com/en/football-tips-and-predictions-for-vietnam",
    "https://www.forebet.com/en/tips-and-predictions-for-wales",
    "https://www.forebet.com/en/football-tips-and-predictions-for-zambia",
    "https://www.forebet.com/en/predictions-zimbabwe",
    "https://www.forebet.com/en/predictions-africa",
    "https://www.forebet.com/en/predictions-asia",
    "https://www.forebet.com/en/predictions-australia",
    "https://www.forebet.com/en/predictions-europe",
    "https://www.forebet.com/en/predictions-north-central-america",
    "https://www.forebet.com/en/south-america",
    "https://www.forebet.com/en/predictions-world",
]


class ForebetFinder(BaseMatchFinder):
    # TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        return list(TOP_LEAGUES.keys()) if self.top_leagues_only else ALL_LINKS

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        league = TOP_LEAGUES.get(url)
        soup = BeautifulSoup(html, "html.parser")
        all_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")
        logger.info(f"Found {len(all_anchors)} matches to scan")

        for anchor in all_anchors:
            try:
                home_team = anchor.find("div", class_="tnms").find("span", class_="homeTeam").get_text()
                away_team = anchor.find("div", class_="tnms").find("span", class_="awayTeam").get_text()

                if anchor.find("div", class_="scoreLnk").get_text().strip() != "":
                    logger.info(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date_str = anchor.find("span", class_="date_bah").get_text().strip()
                match_date = datetime.strptime(match_date_str, "%d/%m/%Y %H:%M")

                home = float(anchor.find("div", class_="ex_sc").get_text().split("-")[0])
                away = float(anchor.find("div", class_="ex_sc").get_text().split("-")[1])
                predictions = [Score(FOREBET_NAME, home, away)]

                odds_tags = [o.get_text() for o in anchor.find("div", class_="haodd").find_all("span")]
                odds = Odds(
                    home=float(odds_tags[0]) if odds_tags[0] not in ("", " - ") else None,
                    draw=float(odds_tags[1]) if odds_tags[1] not in ("", " - ") else None,
                    away=float(odds_tags[2]) if odds_tags[2] not in ("", " - ") else None,
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds, league=league))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error - {e}")
