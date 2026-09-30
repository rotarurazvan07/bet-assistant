"""One-shot generator for all finder HTML fixtures (issue #69, cycle 8).

Builds minimal synthetic HTML matching each finder's ACTUAL selectors/regex,
with FUTURE dates (2035+) so fixtures stay valid for decades (parse tests patch
validate_match_date — decision D2). Predictz/SoccerVista use TODAY+1 closest-year
dates because their year-search is +-1-year bounded (decision D5).

Run:  cd bet_crawler && ../.venv/bin/python tests/fixtures/generate_fixtures.py
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

FIXTURES = Path(__file__).parent / "html"

FUTURE_DATE = datetime(2035, 6, 15)  # Saturday; fixtures valid ~65y vs date window
# D53: FIXED anchor date (was datetime.now()+1 — fixtures rotted when the
# discovery window [today, today+N] slid past the baked-in date overnight;
# 4 CI failures on 2026-09-26). Consumers of "in-window" fixture dates must
# freeze the finder's clock to a date where this anchor is in-window — see
# the clock-freeze fixtures in test_oddsportal.py / test_betexplorer.py
# (predictz D5 pattern). Byte-stable: anchor equals the originally committed
# fixture dates, so regeneration is a no-op diff.
ANCHOR_TOMORROW = datetime(2026, 9, 25).date()  # 2026-09-25 (TODAY+1 when generated in cycle 8)
TOMORROW = ANCHOR_TOMORROW


def w(key, name, html):
    d = FIXTURES / key
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(html, encoding="utf-8")
    print(f"wrote {key}/{name} ({len(html)}b)")


# ─── betclan ────────────────────────────────────────────────────────────────

BETCLAN_LISTING = """<html><body>
<div class="bclisttip"><a href="https://www.betclan.com/predictions/match-1"></a></div>
<div class="bclisttip"><a href="https://www.betclan.com/predictions/match-2"></a></div>
</body></html>"""

BETCLAN_MATCH = """<html><body>
<div class="teamtophome">Arsenal</div>
<div class="teamtopaway">Chelsea</div>
<span class="dategamedetailsis">Date 2035-06-15 London</span>
<div class="predione"><div class="parttwo"><h5>junk</h5><h5>2-1</h5></div></div>
</body></html>"""

BETCLAN_BROKEN = "<html><body><div>Cloudflare challenge — enable JS</div></body></html>"

# ─── scorepredictor ─────────────────────────────────────────────────────────

SP_DD_MM = (FUTURE_DATE + timedelta(days=1)).strftime("%d.%m")

SCOREPREDICTOR_LEAGUE = f"""<html><body>
<table class="table_dark">
<tr><td>Date</td><td>Home</td><td>HS</td><td>AS</td><td>Away</td></tr>
<tr><td>{SP_DD_MM}</td><td>Arsenal</td><td>2</td><td>1</td><td>Chelsea</td></tr>
<tr><td>{SP_DD_MM}</td><td>Youth U19 XI</td><td>x</td><td>2</td><td>Rangers</td></tr>
<tr><td>{SP_DD_MM}</td><td>Spurs</td><td>3</td><td>3</td><td>Liverpool</td></tr>
</table>
</body></html>"""

SCOREPREDICTOR_BROKEN = "<html><body><p>No matches within next 5 days</p><p>x</p></body></html>"

# ─── forebet ────────────────────────────────────────────────────────────────

FOREBET_LEAGUE = """<html><body><div id="body-main">
<div class="rcnt">
  <div class="tnms"><span class="homeTeam">Real Madrid</span><span class="awayTeam">Barcelona</span></div>
  <div class="scoreLnk"></div>
  <span class="date_bah">15/06/2035 20:00</span>
  <div class="ex_sc">2-1</div>
  <div class="haodd"><span>1.85</span><span>3.40</span><span>4.10</span></div>
</div>
<div class="rcnt">
  <div class="tnms"><span class="homeTeam">Atletico</span><span class="awayTeam">Sevilla</span></div>
  <div class="scoreLnk">1:0</div>
  <span class="date_bah">15/06/2035 18:00</span>
  <div class="ex_sc">1-0</div>
  <div class="haodd"><span> - </span><span></span><span>2.50</span></div>
