from datetime import datetime, timedelta

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Odds, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

FOREBET_URL = "https://www.forebet.com"
FOREBET_NAME = "forebet"

TOP_LEAGUES = [
    "https://www.forebet.com/en/predictions-europe/uefa-champions-league",
    "https://www.forebet.com/en/predictions-europe/uefa-europa-league",
    "https://www.forebet.com/en/predictions-europe/uefa-europa-conference-league",
    "https://www.forebet.com/en/football-tips-and-predictions-for-england/premier-league",
    "https://www.forebet.com/en/football-tips-and-predictions-for-italy/serie-a",
    "https://www.forebet.com/en/football-tips-and-predictions-for-spain/primera-division",
    "https://www.forebet.com/en/football-tips-and-predictions-for-germany/bundesliga",
    "https://www.forebet.com/en/football-tips-and-predictions-for-france/ligue1",
    "https://www.forebet.com/en/football-tips-and-predictions-for-belgium/jupiler-pro-league",
    "https://www.forebet.com/en/football-tips-and-predictions-for-england/championship",
    "https://www.forebet.com/en/football-tips-and-predictions-for-portugal/liga-portugal",
    "https://www.forebet.com/en/football-tips-and-predictions-for-brazil/serie-a",
    "https://www.forebet.com/en/football-tips-and-predictions-for-usa/mls",
    "https://www.forebet.com/en/football-tips-and-predictions-for-netherlands/eredivisie",
    "https://www.forebet.com/en/football-tips-and-predictions-for-denmark/superliga",
    "https://www.forebet.com/en/football-tips-and-predictions-for-poland/ekstraklasa",
    "https://www.forebet.com/en/football-tips-and-predictions-for-argentina/liga-profesional",
    "https://www.forebet.com/en/football-tips-and-predictions-for-japan/j1-league",
    "https://www.forebet.com/en/football-tips-and-predictions-for-turkey/super-lig",
    "https://www.forebet.com/en/football-tips-and-predictions-for-sweden/allsvenskan",
    "https://www.forebet.com/en/football-predictions-for-croatia/hnl",
    "https://www.forebet.com/en/football-tips-and-predictions-for-mexico/liga-mx",
    "https://www.forebet.com/en/football-tips-and-predictions-for-spain/segunda-division",
    "https://www.forebet.com/en/football-tips-and-predictions-for-norway/eliteserien",
    "https://www.forebet.com/en/football-tips-and-predictions-for-austria/bundesliga",
    "https://www.forebet.com/en/football-tips-and-predictions-for-switzerland/super-league",
    "https://www.forebet.com/en/football-tips-and-predictions-for-italy/serie-b",
    "https://www.forebet.com/en/football-tips-and-predictions-for-germany/2-bundesliga",
    "https://www.forebet.com/en/football-tips-and-predictions-for-france/ligue2",
    "https://www.forebet.com/en/football-tips-and-predictions-for-scotland/premiership",
]

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

    def get_urls(self) -> list[str]:
        return TOP_LEAGUES if self.top_leagues_only else ALL_LINKS

    def _parse_page(self, url: str, page: Page) -> None:
        all_anchors = page.select("#body-main .rcnt")
        logger.info(f"Found {len(all_anchors)} matches to scan on {url}")

        for anchor in all_anchors:
            try:
                home_team = anchor.find(".tnms .homeTeam").text()
                away_team = anchor.find(".tnms .awayTeam").text()

                if anchor.find(".scoreLnk").text().strip() != "":
                    logger.debug(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date_str = anchor.find(".date_bah").text().strip()
                match_date = datetime.strptime(match_date_str, "%d/%m/%Y %H:%M") + timedelta(hours=1)

                score_text = anchor.find(".ex_sc").text()
                home_score = float(score_text.split("-")[0])
                away_score = float(score_text.split("-")[1])
                predictions = [Score(FOREBET_NAME, home_score, away_score)]

                odds_tags = [o.text() for o in anchor.select(".haodd span")]
                odds = Odds(
                    home=float(odds_tags[0]) if len(odds_tags) > 0 and odds_tags[0] not in ("", " - ") else None,
                    draw=float(odds_tags[1]) if len(odds_tags) > 1 and odds_tags[1] not in ("", " - ") else None,
                    away=float(odds_tags[2]) if len(odds_tags) > 2 and odds_tags[2] not in ("", " - ") else None,
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error on {url} - {e}")
