# 🎯 Bet Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)

A powerful, 24/7 automated betting intelligence platform. **Bet Assistant** crawls multiple sources, aggregates consensus data, calculates value pips, and manages your betting slips through a premium Dash dashboard.

---

## 🚀 Key Features

*   **Multi-Source Aggregation**: Intelligent crawlers for WhoScored, Forebet, SoccerVista, and more.
*   **Consensus Engine**: Calculates betting "Consensus" based on agreement across providers.
*   **Smart Slip Builder**: Dynamic generator that builds slips based on risk profiles (Low, Medium, High).
*   **Real-time Analytics**: Track your success rate, market accuracy, and ROI over time.
*   **24/7 Service Architecture**: Designed to run on a Raspberry Pi or server with automated daily updates.
*   **Premium Web UI**: High-performance dashboard with glassmorphism aesthetics and live status monitoring.

---

## 🐳 1. Docker Setup (Recommended)

The easiest way to get started is using Docker Compose. This ensures all dependencies and background services are configured correctly.

### Prerequisites

*   Docker & Docker Compose installed on your system
*   Git (to clone the repository)

### Installation Steps

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/rotarurazvan07/bet-assistant.git
    cd bet-assistant
    ```

2.  **Launch the stack**:
    ```bash
    docker compose -f setup/compose.yaml up -d
    ```

    This command starts three services:
    *   **Backend** (API server on port 8000)
    *   **Frontend** (Web dashboard on port 3002)
    *   **Bet-Updater** (Watchtower for automatic updates)

3.  **Access the dashboard**:
    Open your browser and navigate to `http://localhost:3002`.

### Stopping the Services

```bash
docker compose -f setup/compose.yaml down
```

### Viewing Logs

```bash
# All services
docker compose -f setup/compose.yaml logs -f

# Specific service
docker compose -f setup/compose.yaml logs -f backend
docker compose -f setup/compose.yaml logs -f frontend
```

### Data Persistence

The compose configuration mounts a `workspace` directory in your project folder:
*   `./workspace/config/` — Stores your profile configurations
*   `./workspace/data/` — Contains the SQLite databases (`matches.db`, `slips.db`)

**Important**: The backend automatically copies default configs from `/app/config/` to `/app/workspace/config/` on first launch. After that, edit the files in `./workspace/config/` to customize your settings.

---

## 📖 2. Frontend User Guide

The dashboard is the heart of Bet Assistant. It provides a real-time view of matches, slip building tools, analytics, and service management.

### <a name="dashboard-tabs"></a>Dashboard Tabs Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard Interface (http://localhost:3002)               │
├─────────────────────────────────────────────────────────────┤
│  [BETTING TIPS] [SMART BUILDER] [SLIPS] [ANALYTICS] [SERVICES] │
└─────────────────────────────────────────────────────────────┘
```

---

### <a name="tab-betting-tips"></a>📊 Betting Tips Tab

The **Betting Tips** tab displays all available matches with their consensus predictions and odds.

#### Features

*   **Live Preview**: Matches update automatically via WebSocket connection.
*   **Search & Filter**: Filter by team name or minimum consensus percentage.
*   **Sortable Columns**: Click any column header to sort (datetime, home/away teams, consensus values, odds).
*   **Manual Slip Builder**: Click any cell in the `1`, `X`, `2`, `O2.5`, `U2.5`, `BTTS Y`, `BTTS N` columns to add that selection to the side panel.
*   **Pagination**: Navigate through large result sets with 40 matches per page.

#### Table Columns

| Column | Description |
|--------|-------------|
| `#` | Row number (for reference) |
| `Date` | Match datetime (localized to your timezone) |
| `Home` / `Away` | Team names |
| `Sources` | Number of data providers covering this match |
| `1` / `X` / `2` | Consensus percentages for Home/Draw/Away result markets |
| `O2.5` / `U2.5` | Consensus percentages for Over/Under 2.5 goals |
| `BTTS Y` / `BTTS N` | Consensus percentages for Both Teams To Score |