</div>
</div></body></html>"""

FOREBET_BROKEN = '<html><body><div id="body-main"><div class="rcnt"><span>future</span></div></div></body></html>'

# ─── vitibet ────────────────────────────────────────────────────────────────

VITIBET_LEAGUE = """<html><body>
<div style="background: linear-gradient(...)" ><span>15.06.2035</span><span> Kickoff list</span></div>
<a class="upcoming-match-wrapper" href="#">
  <div class="mc-team"><span>Juventus</span></div>
  <div class="mc-team"><span>Napoli</span></div>
  <div class="mc-score">2 : 1</div>
</a>
<a class="upcoming-match-wrapper" href="#">
  <div class="mc-team"><span>Milan</span></div>
  <div class="mc-team"><span>Inter</span></div>
  <div class="mc-score">1 : 1</div>
</a>
</body></html>"""

VITIBET_BROKEN = "<html><body><p>No games today</p></body></html>"

# ─── predictz (closest-year: TODAY+1 weekday-correct) ──────────────────────

PZ_DATE = TOMORROW
PZ_HEADER = PZ_DATE.strftime("%A, %B %d")  # "Friday, September 25" -> %A %B %d %Y after clean
PZ_ROW_DATE = f"{PZ_DATE.day:02d} {PZ_DATE.strftime('%b')}"  # td content used for... (not needed; h2 carries date)

PREDICTZ_LEAGUE = f"""<html><body>
<div class="pzcnth"><h2>{PZ_HEADER}</h2></div>
<div class="pzcnth">
  <table><tr>
    <td>2-1</td>
    <div class="fixt"><span>Arsenal vs Chelsea</span></div>
    <td class="odds">1.90</td><td class="odds">3.50</td><td class="odds">4.20</td>
  </tr></table>
</div>
</body></html>"""

PREDICTZ_BROKEN = "<html><body><p>This could be due to games currently in play</p></body></html>"

# ─── windrawwin per_match ────────────────────────────────────────────────────

WDW_LD = '{"@type": "SportsEvent", "startDate": "2035-06-15T19:45:00+00:00"}'

WINDRAWWIN_LEAGUE_HUB = """<html><body><div class="widetable">
<tr><td>Header row</td></tr>
<tr><td>European Leagues</td></tr>
<tr><td><a href="https://www.windrawwin.com/tips/england-premier-league/"></a></td></tr>
</div></body></html>"""

WINDRAWWIN_FIXTURES = """<html><body>
<div class="wtfixt"><a href="https://www.windrawwin.com/match/arsenal-chelsea/"></a></div>
<div class="wtfixt"><a href="https://www.windrawwin.com/match/spurs-liverpool/"></a></div>
</body></html>"""

WINDRAWWIN_MATCH = f"""<html><body>
<h1 class="h1sm">Arsenal v Chelsea</h1>
<script type="application/ld+json">{WDW_LD}</script>
<div class="featurescore">2-1</div>
<div class="compareoddswrapper"><div class="feature2">MATCH WINNER</div><a class="btnstsm">2.10</a><a class="btnstsm">3.40</a><a class="btnstsm">3.75</a></div>
<div class="compareoddswrapper"><div class="feature2">BOTH TEAMS TO SCORE</div><a class="btnstsm">1.85</a><a class="btnstsm">1.95</a></div>
<div class="compareoddswrapper"><div class="feature2">OVER/UNDER 2.5 GOALS</div><a class="btnstsm">1.70</a><a class="btnstsm">2.10</a></div>
<div class="compareoddswrapper"><div class="feature2">OVER/UNDER 1.5 GOALS</div><a class="btnstsm">1.30</a><a class="btnstsm">3.40</a></div>
</body></html>"""

WINDRAWWIN_CLOSED = "<html><body><h1>Voting Is Now Closed</h1></body></html>"

# ─── windrawwin per_league ───────────────────────────────────────────────────

WDW_LG_DATE = (FUTURE_DATE).strftime("%A, %B %d, %Y")

WINDRAWWIN_LEAGUE = (
    '<html><body><div class="wdwtablest mb30">'
    "<b></b><b></b>"
    f'<div class="wttrdt">Today, {WDW_LG_DATE}</div>'
    "<div><div><div>Arsenal</div></div><div><div>Chelsea</div></div><div>2-1</div>"
    '<div class="ob">'
    '<div class="wtmo"><span></span><span>2.05</span><span>3.30</span><span>3.80</span></div>'
    '<div class="wtou"><span></span><span>1.65</span><span>2.15</span></div>'
    '<div class="wtbt"><span></span><span>1.90</span><span>1.90</span></div>'
    "</div></div>"
    '<div><div><div>Liverpool</div></div><div><div>Spurs</div></div><div>3-3</div><div class="ob"></div></div>'
    "</div></body></html>"
)

WINDRAWWIN_LEAGUE_BROKEN = "<html><body><div>no matches today</div></body></html>"

# ─── onemillionpredictions ────────────────────────────────────────────────────

OMP_MATCHDAY_DATE = (FUTURE_DATE + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

ONEMILLION_LEAGUE = f"""<html><body>
<table><tbody><tr><td>header</td></tr></tbody></table>
<table><tbody>
<tr><td><span class="fulldatetime">{OMP_MATCHDAY_DATE}</span></td>
    <td><p>Arsenal</p><p>Chelsea</p></td>
    <td>2:1</td></tr>
