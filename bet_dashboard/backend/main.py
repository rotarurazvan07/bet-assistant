"""
Bet Assistant — FastAPI Backend
===============================
Run from bet_dashboard/backend/:

    export MATCHES_DB_PATH=../../final_matches.db
    export SLIPS_DB_PATH=../../slips.db
    export CONFIG_PATH=../../config
    uvicorn main:app --reload --port 8000

Or using Docker Compose (recommended):

    docker compose -f setup/compose.yaml up -d
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add the backend directory to Python path so 'core' and 'routers' can be imported
# when running from the backend directory or via uvicorn main:app
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.logic import AppLogic  # noqa: E402
from core.ws import ws_manager  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from routers import analytics, builder, matches, profiles, services, slips, system  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hand the running event loop to ws_manager so TickerService daemon threads
    # can call broadcast_sync() safely via run_coroutine_threadsafe.
    ws_manager.set_loop(asyncio.get_event_loop())
    yield
    # TickerService threads are daemons — they die with the process automatically.


def create_app() -> FastAPI:
    matches_db = os.getenv("MATCHES_DB_PATH", "bet_dashboard/workspace/data/final_matches.db")
    slips_db = os.getenv("SLIPS_DB_PATH", "bet_dashboard/workspace/data/slips.db")
    config_dir = os.getenv("CONFIG_PATH", "bet_dashboard/workspace/config")

    app = FastAPI(
        title="Bet Assistant API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Single shared logic instance — owns DashboardLogic + TickerServices
    app.state.app_logic = AppLogic(matches_db, slips_db, config_dir)

    for router in [
        matches.router,
        builder.router,
        profiles.router,
        slips.router,
        analytics.router,
        services.router,
        system.router,
    ]:
        app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
