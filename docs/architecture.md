# System Architecture

## Overview

Bet Assistant is a **monorepo** containing four distinct but integrated parts:

| Part | Technology | Purpose |
|------|------------|---------|
| **Frontend** | React 19 + TypeScript + Vite | Premium betting dashboard UI |
| **Backend** | Python 3.11 + FastAPI | REST API + WebSocket real-time server |
| **Crawler** | Python + scrape-kit | ETL pipeline for match data aggregation |
| **Infrastructure** | Docker + GitHub Actions | Container orchestration + CI/CD |

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "External Data Sources"
        DS1[WhoScored]
        DS2[Forebet]
        DS3[SoccerVista]
        DS4[Vitibet]
        DS5[ScorePredictor]
        DS6[Predictz]
        DS7[WinDrawWin]
        DS8[OneMillionPredictions]
        DS9[xGScore]
        DS10[EaglePredict]
        DS11[LegitPredict]
        DS12[... 6 more sources]
    end

    subgraph "Crawler Pipeline (GitHub Actions)"
        PS[prepare-scrape
        Collect URLs]
        SC[scrape
        Parallel chunks]
        MR[merge
        Fuzzy dedup]
        ODDS[odds-scrape
        Optional enrichment]
    end

    subgraph "Data Layer"
        MDB[(matches.db
        SQLite + odds history)]
        SDB[(slips.db
        SQLite + slip storage)]
        CFG[config/
        YAML profiles]
    end

    subgraph "Docker Compose Stack"
        NG[Nginx :80
        Static + Reverse Proxy]
        API[FastAPI :8000
        REST + WebSocket]
        UI[React 19 + Vite
        MUI v9 + Tailwind]
        GR[Self-hosted Runner
        GitHub Actions]
        WT[Watchtower
        Auto-update]
    end

    subgraph "Frontend Pages"
        BT[Betting Tips
        Match table + filters]
        SB[Smart Builder
        Profile config + preview]
        SL[Slips
        History + validation]
        AN[Analytics
        Charts + metrics]
        SV[Services
        Crawler management]
    end

    DS1 --> PS
    DS2 --> PS
    DS3 --> PS
    DS4 --> PS
    DS5 --> PS
    DS6 --> PS
    DS7 --> PS
    DS8 --> PS
    DS9 --> PS
    DS10 --> PS
    DS11 --> PS
    DS12 --> PS
    
    PS --> SC
    SC --> MR
    MR --> MDB
    MDB --> ODDS
    ODDS --> MDB
    
    MDB --> API
    SDB --> API
    CFG --> API
    
    API --> NG
    UI --> NG
    UI --> API
    
    NG --> UI
    NG --> API
    
    GR --> API
    WT --> NG
    WT --> GR
    
    UI --> BT
    UI --> SB
    UI --> SL
    UI --> AN
    UI --> SV
```

---

## Data Flow Architecture

### 1. Crawler Pipeline (Daily Automated)

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant PS as prepare-scrape
    participant SC as scrape (parallel)
    participant MR as merge
    participant MDB as matches.db
    participant API as FastAPI Backend
    participant UI as React Frontend
    
    GH->>PS: Trigger (cron 0 */1 * * *)
    PS->>PS: Collect URLs from 18+ finders
    PS->>SC: Split into chunks (max 100 URLs)
    par Parallel Scraping
        SC->>DS1: Scrape WhoScored
        SC->>DS2: Scrape Forebet
        SC->>DS3: Scrape SoccerVista
        SC->>DS4: Scrape Vitibet
        SC->>DS5: Scrape ScorePredictor
        SC->>DS6: Scrape Predictz
        SC->>DS7: Scrape WinDrawWin
        SC->>DS8: Scrape 1M Predictions
        SC->>DS9: Scrape xGScore
        SC->>DS10: Scrape EaglePredict
        SC->>DS11: Scrape LegitPredict
    end
    SC->>MR: Chunk DBs (actions-1.db, local-1.db, etc.)
    MR->>MR: Fuzzy deduplication (home/away/datetime)
    MR->>MDB: Write final_matches.db
    MR->>GH: Upload as release artifact
    GH->>API: bet-updater pulls new image
    API->>MDB: Download latest DB on startup
    API->>UI: WebSocket broadcast matches_updated
    UI->>UI: Refetch matches table
```