#### Side Panel — Slip Builder

The permanent side panel on the right shows your pending manual selections:

*   **Legs List**: Each added selection displays match name, market, odds, and datetime.
*   **Total Odds**: Running product of all selected odds.
*   **Remove**: Click the ✕ button to remove a leg.
*   **Submit**: Enter units and click "Add to Slips" to save the slip to your database.

---

### <a name="tab-smart-builder"></a>🧠 Smart Builder Tab

The **Smart Builder** is the intelligent engine that automatically constructs betting slips based on configurable risk profiles.

#### What is Smart Builder?

Instead of manually picking legs, Smart Builder analyzes all available matches and selects the best combinations that meet your criteria. It uses a sophisticated scoring model that balances:

*   **Consensus strength** (agreement across sources)
*   **Number of sources** (data provider coverage)
*   **Odds proximity** (how close each pick is to your target per-leg odds)
*   **Match uniqueness** (no duplicate matches in a single slip)

#### Configuration Panel (Left Side)

The configuration is divided into logical sections:

---

##### **Bet Shape**

| Setting | Description | Default |
|---------|-------------|---------|
| **Target Odds** | Desired cumulative odds for the entire slip (e.g., 3.0 = 2.0 × 1.5). | `3.0` |
| **Target Legs** | Desired number of selections in the slip (1–10). | `3` |
| **Max Overflow Legs** | Extra legs allowed beyond target when good opportunities arise. Auto mode adds +1 for 2–4 leg targets, +2 for 5+. | `Auto` |

**Example**: Target Odds = 3.0, Target Legs = 3
*   Ideal per-leg odds = ∛3.0 ≈ 1.44
*   Builder will try to find 3 legs with odds around 1.44 each
*   If Max Overflow = 1, it may add a 4th leg if total odds are still close to target

---

##### **Quality Gate**

| Setting | Description | Default |
|---------|-------------|---------|
| **Consensus Floor** | Minimum source agreement percentage. Picks below this are discarded. | `50%` |
| **Min Odds** | Minimum bookmaker odds. Filters out extremely likely outcomes (value protection). | `1.05` |

**Example**: Consensus Floor = 70%
*   Only picks where ≥70% of sources agree on the outcome are considered
*   A match with consensus `1: 65%` would be excluded

---

##### **Markets**

Select which betting markets to include. Options:

*   `1` (Home Win)
*   `X` (Draw)
*   `2` (Away Win)
*   `O2.5` (Over 2.5 Goals)
*   `U2.5` (Under 2.5 Goals)
*   `BTTS Y` (Both Teams To Score — Yes)
*   `BTTS N` (Both Teams To Score — No)

**All markets** are selected by default. Uncheck to exclude specific markets from slip generation.

---

##### **Tolerance & Stop**

| Setting | Description | Default |
|---------|-------------|---------|
| **Tolerance Factor** | ±% band around the ideal per-leg odds. Tier 1 picks sit within this band and always rank above Tier 2. | `25%` |
| **Stop Threshold** | Stop building when total odds ≥ target × threshold AND enough legs are filled. | `91%` |
| **Min Legs Fill Ratio** | Minimum fraction of target legs before early stop is allowed. | `70%` |

**How Tolerance Works**:
*   Target Odds = 3.0, Target Legs = 3 → Ideal per-leg = 1.44
*   Tolerance = 25% → Acceptable range = 1.08 to 1.80
*   Picks within this range are **Tier 1** (prioritized)
*   Picks outside are **Tier 2** (used only if necessary)

**How Stop Threshold Works**:
*   Target Odds = 3.0, Stop Threshold = 91% → Stop when total ≥ 2.73
*   Combined with Min Legs Fill Ratio = 70% → Need at least 2 legs (70% of 3) before stopping early

---

##### **Scoring**

Two dual-sliders control how picks are ranked:

```
Balance ────────○──────── Quality
Sources ────────○──────── Consensus
```