<tr><td><span class="fulldatetime">{OMP_MATCHDAY_DATE}</span></td>
    <td><p>Rangers</p><p>Celtic</p></td>
    <td>1:2</td></tr>
<tr><td>Matchday 1</td><td>x</td><td>y</td></tr>
</tbody></table>
</body></html>"""

ONEMILLION_BROKEN = "<html><body><p>no predictions</p></body></html>"

# ─── eaglepredict ────────────────────────────────────────────────────────────

EAGLEPREDICT_PAGE = """<html><body>
<div class="league-block">
  <span>Sat - 15 Jun 2035</span>
  <div class="match-row">
    <img src="/a.png" alt="Arsenal Logo"/><img src="/b.png" alt="Chelsea Logo"/>
    <span>Correct Score: 2-1</span>
    <span>19:45</span>
  </div>
  <div class="match-row">
    <img src="/c.png" alt="Milan Logo"/><img src="/d.png" alt="Inter Logo"/>
    <span>Correct Score: 1-1</span>
    <span>21:00</span>
  </div>
</div>
</body></html>"""

EAGLEPREDICT_BROKEN = "<html><body><p>Correct Score: 2-1</p></body></html>"

# ─── xgscore ────────────────────────────────────────────────────────────────

XGSCORE_DISCOVERY = """<html><body>
<div class="xgs-category-forecast-fixture">
  <a class="xgs-category-forecast-fixture_teams" href="/prediction/arsenal-chelsea"></a>
</div>
<div class="xgs-category-forecast-fixture">
  <a class="xgs-category-forecast-fixture_teams" href="/prediction/milan-inter"></a>
</div>
</body></html>"""

XGSCORE_MATCH = """<html><body>
<strong class="xgs-game-header_team-name">Arsenal</strong>
<strong class="xgs-game-header_team-name">Chelsea</strong>
<div class="xgs-game-header_datetime">June 15, 2035 19:45</div>
<p>Prediction: Correct Score: 2-1 (xG 1.8 - 0.9)</p>
<xgs-odds></xgs-odds>
<xgs-odds>
  <span class="odds-cell_label">1x</span><span class="text-sm-tiny"> 1.25 </span>
  <span class="odds-cell_label">12</span><span class="text-sm-tiny"> 1.30 </span>
  <span class="odds-cell_label">x2</span><span class="text-sm-tiny"> 1.45 </span>
</xgs-odds>
</body></html>"""

XGSCORE_FINISHED = """<html><body>
<strong class="xgs-game-header_team-name">Old FC</strong>
<strong class="xgs-game-header_team-name">Past FC</strong>
<div class="xgs-game-header_datetime">Match finished</div>
<p>Correct Score: 3-0</p>
</body></html>"""

XGSCORE_BROKEN = "<html><body><p>loading...</p></body></html>"

# ─── soccervista per_league ──────────────────────────────────────────────────

SV_LG_DATE = TOMORROW.strftime("%d %b")  # closest-year resolution (decision D5)

SOCCERVISTA_LEAGUE = f"""<html><body>
<div><h2>Upcoming Predictions</h2>
<table><tbody>
<tr><td>{SV_LG_DATE}</td><td><span>x</span><span>Arsenal</span></td>
    <td>vs</td><td><span>Chelsea</span></td><td>1</td><td>x</td><td>2:1</td>
    <a href="/fr/match/arsenal-chelsea/">detail</a></td></tr>