### 2. Slip Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as React Dashboard
    participant API as FastAPI
    participant BA as BetAssistant
    participant SDB as slips.db
    
    User->>UI: Configure Smart Builder profile
    UI->>API: POST /api/builder/preview
    API->>BA: build_preview(config)
    BA->>BA: Score all candidate picks
    BA->>BA: Select legs (Tier 1 first)
    BA-->>API: CandidateLeg[] + total_odds
    API-->>UI: PreviewResult
    UI->>User: Show live preview
    
    User->>UI: Click + Add to Slips
    UI->>API: POST /api/slips {profile, legs, units}
    API->>BA: save_slip(profile, legs, units)
    BA->>SDB: INSERT slip + legs
    BA-->>API: slip_id
    API-->>UI: {slip_id}
    UI->>UI: Broadcast slips_updated via WS
    UI->>User: Slip appears in Slips tab
```

### 3. Real-time Validation Flow

```mermaid
sequenceDiagram
    participant VS as validate-slips (cron)
    participant BA as BetAssistant
    participant SDB as slips.db
    participant WS as WebSocket
    participant UI as React Dashboard
    
    loop Every 60 seconds (Verifier service)
        VS->>BA: validate_slips()
        BA->>SDB: SELECT pending/live legs
        BA->>BA: Group by result_url
        par Parallel result scraping
            BA->>DS1: Scrape match result
            BA->>DS2: Scrape match result
        end
        BA->>BA: determine_outcome(score, market)
        BA->>SDB: UPDATE leg status (Won/Lost/Live)
        BA->>SDB: UPDATE slip_status (Won/Lost/Live/Pending)
        BA-->>VS: ValidationReport
        BA->>WS: broadcast_sync(slips_updated + live_data)
        WS->>UI: Receive event
        UI->>UI: Refetch slips + analytics
    end
```

---

## Component Architecture

### Frontend (React 19 + TypeScript)

```mermaid
graph TD
    App[App.tsx
    BrowserRouter + WS Provider]
    
    Layout[Layout.tsx
    Global filters + Tab navigation]
    
    Pages[Pages/]
    BT[BettingTips.tsx
    Match table + slip builder]
    SB[SmartBuilder.tsx
    Config panel + preview]
    SL[Slips.tsx
    Slip cards + filters]
    AN[Analytics.tsx
    Charts + metrics]
    SV[Services.tsx
    Service cards + schedule]
    
    Components[Components/]
    UI[ui.tsx
    Base components: Tooltip, Toggle, Badge, Card]
    MR[MatchRow.tsx
    Clickable market cells]
    FP[FloatingSlipBuilder.tsx
    Side panel with legs]
    BP[BuilderPanel.tsx
    Smart Builder config]
    AD[AnalyticsDashboard.tsx
    Chart containers]
    SC[ServiceCard.tsx
    Toggle + status]
    
    Hooks[Hooks/]
    US[useSocket.ts
    WS connection + reconnect]
    UP[useProfileSelection.ts
    Profile state management]
    
    API[API/]
    CL[client.ts
    Axios instance]
    DT[data.ts
    Builder, profiles, slips, analytics]
    MT[matches.ts
    Match fetching]
    OH[oddsHistory.ts
    Movement data]
    
    Config[Config/]
    MC[marketConfig.ts
    Market columns + types]
    
    Types[Types/]
    IDX[index.ts
    All TypeScript interfaces]
    
    Utils[Utils/]
    BU[betUtils.ts
    Formatting helpers]
    CU[calculationUtils.ts
    Math helpers]
    TU[teamUtils.ts
    Team name normalization]
    
    App --> Layout
    Layout --> Pages
    Pages --> BT
    Pages --> SB
    Pages --> SL
    Pages --> AN
    Pages --> SV
    
    BT --> Components
    SB --> Components
    SL --> Components
    AN --> Components
    SV --> Components
    
    Components --> UI
    Components --> MR
    Components --> FP
    Components --> BP
    Components --> AD
    Components --> SC
    
    BT --> Hooks
    SB --> Hooks
    SL --> Hooks
    AN --> Hooks
    SV --> Hooks
    
    Hooks --> US
    Hooks --> UP
    
    BT --> API
    SB --> API
    SL --> API
    AN --> API
    SV --> API
    
    API --> CL
    API --> DT
    API --> MT
    API --> OH
    
    SB --> Config
    BT --> Config
    
    All --> Types
    All --> Utils