*   **Quality vs Balance** (left): 
    *   Left (0.0) = prioritize odds closest to ideal (balance)
    *   Right (1.0) = prioritize high consensus and many sources (quality)
*   **Consensus vs Sources** (right):
    *   Left (0.0) = prioritize number of data sources
    *   Right (1.0) = prioritize consensus percentage

**Scoring Formula** (from [`BetAssistant.py`](bet_framework/BetAssistant.py:34-35)):
```
quality = consensus_vs_sources × consensus_score + (1 − consensus_vs_sources) × sources_score
final   = quality_vs_balance × quality + (1 − quality_vs_balance) × balance_score
```

Each axis is normalized to 0.0–1.0:
*   `consensus_score`: linear from `consensus_floor` → 100% = 1.0
*   `sources_score`: 0 sources → 0.0; max sources in pool → 1.0
*   `balance_score`: perfect match → 1.0; at tolerance edge → 0.0

---

#### Live Preview (Right Side)

The right panel shows a real-time preview of the slip that would be generated with the current configuration.

**Preview Card**:
*   **Total Odds**: Combined odds of all selected legs
*   **Legs**: Number of selections
*   **Out-of-band badge**: Appears if any Tier 2 picks are included (odds outside tolerance)

**Each Leg Card**:
*   Match name (clickable link to source)
*   Datetime
*   Market (e.g., `1`, `O2.5`, `BTTS Y`)
*   Odds (highlighted)
*   Consensus bar (visual progress bar showing agreement %)
*   Consensus & Sources text
*   Tier badge: "✓ Balanced" (Tier 1) or "⚠ Drift" (Tier 2)
*   Score (numeric value from the ranking algorithm)
*   **Exclude button (✕)**: Remove this specific match from consideration

**Excluded Matches Section**:
Shows all manually excluded matches. You can:
*   See why each was excluded (pattern, date, or manual)
*   Remove manual exclusions with the ✕ button
*   Clear all exclusions with "Reset excluded" button

---

#### Profiles & Automation

**Save a Profile**:
1.  Enter a profile name in the text field (e.g., `low_risk`, `high_value`)
2.  Adjust configuration to your liking
3.  Click **Save**
4.  The profile appears as a button in the Profiles section

**Load a Profile**:
Click any saved profile button to instantly load its configuration.

**Delete a Profile**:
Select a profile, then click **Delete**.

**Run Daily**:
Set a number (0–24) to indicate how many times per day this profile should automatically generate slips via the Services tab. The backend scheduler will run it at the configured "Generate Slips" hour.

**Add to Slips**:
Click **+ Add to Slips** to save the current preview as an actual betting slip in the database (appears in the Slips tab).

---

### <a name="tab-slips"></a>📋 Slips Tab

The **Slips** tab displays all generated betting slips, both from profiles and manual creation.

#### Features

*   **Slip Cards**: Each slip shows:
    *   Generation date & profile name
    *   Units staked
    *   Total odds
    *   Status badge (Won / Lost / Live / Pending)
    *   List of legs with match name, datetime, market, odds, and live score (if applicable)
    *   Delete button (only for fully pending slips)
*   **Filters**:
    *   Profile dropdown (All / specific profile / Manual)
    *   Hide settled (toggle to show only pending/live slips)
    *   Live only (toggle to show only slips with at least one live leg)
*   **Actions**:
    *   **✓ Validate Results**: Scrapes current scores and updates all pending/live legs
    *   **✦ Generate Slips**: Triggers all profiles with "Run Daily" > 0 to generate new slips immediately

#### Slip Status Logic

Derived from leg statuses (priority order):

1.  **Lost** — At least one leg is Lost
2.  **Live** — No Lost legs, but at least one Live
3.  **Pending** — No Lost or Live legs, but at least one Pending
4.  **Won** — All legs are Won

---

### <a name="tab-analytics"></a>📈 Analytics Tab

The **Analytics** tab provides deep insights into your betting performance.

#### Metrics Overview

Six stat cards at the top:

| Metric | Formula |
|--------|---------|
| **Total Bet** | Sum of units staked across all settled legs |
| **Gross Return** | Sum of `units × odds` for Won legs |
| **Net Profit** | Gross Return − Total Bet |
| **Win Rate** | (Won legs / Settled legs) × 100% |
| **ROI** | (Net Profit / Total Bet) × 100% |
| **Settled** | Number of legs with final outcome |
| **Won** | Count of Won legs |

---

#### Charts

**History Tracking**:

*   **Cumulative Net Profit**: Line chart showing profit over time
*   **Win Rate — Cumulative vs Rolling (10)**: Compare long-term win % with recent 10-leg average
*   **ROI % Over Time**: Return on Investment trend

**Market Statistics**:

*   **Net Profit Contribution by Market** (horizontal bar chart): Which markets are most profitable?
*   **Market Accuracy — Won vs Lost** (stacked bar): Success rate per market

**Correlation Analysis**:

*   **Win Rate by Number of Legs**: Does slip length affect success?
*   **Profile — Avg Odds vs Win Rate** (scatter plot): Bubble size = volume. Compare different profiles.

---

### <a name="tab-services"></a>⚙️ Services Tab

The **Services** tab manages automated background tasks.

#### Service Cards

Each crawler source appears as a card:

*   **Name**: Data provider (e.g., `whoscored`, `forebet`, `soccervista`)
*   **Status**: `● Active` or `○ Inactive` (toggle with the switch)
*   **Last Run**: Timestamp of most recent successful crawl
*   **Matches**: Count of matches collected in last run

Toggle services on/off to control which providers are used during data collection.

---

#### Scheduled Hours

Configure two daily automation tasks:

*   **Pull DB** (hour 0–23): When to automatically fetch new match data from all active sources
*   **Generate Slips** (hour 0–23): When to automatically generate slips for profiles with "Run Daily" > 0

**Example**: Set Pull DB = 06:00, Generate Slips = 08:00
*   Every day at 6 AM, the system fetches fresh match data
*   At 8 AM, it runs all daily-enabled profiles to create new slips

Click **Save Settings** to persist changes. The system recalculates schedules immediately.

---

## 🛠️ 3. Manual Crawling with `crawl.py`

If you prefer not to use Docker or need to run custom crawl operations, the `bet_crawler/crawl.py` module provides a full CLI.

### Modes Overview

```bash
python -m bet_crawler.crawl --mode <mode> [options]
```

| Mode | Purpose |
|------|---------|
| `prepare-scrape` | Collect match URLs from all active finders |
| `scrape` | Scrape match data from URLs into a chunk database |
| `merge` | Combine all chunk databases into a single final DB |
| `generate-slips` | Build slips using a specific profile YAML |
| `validate-slips` | Scrape results and settle pending legs |

---

### <a name="crawl-prepare"></a>Mode 1: Prepare Scrape

Collects URLs from all enabled finders and splits them into manageable chunks for parallel processing.

```bash
python -m bet_crawler.crawl \
  --mode prepare-scrape \
  --runners actions \
  --config_dir ./config \
  > urls.json
```

**Parameters**:

*   `--runners`: Which finder set to use
    *   `actions` — All cloud-based sources (Vitibet, ScorePredictor, Predictz, SoccerVista, WinDrawWin, OneMillionPredictions, xGScore, EaglePredict, LegitPredict)
    *   `local` — Local-only sources (WhoScored, Forebet, FootballBettingTips)
    *   `all` — Every registered finder
    *   `test` — Single finder for debugging (LegitPredict)
*   `--config_dir`: Path to config directory (contains `scraper_config.yaml`)

**Output**: JSON array of task objects printed to stdout:
```json
[
  {
    "db_path": "actions-1.db",
    "urls": "url1,url2,url3,..."
  },
  ...
]
```

Each task contains a chunk of URLs (max 100 for `actions`, max 1 for `local`/`all`/`test`) and a target database path.

---

### <a name="crawl-scrape"></a>Mode 2: Scrape