</tbody></table></div>
</body></html>"""

SOCCERVISTA_LEAGUE_BROKEN = "<html><body><h1>Predictions</h1></body></html>"

# ─── soccervista per_match ───────────────────────────────────────────────────

SV_LD = '{"@type": ["Event", "SportsEvent"], "homeTeam": {"name": "Arsenal"}, "awayTeam": {"name": "Chelsea"}, "startDate": "2035-06-15T19:45"}'

SV_PRED_SCRIPT = 'var state = {"correctScorePrediction": {"score": "2:1", "probability": "31%"}};'

SOCCERVISTA_MATCH = f"""<html><body>
<script type="application/ld+json">{SV_LD}</script>
<script>{SV_PRED_SCRIPT}</script>
<a class="odds-link-1">2.10</a><a class="odds-link-X">3.40</a><a class="odds-link-2">3.75</a>
<a class="odds-link-over-2.5">1.70</a><a class="odds-link-under-2.5">2.10</a>
<a class="odds-link-yes">1.85</a><a class="odds-link-no">1.95</a>
</body></html>"""

SOCCERVISTA_MATCH_BROKEN = "<html><body><h1>Arsenal vs Chelsea</h1></body></html>"

# ─── footballpredictions ─────────────────────────────────────────────────────

FOOTBALLPREDICTIONS_LEAGUE = """<html><body>
<table class="table-tips"><tbody>
<tr>
  <td><span class="table-tips__team-wrapper"><span>Arsenal</span></span>
      <span class="table-tips__team-wrapper"><span>Chelsea</span></span>
      <span class="table-tips__date-time-wrapper" data-datetime="2035-06-15T20:00:00+01:00"></span></td>
  <td><ul><li>Tip: Home</li><li>Correct Score: 2-1</li></ul></td>
</tr>
<tr><td colspan="2">no tds with data here</td></tr>
</tbody></table>
</body></html>"""

FOOTBALLPREDICTIONS_BROKEN = "<html><body><p>No predictions yet</p></body></html>"

# ─── footballbettingtips ─────────────────────────────────────────────────────

FBT_DATE = FUTURE_DATE.strftime("%A, %d %B %Y")

FOOTBALLBETTINGTIPS_PAGE = f"""<html><body>
<h2>Other section</h2>
<h2>{FBT_DATE}</h2>
<table class="results">
<tr><th>Match</th><th>Tip</th><th>Score</th><th>Odds</th></tr>
<tr><td><a href="/m/1">Arsenal - Chelsea</a></td><td>2</td><td>2:1</td>
    <td><span class="desktop">2.10</span><span class="desktop">3.40</span><span class="desktop">3.75</span></td></tr>
<tr><td><a href="/m/2">Spurs - Liverpool</a></td><td>1</td><td>1:2</td>
    <td><span class="desktop">2.50</span><span class="desktop">3.20</span><span class="desktop">2.80</span></td></tr>
<tr><td>header-less row skipped</td></tr>
</table>
</body></html>"""

FOOTBALLBETTINGTIPS_BROKEN = "<html><body><p>no tips today</p></body></html>"

# ─── legitpredict ───────────────────────────────────────────────────────────

LP_DATE = FUTURE_DATE.strftime("%d-%m-%Y")

LEGITPREDICT_URL_DT = f"https://legitpredict.com/correct-score?dt={LP_DATE}"

LEGITPREDICT_PAGE = """<html><body>
<div class="content nopaddingsmall"><table><tbody>
<tr><td>20:45</td><td>ok</td><td>Arsenal VS Chelsea</td><td>2-1</td></tr>
<tr><td>21:00</td><td>ok</td><td>Milan VS Inter</td><td>1-1</td></tr>
<tr><td>22:00</td><td>bad</td><td>Broken VS Row</td><td>garbage</td></tr>
</tbody></table></div>
</body></html>"""

LEGITPREDICT_EMPTY = "<html><body><p>OOPS! NO GAME HERE</p></body></html>"

LEGITPREDICT_BROKEN = "<html><body><div>no table</div></body></html>"

# ─── oddsportal ─────────────────────────────────────────────────────────────

OP_TOMORROW_ISO = (datetime.combine(TOMORROW, datetime.min.time(), tzinfo=timezone.utc)).strftime("%Y-%m-%dT15:00:00Z")
OP_FUTURE_ISO = "2035-06-15T15:00:00Z"  # far out-of-window for discovery filter

ODDSPORTAL_LEAGUE = f"""<html><body>
<script type="application/ld+json">
{{"@graph": [
  {{"url": "https://www.oddsportal.com/match/in-window-1/", "startDate": "{OP_TOMORROW_ISO}", "eventStatus": "Scheduled"}},
  {{"url": "https://www.oddsportal.com/match/in-window-1/", "startDate": "{OP_TOMORROW_ISO}", "eventStatus": "Scheduled"}},
  {{"url": "https://www.oddsportal.com/match/out-window/", "startDate": "{OP_FUTURE_ISO}", "eventStatus": "Scheduled"}},
  {{"url": "https://www.oddsportal.com/match/cancelled/", "startDate": "{OP_TOMORROW_ISO}", "eventStatus": "Cancelled"}},
  {{"url": "https://www.oddsportal.com/match/no-date/"}}
]}}
</script>
</body></html>"""


def _oddsportal_page(tab):
    if tab == "base":
        return """<html><body>