```

### Backend (FastAPI + Python)

```mermaid
graph TD
    Main[main.py
    create_app() + lifespan]
    
    Routers[Routers/ 8 endpoints]
    MT[matches.py
    GET /api/matches]
    BL[builder.py
    POST /api/builder/preview
    GET /api/builder/excluded
    GET /api/builder/leagues]
    PR[profiles.py
    CRUD /api/profiles]
    SP[slips.py
    CRUD /api/slips
    POST /validate
    POST /generate]
    SV[services.py
    GET /api/services
    POST /settings
    POST /toggle]
    AN[analytics.py
    GET /api/analytics]
    OH[odds_history.py
    GET /api/odds-history]
    SY[system.py
    POST /api/pull
    GET /api/status
    WS /ws]
    
    Core[Core modules]
    LG[logic.py
    AppLogic - unified business logic
    TickerService orchestration]
    TS[ticker_service.py
    Daemon thread polling
    Predicate-based execution]
    WS[ws.py
    ConnectionManager
    Thread-safe broadcast]
    MC[market_config.py
    MarketDef + constants]
    SC[schemas.py
    Pydantic request/response]
    AU[analytics_utils.py
    Statistics calculations]
    CH[config_helpers.py
    Profile YAML conversion]
    
    Framework[bet_framework/]
    BA[BetAssistant.py
    Slip building + validation + storage]
    MM[MatchesManager.py
    Buffered SQLite + fuzzy dedup]
    CoreF[core/
    Match, Slip, Consensus, Scoring, Outcomes]
    
    Main --> Routers
    Routers --> MT
    Routers --> BL
    Routers --> PR
    Routers --> SP
    Routers --> SV
    Routers --> AN
    Routers --> OH
    Routers --> SY
    
    Main --> Core
    Core --> LG
    Core --> TS
    Core --> WS
    Core --> MC
    Core --> SC
    Core --> AU
    Core --> CH
    
    LG --> Framework
    LG --> BA
    LG --> MM
    BA --> CoreF
    MM --> CoreF
```

### Crawler (ETL Pipeline)

```mermaid
graph TD
    Crawl[crawl.py
    CLI entry + CrawlerFactory]
    
    Finders[Finders/ 18+ classes]
    BF[BaseMatchFinder
    Abstract base + datetime norm + skip patterns]
    WS[WhoScoredFinder
    Browser + JSON parsing]
    FB[ForebetFinder
    STEALTH mode + 100+ leagues]
    SV[SoccerVistaFinder
    Per league + per match]
    VT[VitibetFinder]
    SP[ScorePredictorFinder]
    PZ[PredictzFinder]
    WD[WinDrawWinFinder]
    OM[OneMillionPredictionsFinder]
    XG[xGScoreFinder]
    EP[EaglePredictFinder]
    LP[LegitPredictFinder]
    OP[OddsPortalFinder]
    BE[BetExplorerFinder]
    BT[BetClanFinder]
    FB2[FootballBettingTipsFinder]
    FP2[FootballPredictionsFinder]
    
    Core[Crawl Core/]
    PS[prepare_scrape.py
    URL collection + chunking]
    SC[scrape.py
    Domain grouping + parallel scrape]
    MR[merge.py
    Fuzzy dedup + validation]
    GS[generate_slips.py
    Profile-based slip building]
    VS[validate_slips.py
    Result scraping + settlement]
    
    Storage[Storage]
    SM[MatchesManager
    BufferedStorageManager
    SimilarityEngine]
    BA[BetAssistant
    BaseStorageManager
    Slip persistence]
    
    Crawl --> Finders
    Crawl --> Core
    
    Finders --> BF
    Finders --> WS
    Finders --> FB
    Finders --> SV
    Finders --> VT
    Finders --> SP
    Finders --> PZ
    Finders --> WD
    Finders --> OM
    Finders --> XG
    Finders --> EP
    Finders --> LP
    Finders --> OP
    Finders --> BE
    Finders --> BT
    Finders --> FB2
    Finders --> FP2
    
    Core --> PS
    Core --> SC
    Core --> MR
    Core --> GS
    Core --> VS
    
    PS --> Finders
    SC --> Finders
    SC --> Storage
    MR --> Storage
    GS --> Storage
    GS --> Framework
    VS --> Framework
    
    Storage --> SM
    Storage --> BA
    Framework --> BA