Scrapes a specific chunk of URLs and stores match data in a SQLite database.

```bash
python -m bet_crawler.crawl \
  --mode scrape \
  --matches_db_path actions-1.db \
  --urls "url1,url2,url3" \
  --config_dir ./config
```

**Parameters**:

*   `--matches_db_path`: Output database file (will be created/overwritten)
*   `--urls`: Comma-separated URLs **or** path to a `.txt` file containing URLs
*   `--config_dir`: Config directory

**Process**:
1.  Groups URLs by domain
2.  For each domain, instantiates the appropriate finder (from [`crawl.py`](bet_crawler/crawl.py:80-85))
3.  Scrapes each URL using the finder's `_parse_page()` method
4.  Applies skip patterns (youth teams, reserves, etc.) and date validation
5.  Stores normalized matches in the database

**Example with file input**:
```bash
python -m bet_crawler.crawl \
  --mode scrape \
  --matches_db_path local-1.db \
  --urls urls.txt \
  --config_dir ./config
```

---

### <a name="crawl-merge"></a>Mode 3: Merge

Combines all chunk databases into a single final database.

```bash
python -m bet_crawler.crawl \
  --mode merge \
  --matches_db_path final_matches.db \
  --chunks_dir ./chunks \
  --config_dir ./config
```

**Parameters**:

*   `--matches_db_path`: Path to the final merged database (will be created/overwritten)
*   `--chunks_dir`: Directory containing all chunk `.db` files
*   `--config_dir`: Config directory (for similarity settings)

**Process**:
1.  Creates a new database at `matches_db_path`
2.  Attaches each chunk database and copies all `matches` table rows
3.  Deduplicates based on match identity (home, away, datetime)
4.  Prints a summary:
```
  ==========================
    MERGE SUMMARY
  ==========================
  Unique Matches: 1247
  Chunks scanned: 5
    - vitibet: 312 matches
    - soccervista: 298 matches
    - whoscored: 201 matches
    ...
```

---

### <a name="crawl-generate"></a>Mode 4: Generate Slips

Builds betting slips from a matches database using a profile configuration.

```bash
python -m bet_crawler.crawl \
  --mode generate-slips \
  --matches_db_path final_matches.db \
  --slips_db_path slips.db \
  --profile_path ./config/profiles/low_risk.yaml
```

**Parameters**:

*   `--matches_db_path`: Input database with match data
*   `--slips_db_path`: Output database for slips (created if doesn't exist)
*   `--profile_path`: Path to a YAML profile file

**Profile YAML Structure** (see [`BetAssistant.py`](bet_framework/BetAssistant.py:287-326) for all options):
```yaml
# Example: low_risk.yaml
target_odds: 2.5
target_legs: 3
consensus_floor: 70
min_odds: 1.2
tolerance_factor: 0.2
stop_threshold: 0.95
min_legs_fill_ratio: 0.8
quality_vs_balance: 0.7
consensus_vs_sources: 0.6
included_markets:
  - 1
  - X
  - 2
units: 1.0
run_daily_count: 1  # Auto-generate once per day via Services
```

**Output**:
```
▶ Profile: LOW_RISK
  ⚽ Team A vs Team B (1) @ 1.85
  ⚽ Team C vs Team D (X) @ 2.10
  ⚽ Team E vs Team F (2) @ 1.65
  ✅ Slip #1 — 3 legs @ 6.42 (1.0u)
```

---

### <a name="crawl-validate"></a>Mode 5: Validate Slips

Scrapes current match results and updates the status of pending/live legs.

```bash
python -m bet_crawler.crawl \
  --mode validate-slips \
  --slips_db_path slips.db
```

**Parameters**:

*   `--slips_db_path`: Database containing slips to validate

**Process**:
1.  Fetches all legs with status `Pending` or `Live`
2.  Groups by unique `result_url`
3.  Scrapes each URL to extract current score and match status
4.  Updates leg outcomes:
    *   `FT` → Won/Lost based on market
    *   `LIVE` → Status set to Live, minute and score recorded
    *   `Pending` (not started) → No change

**Output**:
```
✅ Checked 47 · Settled 12 · Live 8 · Errors 0
  ✓ Team A vs Team B (1)  2:1  → Won
  ✗ Team C vs Team D (X)  0:0  → Lost
  ● Team E vs Team F (2)  1:0  (75')
```

---

## 🔧 4. How to Add a New Finder

Bet Assistant's modular crawler architecture makes it easy to add new data sources.

### Step 1: Create the Finder Class

Create a new file in [`bet_crawler/finders/`](bet_crawler/finders/) (e.g., `MyNewFinder.py`).

**Template**:
```python
from scrape_kit import get_logger
from bs4 import BeautifulSoup
from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

class MyNewFinder(BaseMatchFinder):
    # Set the timezone of the source (UTC, Europe/London, Asia/Bangkok, etc.)
    TIMEZONE = "UTC"  # or None if no normalization needed

    def get_matches_urls(self):
        """
        Fetch and return a list of match URLs to scrape.
        This is called during prepare-scrape mode.
        """
        # Example: Use browser for JS-rendered pages
        from scrape_kit import browser
        with browser(solve_cloudflare=True) as session:
            page = session.fetch("https://example.com/previews")
            soup = BeautifulSoup(page.html_content, "html.parser")

        urls = []
        for link in soup.select("a.match-link"):
            href = link.get("href")
            if href:
                urls.append(f"https://example.com{href}" if href.startswith("/") else href)

        logger.info(f"Found {len(urls)} matches")
        return urls

    def get_matches(self, urls):
        """
        Main entry point for scraping. Called during scrape mode.
        Typically delegates to scrape_urls() from scrape_kit.
        """
        from scrape_kit import scrape, ScrapeMode

        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,  # or BALANCED, THOROUGH
            max_concurrency=5,     # adjust based on source rate limits
        )

    def _parse_page(self, url, html):
        """
        Parse a single match page and extract data.
        Must call self.add_match(match) for each valid match.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 1. Extract team names
            home = soup.select_one(".home-team").text.strip()
            away = soup.select_one(".away-team").text.strip()

            # 2. Extract datetime
            # Use self.normalise_datetime() if needed (handles TIMEZONE)
            dt_str = soup.select_one(".match-time")["datetime"]
            dt = datetime.fromisoformat(dt_str)
            dt = self.normalise_datetime(dt)

            # 3. Extract predictions
            # Find consensus values and odds from the page
            # Example: home win odds = 2.10, consensus = 65%
            odds_home = float(soup.select_one(".odds-home").text)
            odds_draw = float(soup.select_one(".odds-draw").text)
            odds_away = float(soup.select_one(".odds-away").text)

            # 4. Build the Match object
            from bet_framework.core.Match import Match, Score

            scores = [
                Score(
                    source="mynewfinder",  # unique source identifier
                    home=str(int(65)),     # consensus home % as string
                    away=str(int(25)),     # consensus away % as string
                )
            ]

            # Optional: include bookmaker odds in the Match
            odds = {
                "home": odds_home,
                "draw": odds_draw,
                "away": odds_away,
            }

            match = Match(
                home_team=home,
                away_team=away,
                datetime=dt,
                predictions=scores,
                odds=odds,
                result_url=url  # important for validation later
            )

            # 5. Add to collection (applies skip patterns & date filters)
            self.add_match(match)

        except Exception as e:
            logger.error(f"Failed to parse {url}: {e}")
```

**Key Points**:

*   Inherit from [`BaseMatchFinder`](bet_crawler/finders/BaseMatchFinder.py)
*   Set `TIMEZONE` to the source's timezone (or `None` to skip normalization)
*   Implement `get_matches_urls()`, `get_matches()`, `_parse_page()`
*   In `_parse_page()`, create a [`Match`](bet_framework/core/Match.py) object and call `self.add_match(match)`
*   Use `Score` objects to represent predictions; `source` must be unique and lowercase
*   Include `result_url` in the Match for later validation

---

### Step 2: Register the Finder

Edit [`bet_crawler/crawl.py`](bet_crawler/crawl.py:39-52) and add your finder to the `_CRAWLER_KEYS` dictionary:

```python
_CRAWLER_KEYS = {
    "scorepredictor": lambda: _import("ScorePredictorFinder"),
    # ... existing entries ...
    "mynewfinder": lambda: _import("MyNewFinder"),  # ← Add this line
}
```

Then add it to one or more runner sets (lines 54–69):

```python
_RUNNER_SETS = {
    "actions": [
        "vitibet",
        # ... existing ...
        "mynewfinder",  # ← Add here to include in 'actions' set
    ],
    "local": ["whoscored", "forebet", "footballbettingtips"],
    "all": list(_CRAWLER_KEYS.keys()),
    "test": ["legitpredict"],
}
```

**Concurrency Note**: Adjust `MAX_CHUNK_SIZE` if your finder needs special chunking (line 71).

---

### Step 3: Test Your Finder

```bash
# Test in isolation
python -m bet_crawler.crawl \
  --mode prepare-scrape \
  --runners test \
  --config_dir ./config

# Or test directly
python -c "
from bet_crawler.finders.MyNewFinder import MyNewFinder
f = MyNewFinder(print)
urls = f.get_matches_urls()
print(f'Found {len(urls)} URLs')
f.get_matches(urls[:3])  # test first 3
"
```

Check the logs for errors and verify that matches appear in the database.

---

### Step 4: Handle Skip Patterns (Optional)

If your source includes youth teams, women's teams, or reserve sides, extend the `SKIP_PATTERNS` list in [`BaseMatchFinder.py`](bet_crawler/finders/BaseMatchFinder.py:11-21):

```python
SKIP_PATTERNS: list[tuple[str, str]] = [
    (r"\bU\d{2}s?\b", "Youth team"),
    (r"\bW\b", "Women's team"),
    (r"\bII\b", "Reserve team II"),
    # Add custom patterns for your source
    (r"\bB Team\b", "B team"),
    (r"\bU23\b", "U23 team"),
]
```

---

### Step 5: Verify Integration

Run the full pipeline:

```bash
# 1. Collect URLs
python -m bet_crawler.crawl --mode prepare-scrape --runners all --config_dir ./config > tasks.json

# 2. Scrape chunks (example: first task)
python -m bet_crawler.crawl --mode scrape --matches_db_path chunk-1.db \
  --urls "$(jq -r '.[0].urls' tasks.json)" --config_dir ./config

# 3. Merge
python -m bet_crawler.crawl --mode merge --matches_db_path final.db \
  --chunks_dir ./ --config_dir ./config

# 4. Generate a test slip
python -m bet_crawler.crawl --mode generate-slips \
  --matches_db_path final.db --slips_db_path test.db \
  --profile_path ./config/profiles/medium_risk.yaml

# 5. Validate
python -m bet_crawler.crawl --mode validate-slips --slips_db_path test.db
```

If all steps succeed, your finder is ready for production use.

---

## 📁 Project Structure

```
bet-assistant/
├── bet_crawler/              # CLI crawler module
│   ├── crawl.py              # Main entry point with all modes
│   └── finders/              # Individual source crawlers
│       ├── BaseMatchFinder.py
│       ├── WhoScoredFinder.py
│       ├── ForebetFinder.py
│       └── ...
├── bet_dashboard/            # Web UI (React + FastAPI)
│   ├── frontend/             # React + TypeScript + Vite
│   │   └── src/
│   │       ├── pages/        # Dashboard tabs
│   │       ├── components/   # Reusable UI components
│   │       └── api/          # Backend API client
│   └── backend/              # FastAPI server
│       ├── main.py
│       └── routers/          # API endpoints
├── bet_framework/            # Core logic library
│   ├── BetAssistant.py       # Slip building & validation
│   ├── MatchesManager.py     # SQLite buffer for matches
│   └── core/
│       ├── Match.py          # Match data model
│       ├── Slip.py           # Slip data model
│       ├── scoring.py        # Pick scoring algorithm
│       └── consensus.py      # Consensus calculation
├── config/
│   ├── scraper_config.yaml   # Retry/block indicators
│   ├── similarity_config.yaml # Team name matching rules
│   └── profiles/             # YAML profiles for Smart Builder
├── setup/
│   ├── compose.yaml          # Docker Compose stack
│   └── requirements-*.txt    # Python dependencies
├── workspace/                # Created on first Docker run
│   ├── config/               # Copied from /app/config/
│   └── data/                 # SQLite databases
└── tests/                    # Unit & integration tests
```

---

## 🧠 Understanding the Scoring Model

The Smart Builder's selection algorithm is based on three normalized axes:

### 1. Consensus Score
```
Linear mapping: consensus_floor → 100% = 1.0
```
Higher agreement across sources yields a higher score.

### 2. Sources Score
```
0 sources → 0.0
max_sources_in_pool → 1.0
```
More independent providers covering a match increases confidence.

### 3. Balance Score
```
ideal_odds = (target_odds) ^ (1 / target_legs)
tolerance_band = ideal_odds ± (tolerance_factor × ideal_odds)

Within band: 1.0 (perfect)
At band edge: 0.0
Outside band: 0.0 (Tier 2)
```
Measures how close the pick's odds are to the ideal per-leg odds needed to reach the target.

### Combined Formula

```
quality = consensus_vs_sources × consensus_score + (1 − consensus_vs_sources) × sources_score
final   = quality_vs_balance × quality + (1 − quality_vs_balance) × balance_score
```

**Tier System**:
*   **Tier 1**: Balance score > 0 (within tolerance). Always ranked above Tier 2.
*   **Tier 2**: Balance score = 0 (outside tolerance). Used only if insufficient Tier 1 options.

---

## 🔍 Troubleshooting

### No matches appearing in the dashboard

1.  Check that the backend container is healthy:
    ```bash
    docker compose -f setup/compose.yaml ps
    ```
2.  View backend logs for errors:
    ```bash
    docker compose -f setup/compose.yaml logs backend
    ```
3.  Verify that the `workspace/data/matches.db` file exists and contains data:
    ```bash
    sqlite3 workspace/data/matches.db "SELECT COUNT(*) FROM matches;"
    ```
4.  Ensure at least one finder is enabled in the Services tab.

### Smart Builder returns "No matches meet the current criteria"

1.  Lower the **Consensus Floor** (try 40–50%)
2.  Lower the **Min Odds** (try 1.01)
3.  Check the **Excluded Matches** section — you may have manually excluded too many
4.  Verify that the global date filters (top bar) are not restricting the date range too much
5.  Ensure matches exist in the database for the selected date range

### Docker containers keep restarting

Check the logs:
```bash
docker compose -f setup/compose.yaml logs
```

Common issues:
*   Port 3002 or 8000 already in use → change ports in `compose.yaml`
*   Permission errors on `./workspace/` → ensure the directory is writable

### Finders are not collecting URLs

1.  Verify the finder's `get_matches_urls()` method works (test in isolation)
2.  Check for Cloudflare blocks — some sources require `solve_cloudflare=True`
3.  Review `scraper_config.yaml` for custom retry/block indicators
4.  Ensure the finder is registered in `crawl.py` and enabled in Services

### Validation fails to update leg status

1.  Confirm `result_url` is stored correctly in the `legs` table:
    ```bash
    sqlite3 workspace/data/slips.db "SELECT result_url FROM legs LIMIT 3;"
    ```
2.  Test scraping the URL manually:
    ```bash
    curl -s "https://example.com/match" | grep -i "score\|status"
    ```
3.  Check that the parser in `_parse_match_result_html()` (BetAssistant.py:91) can handle the source's HTML structure. Some sites may need custom parsing logic.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
