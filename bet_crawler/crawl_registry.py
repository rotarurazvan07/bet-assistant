"""
crawl_registry.py — Shared crawler registry and utility functions
────────────────────────────────────────────────────────────────
This module contains the crawler registry and related functions that are
used by both the main crawl.py and the crawl_core mode modules.
"""

from scrape_kit import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Crawler registry
# ─────────────────────────────────────────────────────────────────────────────

_CRAWLER_KEYS = {
    "scorepredictor": {"class": lambda: _import("ScorePredictorFinder"), "contributes_odds": True},
    "soccervista": {"class": lambda: _import("SoccerVistaFinder_per_league"), "contributes_odds": True},
    "whoscored": {"class": lambda: _import("WhoScoredFinder"), "contributes_odds": True},
    "windrawwin": {"class": lambda: _import("WinDrawWinFinder_per_league"), "contributes_odds": True},
    "forebet": {"class": lambda: _import("ForebetFinder"), "contributes_odds": True},
    "vitibet": {"class": lambda: _import("VitibetFinder"), "contributes_odds": True},
    "predictz": {"class": lambda: _import("PredictzFinder"), "contributes_odds": True},
    "onemillionpredictions": {"class": lambda: _import("OneMillionPredictionsFinder"), "contributes_odds": True},
    "footballbettingtips": {"class": lambda: _import("FootballBettingTipsFinder"), "contributes_odds": True},
    "xgscore": {"class": lambda: _import("xGScoreFinder"), "contributes_odds": True},
    "eaglepredict": {"class": lambda: _import("EaglePredictFinder"), "contributes_odds": True},
    "legitpredict": {"class": lambda: _import("LegitPredictFinder"), "contributes_odds": True},
    "betclan": {"class": lambda: _import("BetClanFinder"), "contributes_odds": True},
    "oddsportal": {"class": lambda: _import("OddsPortalFinder"), "contributes_odds": True},
    "betexplorer": {"class": lambda: _import("BetExplorerFinder"), "contributes_odds": True},
}

_RUNNER_SETS = {
    "actions": [
        "vitibet",
        "scorepredictor",
        "predictz",
        "soccervista",
        "windrawwin",
        "onemillionpredictions",
        "xgscore",
        "eaglepredict",
        "legitpredict",
        "betclan",
        "oddsportal",
        "forebet",
    ],
    "local": [
        "whoscored",
        "footballbettingtips",
        "betexplorer",
    ],
    "all": list(_CRAWLER_KEYS.keys()),
    "test": ["forebet"],
}

MAX_CHUNK_SIZE = {"actions": 100, "local": 1, "all": 1, "test": 1}


def _import(cls: str):
    from bet_crawler import finders

    return getattr(finders, cls)


def get_crawler_class(url: str, on_match_callback=None):
    lower = url.lower()
    for key, loader in _CRAWLER_KEYS.items():
        if key in lower:
            return loader["class"]()(on_match_callback), loader["contributes_odds"]
    raise ValueError(f"No crawler registered for URL: {url}")


def get_runner_classes(runner: str) -> list:
    keys = _RUNNER_SETS.get(runner, [])
    return [_CRAWLER_KEYS[k]["class"]() for k in keys]