<div data-testid="game-host"><a>Arsenal</a></div>
<div data-testid="game-guest"><a>Chelsea</a></div>
<div data-testid="game-time-item"><p>Sat</p><p>15 Jun 2035,</p></div>
</body></html>"""
    if tab == "1X2":
        return """<html><body><div data-testid="over-under-expanded-row">
<div data-testid="odd-container"><a class="odds-link">2.10</a></div>
<div data-testid="odd-container"><a class="odds-link">3.40</a></div>
<div data-testid="odd-container"><a class="odds-link">3.75</a></div>
</div></body></html>"""
    if tab == "Both Teams to Score":
        return """<html><body><div data-testid="over-under-expanded-row">
<div data-testid="odd-container"><a class="odds-link">1.85</a></div>
<div data-testid="odd-container"><a class="odds-link">1.95</a></div>
</div></body></html>"""
    if tab == "Double Chance":
        return """<html><body><div data-testid="over-under-expanded-row">
<div data-testid="odd-container"><a class="odds-link">1.25</a></div>
<div data-testid="odd-container"><a class="odds-link">1.30</a></div>
<div data-testid="odd-container"><a class="odds-link">1.45</a></div>
</div></body></html>"""
    # Over/Under tab
    rows = ""
    for line, over, under in [
        ("+0.5", "1.10", "8.00"),
        ("+1.5", "1.35", "3.10"),
        ("+2.5", "1.70", "2.10"),
        ("+3.5", "3.20", "1.34"),
        ("+4.5", "6.50", "1.09"),
    ]:
        rows += f"""<div data-testid="over-under-collapsed-row">
<div data-testid="over-under-collapsed-option-box">{line}</div>
<div data-testid="odd-container-default"><p>{over}</p></div>
<div data-testid="odd-container-default"><p>{under}</p></div>
</div>"""
    return f"<html><body>{rows}</body></html>"


ODDSPORTAL_BROKEN = "<html><body><p>Access denied</p></body></html>"

# ─── betexplorer ────────────────────────────────────────────────────────────

BE_TOMORROW_ISO = OP_TOMORROW_ISO

BETEXPLORER_LEAGUE = f"""<html><body>
<script type="application/ld+json">
[
  {{"url": "https://www.betexplorer.com/match/in-window-1/", "startDate": "{BE_TOMORROW_ISO}", "eventStatus": "Scheduled"}},
  {{"url": "https://www.betexplorer.com/match/out-window/", "startDate": "{OP_FUTURE_ISO}", "eventStatus": "Scheduled"}},
  {{"url": "https://www.betexplorer.com/match/postponed/", "startDate": "{BE_TOMORROW_ISO}", "eventStatus": {{"@id": "EventPostponed"}}}}
]
</script>
</body></html>"""


def _betexplorer_page(tab):
    if tab == "base":
        return """<html><body>
<ul class="list-details">
<li class="list-details__item"><div class="list-details__item__title">Arsenal</div></li>
<li class="list-details__item">19:45</li>
<li class="list-details__item"><div class="list-details__item__title">Chelsea</div></li>
</ul>
<div id="match-date">15.06.2035 - 19:45</div>
<div id="bettype_menu_best"><ul class="oddsComparison__ul bestOddsComparison"><li id="all"></li></ul></div>
</body></html>"""
    if tab in ("1X2", "Both Teams to Score", "Double Chance"):
        n = 2 if tab == "Both Teams to Score" else 3
        vals = ["2.10", "3.40"] + (["3.75"] if n == 3 else [])
        cells = "".join(f'<div class="oddsComparisonAll__average_text">{v}</div>' for v in vals)
        return f"<html><body>{cells}</body></html>"
    # Over/Under tab
    rows = ""
    for line, over, under in [
        ("0.50", "1.10", "8.00"),
        ("1.50", "1.35", "3.10"),
        ("2.50", "1.70", "2.10"),
        ("3.50", "3.20", "1.34"),
        ("4.50", "6.50", "1.09"),
    ]:
        rows += f"""<div data-all-handicap="{line}">