```

---

## Integration Architecture

### Multi-Part Communication

```mermaid
graph LR
    subgraph "Frontend (React)"
        UI[UI Components]
        HK[useSocket Hook
        WebSocket Client]
        AX[Axios Client
        REST API]
    end

    subgraph "Backend (FastAPI)"
        WS[WebSocket Server
        /ws endpoint]
        RS[REST API
        8 routers]
        AL[AppLogic
        Business Logic]
        TS[TickerServices
        3 daemon threads]
    end

    subgraph "Data Layer"
        MDB[(matches.db
        SQLite)]
        SDB[(slips.db
        SQLite)]
        CFG[config/
        YAML files]
    end

    subgraph "External"
        GH[GitHub Releases
        final_matches.db]
        CR[Crawler Pipeline
        GitHub Actions]
    end

    UI --> HK
    UI --> AX
    HK --> WS
    AX --> RS
    WS --> AL
    RS --> AL
    AL --> MDB
    AL --> SDB
    AL --> CFG
    AL --> TS
    TS --> AL
    TS --> WS
    TS --> AX
    CR --> GH
    GH --> AL
    AL --> GH
```

### Service Communication Matrix

| From | To | Protocol | Purpose |
|------|-----|----------|---------|
| Frontend | Backend | WebSocket | Real-time updates (matches, slips, services) |
| Frontend | Backend | REST (HTTPS) | CRUD operations, previews, analytics |
| Backend | SQLite | SQL | Match/slip data persistence |
| Backend | Config | File I/O | Profile/settings management |
| TickerServices | Backend | In-process | Polling predicates + callbacks |
| GitHub Actions | Backend | HTTP (Release API) | Database distribution |
| Watchtower | Docker | Docker API | Container auto-updates |
| Self-hosted Runner | GitHub | HTTPS | CI/CD job execution |

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "CI/CD Pipeline"
        GH1[scrape.yml
        Daily scraping]
        GH2[deploy.yml
        Build & push images]
        GH3[cicd.yml
        Auto-fix + Test + Audit]
    end

    subgraph "Container Registry"
        REG[ghcr.io/rotarurazvan07/
        bet-assistant:latest
        bet-assistant-runner:latest]
    end

    subgraph "Production Host"
        DC[Docker Compose
        setup/compose.yaml]
        
        BA[bet-assistant
        Nginx + FastAPI + React]
        GR[runner
        Self-hosted GH runner]
        WT[bet-updater
        Watchtower]
        
        WS[workspace/
        config/ + data/]
    end

    GH1 --> REG
    GH2 --> REG
    GH3 --> REG
    
    REG --> DC
    DC --> BA
    DC --> GR
    DC --> WT
    
    BA --> WS
    GR --> WS
    WT --> BA
    WT --> GR
    
    BA -.->|Healthcheck| BA
    GR -.->|Labels| WT
```

### Docker Multi-Stage Build

```mermaid
graph TD
    subgraph "Stage 1: Frontend Builder"
        FB[FROM node:22-alpine
        WORKDIR /app
        COPY package*.json .
        RUN npm ci
        COPY . .
        RUN npm run build
        OUTPUT: /app/dist]
    end

    subgraph "Stage 2: Python Dependencies"
        PD[FROM python:3.11-slim
        COPY requirements.txt .
        RUN pip install --prefix=/install -r requirements.txt
        OUTPUT: /install]
    end

    subgraph "Stage 3: Runtime"
        RT[FROM python:3.11-slim
        WORKDIR /app
        COPY --from=PD /install /usr/local
        RUN scrapling install
        COPY bet_framework/ ./bet_framework/
        COPY bet_dashboard/backend/ .
        COPY config/ config/
        COPY --from=FB /app/dist /usr/share/nginx/html
        COPY nginx.conf /etc/nginx/sites-available/default
        COPY start-dashboard.sh /usr/local/bin/
        EXPOSE 80
        CMD ["/usr/local/bin/start-dashboard.sh"]]
    end

    FB --> RT
    PD --> RT
```

