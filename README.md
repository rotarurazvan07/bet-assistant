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

> [!NOTE]
> This section is currently under construction. Implementation details, API documentation, and contribution guidelines will be added soon.

---

## 📜 License
Distrubuted under the MIT License. See `LICENSE` for more information.
