# 🎯 Bet Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)

A powerful, 24/7 automated betting intelligence platform. **Bet Assistant** crawls multiple sources, aggregates consensus data, calculates value pips, and manages your betting slips through a premium Dash dashboard.

---

## 🚀 Key Features

*   **Multi-Source Aggragation**: Intelligent crawlers for WhoScored, Forebet, SoccerVista, and more.
*   **Consensus Engine**: Calculates betting "Consensus" based on agreement across providers.
*   **Smart Slip Builder**: Dynamic generator that builds slips based on risk profiles (Low, Medium, High).
*   **Real-time Analytics**: Track your success rate, market accuracy, and ROI over time.
*   **24/7 Service Architecture**: Designed to run on a Raspberry Pi or server with automated daily updates.
*   **Premium Web UI**: High-performance dashboard with glassmorphism aesthetics and live status monitoring.

---

## 📖 User Guide

### 🐳 1. Docker Setup (Recommended)
The easiest way to get started is using Docker Compose. This ensures all dependencies and background services are configured correctly.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/rotarurazvan07/bet-assistant.git
    cd bet-assistant
    ```

2.  **Launch**:
    ```bash
    docker compose -f setup/compose.yaml up -d
    ```
    The dashboard will be available at `http://localhost:8050`.

---

### 🛠️ 2. Manual Installation

If you prefer to run locally on Windows, Linux, or a Raspberry Pi:

1.  **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/Pi
    .\venv\Scripts\activate   # Windows
    ```

2.  **Install Requirements**:
    ```bash
    pip install -r setup/requirements-dashboard.txt
    pip install -r setup/requirements-scrape.txt
    scrapling install
    ```

---

### 🏃 3. Usage & Operations

Copy all yamls of config folder to your project config folder. These can be finetuned, the ones in the repo are whats used in actions. When setuping the dashboard, you need to copy those configs to where your workspace will be.

#### **A. Collecting Match Data**
First, generate a list of target URLs:
```bash
python -m main --mode prepare-scrape --runners all --config_path .\config\ > urls.txt
```
Then, scrape the data into your database:
```bash
python -m main --mode scrape --matches_db_path final_matches.db --urls urls.txt --config_path .\config\
```

#### **B. Launching the Dashboard**
Run the dashboard in production mode for 24/7 stability:
```bash
python -m dashboard.app --matches_db_path final_matches.db --slips_db_path slips.db --config_path config --no-debug
```

#### **C. Configuration**
*   **Profiles**: Define your betting strategy in `config/profiles/*.yaml`.
*   **Services**: Tune the auto-pull and auto-generate hours via the **Services** tab in the Dashboard.

---

## 🏗️ Developer Guide

Bet Assistant is built with a modular architecture that separates data collection, persistence, and intelligence.

### 📁 Project Structure
- `bet_framework/`: The engine room of the application.
  - `BetAssistant.py`: Core logic for slip building, scoring picks, and result validation.
  - `MatchesManager.py`: Thread-safe SQLite buffer for match data.
  - `WebScraper.py`: Stealthy scraper with Cloudflare bypass (leveraging Scrapling).
  - `SimilarityEngine.py`: Hybrid matching for team names across different providers.
- `dashboard/`: Premium Dash-based user interface.
- `runners/`: Modular crawler implementations for various sports data providers.

### 🧠 Intelligence Model (Consensus)
The system doesn't rely on a single source. Instead, it calculates a **Consensus Percentage** across multiple providers:
- **Consensus**: (Agreement Count / Total Sources) * 100.
- **Scoring**: Every pick is assigned a `Final Score` based on consensus, number of sources, and its proximity to the target odds (Balance).

### 🛠️ Adding a New Crawler
To add a provider, create a new script in `runners/` that implements:
1. `prepare()`: Fetches a list of match URLs.
2. `parse_page()`: Scrapes match details, predictions, and bookmaker odds.
3. Registration in `main.py` under the `--runners` argument.

### 🧪 Quality Standards
We use `desloppify` to maintain high code quality (baseline score 95%+). All core framework modules include unit tests within the `tests/` directory to prevent regressions in the similarity or scoring engines.

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