---

## Security Architecture

```mermaid
graph TD
    subgraph "Network Security"
        NG[Nginx Reverse Proxy
        Rate limiting + SSL termination]
        CORS[CORS Middleware
        Allowlisted origins]
        HOST[HOST env var
        Default 127.0.0.1]
    end

    subgraph "Application Security"
        VAL[Pydantic v2
        Request validation]
        URLV[URL Validation
        is_valid_url()]
        SCHEME[URL Scheme Check
        HTTPS only for downloads]
        TEMP[Temp File Cleanup
        Best-effort unlink]
    end

    subgraph "Infrastructure Security"
        GH_TOKEN[GITHUB_TOKEN
        Least privilege]
        RUNNER[Self-hosted runners
        Isolated network]
        WATCH[Watchtower
        Label-scoped updates]
        HEALTH[Health Checks
        HTTP endpoint polling]
    end

    subgraph "CI/CD Security"
        AUDIT[Security Audit
        bandit + semgrep + pip-audit]
        TYPE[Type Checking
        mypy strict mode]
        DEPS[Dependency Scanning
        pip-audit CVE check]
        COMPLEX[Complexity Analysis
        radon CC + MI]
    end

    NG --> CORS
    NG --> HOST
    CORS --> VAL
    VAL --> URLV
    URLV --> SCHEME
    SCHEME --> TEMP
    
    GH_TOKEN --> RUNNER
    RUNNER --> WATCH
    WATCH --> HEALTH
    
    AUDIT --> TYPE
    TYPE --> DEPS
    DEPS --> COMPLEX
```

---

## Scalability Considerations

| Component | Current Scale | Scaling Strategy |
|-----------|---------------|------------------|
| **Frontend** | Single container | CDN for static assets, multiple replicas behind load balancer |
| **Backend** | Single container + daemon threads | Horizontal scaling with Redis for WebSocket pub/sub, shared SQLite → PostgreSQL |
| **Crawler** | GitHub Actions parallel jobs | Increase runner count, chunk size tuning, dedicated scraping infrastructure |
| **Database** | SQLite (file-based) | Migrate to PostgreSQL with connection pooling, read replicas |
| **WebSocket** | In-memory connection manager | Redis adapter for multi-instance broadcasting |
| **Scheduler** | Daemon threads (3 services) | External scheduler (Celery Beat, cron) for distributed deployment |

---

## Technology Decisions

| Decision | Rationale |
|----------|-----------|
| **React 19 + Vite** | Modern React with concurrent features, fast HMR, optimized builds |
| **FastAPI** | Async-native, automatic OpenAPI docs, Pydantic integration, high performance |
| **SQLite** | Zero-config, file-based, perfect for single-host deployment, embedded odds history |
| **Docker Multi-stage** | Small production images (~500MB), build-time dependency isolation |
| **GitHub Actions + Self-hosted** | Free CI/CD minutes, control over scraping environment, IP rotation |
| **Watchtower** | Zero-downtime auto-updates, label-scoped to bet-stack only |
| **scrape-kit** | Unified scraping framework with browser automation, Cloudflare solving |
| **MUI v9 + Tailwind** | Component library + utility CSS, glassmorphism design system |
| **Recharts** | React-native charting, declarative API, responsive |
| **Pydantic v2** | Fast validation, serialization, OpenAPI schema generation |

---

## Failure Modes & Mitigations

| Failure Mode | Detection | Mitigation |
|--------------|-----------|------------|
| **Crawler blocked by Cloudflare** | 0 URLs collected, scraper logs | `solve_cloudflare=True` in browser, rotate IPs via self-hosted runners |
| **Database corruption** | Healthcheck fails, SQLite errors | WAL mode, atomic writes, backup on merge |
| **WebSocket connection loss** | Frontend reconnect logic (3s delay) | Exponential backoff, ping interval (25s) |
| **Docker image pull fails** | Watchtower logs, container restart loop | Retry with backoff, fallback to previous image |
| **GitHub Actions runner offline** | Workflow failure, runner status | Multiple runner replicas, health monitoring |
| **Odds validation errors** | Implied probability > 120% | Market group validation, reject invalid odds |
| **Fuzzy match false positives** | Near-miss report (40-65 score) | Similarity config tuning, manual review |