<div class="oddsComparisonAll__average_text" data-odd="{over}">o</div>
<div class="oddsComparisonAll__average_text" data-odd="{under}">u</div>
</div>"""
    return f"<html><body>{rows}</body></html>"


BETEXPLORER_BROKEN = "<html><body><p>no match data</p></body></html>"

# ─── main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    w("betclan", "listing.html", BETCLAN_LISTING)
    w("betclan", "match.html", BETCLAN_MATCH)
    w("betclan", "broken.html", BETCLAN_BROKEN)
    w("scorepredictor", "league.html", SCOREPREDICTOR_LEAGUE)
    w("scorepredictor", "broken.html", SCOREPREDICTOR_BROKEN)
    w("forebet", "league.html", FOREBET_LEAGUE)
    w("forebet", "broken.html", FOREBET_BROKEN)
    w("vitibet", "league.html", VITIBET_LEAGUE)
    w("vitibet", "broken.html", VITIBET_BROKEN)
    w("predictz", "league.html", PREDICTZ_LEAGUE)
    w("predictz", "broken.html", PREDICTZ_BROKEN)
    w("windrawwin", "hub.html", WINDRAWWIN_LEAGUE_HUB)
    w("windrawwin", "fixtures.html", WINDRAWWIN_FIXTURES)
    w("windrawwin", "match.html", WINDRAWWIN_MATCH)
    w("windrawwin", "closed.html", WINDRAWWIN_CLOSED)
    w("windrawwin", "league.html", WINDRAWWIN_LEAGUE)
    w("windrawwin", "league_broken.html", WINDRAWWIN_LEAGUE_BROKEN)
    w("onemillionpredictions", "league.html", ONEMILLION_LEAGUE)
    w("onemillionpredictions", "broken.html", ONEMILLION_BROKEN)
    w("eaglepredict", "page.html", EAGLEPREDICT_PAGE)
    w("eaglepredict", "broken.html", EAGLEPREDICT_BROKEN)
    w("xgscore", "discovery.html", XGSCORE_DISCOVERY)
    w("xgscore", "match.html", XGSCORE_MATCH)
    w("xgscore", "finished.html", XGSCORE_FINISHED)
    w("xgscore", "broken.html", XGSCORE_BROKEN)
    w("soccervista", "league.html", SOCCERVISTA_LEAGUE)
    w("soccervista", "league_broken.html", SOCCERVISTA_LEAGUE_BROKEN)
    w("soccervista", "match.html", SOCCERVISTA_MATCH)
    w("soccervista", "match_broken.html", SOCCERVISTA_MATCH_BROKEN)
    w("footballpredictions", "league.html", FOOTBALLPREDICTIONS_LEAGUE)
    w("footballpredictions", "broken.html", FOOTBALLPREDICTIONS_BROKEN)
    w("footballbettingtips", "page.html", FOOTBALLBETTINGTIPS_PAGE)
    w("footballbettingtips", "broken.html", FOOTBALLBETTINGTIPS_BROKEN)
    w("legitpredict", "page.html", LEGITPREDICT_PAGE)
    w("legitpredict", "empty.html", LEGITPREDICT_EMPTY)
    w("legitpredict", "broken.html", LEGITPREDICT_BROKEN)
    w("oddsportal", "league.html", ODDSPORTAL_LEAGUE)
    w("oddsportal", "match_1x2.html", _oddsportal_page("1X2"))
    w("oddsportal", "match_btts.html", _oddsportal_page("Both Teams to Score"))
    w("oddsportal", "match_dc.html", _oddsportal_page("Double Chance"))
    w("oddsportal", "match_ou.html", _oddsportal_page("Over/Under"))
    w("oddsportal", "match_base.html", _oddsportal_page("base"))
    w("oddsportal", "broken.html", ODDSPORTAL_BROKEN)
    w("betexplorer", "league.html", BETEXPLORER_LEAGUE)
    w("betexplorer", "match_1x2.html", _betexplorer_page("1X2"))
    w("betexplorer", "match_btts.html", _betexplorer_page("Both Teams to Score"))
    w("betexplorer", "match_dc.html", _betexplorer_page("Double Chance"))
    w("betexplorer", "match_ou.html", _betexplorer_page("Over/Under"))
    w("betexplorer", "match_base.html", _betexplorer_page("base"))
    w("betexplorer", "broken.html", BETEXPLORER_BROKEN)
    print("ALL FIXTURES WRITTEN")
