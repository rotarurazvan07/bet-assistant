import time
import json
from itertools import product
from bs4 import BeautifulSoup
from bet_framework.WebScraper import WebScraper, ScrapeMode

# List of targets: (url, selector_to_wait, name)
TARGETS = [
    # Forebet
    # ("https://www.forebet.com/en/football-predictions", "div#body-main", "Forebet Parse"),

    # Predictz
    ("https://www.predictz.com/", ".dd.nav-select", "Predictz Prepare"),
    ("https://www.predictz.com/predictions/england/premier-league/", ".pzcnth", "Predictz Parse"),

    # FootballBettingTips
    # ("https://www.footballbettingtips.org/", "h3", "FootballBettingTips Prepare"),
    #("https://www.footballbettingtips.org/predictions/england/premier-league/", "table.results", "FootballBettingTips Parse"),

    # ScorePredictor
    ("https://scorepredictor.net/index.php?section=football", ".block_categories", "ScorePredictor Prepare"),
    ("https://scorepredictor.net/index.php?section=football&season=EnglandPremier", ".table_dark", "ScorePredictor Parse"),

    # SoccerVista
    ("https://www.soccervista.com/", "h3", "SoccerVista Prepare"),
    ("https://www.soccervista.com/italy/serie-a/COuk57Ci/", "tbody", "SoccerVista Parse"),

    # Vitibet
    ("https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en", "ul#primarne", "Vitibet Prepare"),
    ("https://www.vitibet.com/index.php?clanek=tips&sekce=fotbal&liga=england1&lang=en", "table.tabulkaquick", "Vitibet Parse"),

    # WinDrawWin
    ("https://www.windrawwin.com/predictions/", "div.widetable", "WinDrawWin Prepare"),
    ("https://www.windrawwin.com/tips/england-premier-league/", "div.wdwtablest", "WinDrawWin Parse"),

    # WhoScored
    ("https://www.whoscored.com/previews", "table.grid", "WhoScored Prepare"),
    ("https://www.whoscored.com/matches/1903410/preview/england-premier-league-2025-2026-manchester-united-crystal-palace", "div#preview-prediction", "WhoScored Parse"),
]

def generate_configs():
    """Generate all possible scraping configurations from fastest to slowest."""

    # 1. FAST Mode (fetcher)
    for stealth in [True, False]:
        yield {
            "mode": "FAST",
            "stealthy_headers": stealth
        }

    # 2. DYNAMIC Mode combinations
    solve_cf_options = [False, True]
    disable_res_options = [True, False]
    network_idle_options = [False, True]
    wait_until_options = ["load", "domcontentloaded", "networkidle"]
    extra_waits = [0, 2, 5]

    # Combine them
    combos = list(product(solve_cf_options, disable_res_options, network_idle_options, wait_until_options, extra_waits))

    # Sort combos roughly by expected speed
    combos.sort(key=lambda x: (x[0], not x[1], x[2], x[3] == "networkidle", x[4]))

    for solve_cf, disable_res, net_idle, wait_u, extra_w in combos:
        yield {
            "mode": "BROWSER",
            "solve_cloudflare": solve_cf,
            "disable_resources": disable_res,
            "network_idle": net_idle,
            "wait_until": wait_u,
            "extra_wait": extra_w
        }

def run_benchmark(url, selector, config):
    start_time = time.time()
    html = ""
    status = "failed"
    error = ""

    try:
        if config["mode"] == "FAST":
            html = WebScraper.fetch(url, stealthy_headers=config["stealthy_headers"])
        else:
            with WebScraper.browser(
                headless=True,
                solve_cloudflare=config["solve_cloudflare"],
                disable_resources=config["disable_resources"],
                network_idle=config["network_idle"],
                wait_until=config["wait_until"]
            ) as session:
                resp = session.fetch(url)
                html = resp.html_content
                if config.get("extra_wait", 0) > 0:
                    time.sleep(config["extra_wait"])
                    try:
                        html = session.page.content()
                    except:
                        html = session.browser_page.content()

        if WebScraper.is_blocked(html):
            status = "blocked"
        else:
            soup = BeautifulSoup(html, "html.parser")
            if soup.select_one(selector):
                status = "success"
            else:
                status = "selector_not_found"

    except Exception as e:
        status = "error"
        error = str(e)

    duration = time.time() - start_time
    return {
        "status": status,
        "duration": duration,
        "html_preview": html[:200].replace("\n", " "),
        "error": error
    }

def main():
    results = {}

    for url, selector, name in TARGETS:
        print(f"\n[Benchmarking] {name} | URL: {url} | Selector: {selector}")
        results[name] = []

        configs = list(generate_configs())
        print(f"Testing {len(configs)} configurations...")

        for i, config in enumerate(configs):
            print(f"  [{i+1}/{len(configs)}] testing {config['mode']} (solve_cf={config.get('solve_cloudflare')}, wait={config.get('wait_until')}, extra={config.get('extra_wait', 0)})...", end="\r")
            res = run_benchmark(url, selector, config)

            config_copy = config.copy()
            config_copy.update(res)
            results[name].append(config_copy)

            if res["status"] == "success":
                print(f"\n  [SUCCESS] Found working method in {res['duration']:.2f}s: {config}")
                # Early break on first working method (the fastest due to sorting)
                break

    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("\nBenchmark complete. Results saved to benchmark_results.json")

if __name__ == "__main__":
    main()
