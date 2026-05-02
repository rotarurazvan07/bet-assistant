"""
crawl_registry.py — Shared crawler registry and utility functions
────────────────────────────────────────────────────────────────
This module contains the crawler registry and related functions that are
used by both the main crawl.py and the crawl_core mode modules.
"""

import os
import random
import sys
from collections import defaultdict
from contextlib import redirect_stdout
from urllib.parse import urlparse

import pandas as pd
from scrape_kit import SettingsManager, configure, get_logger
from bet_framework.MatchesManager import MatchesManager

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Crawler registry
# ─────────────────────────────────────────────────────────────────────────────

_CRAWLER_KEYS = {
    "scorepredictor": lambda: _import("ScorePredictorFinder"),
    "soccervista": lambda: _import("SoccerVistaFinder_per_match"),
    "whoscored": lambda: _import("WhoScoredFinder"),
    "windrawwin": lambda: _import("WinDrawWinFinder_per_league"),
    "forebet": lambda: _import("ForebetFinder"),
    "vitibet": lambda: _import("VitibetFinder"),
    "predictz": lambda: _import("PredictzFinder"),
    "onemillionpredictions": lambda: _import("OneMillionPredictionsFinder"),
    "footballbettingtips": lambda: _import("FootballBettingTipsFinder"),
    "xgscore": lambda: _import("xGScoreFinder"),
    "eaglepredict": lambda: _import("EaglePredictFinder"),
    "legitpredict": lambda: _import("LegitPredictFinder"),
    "betclan": lambda: _import("BetClanFinder"),
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
    ],
    "local": ["whoscored",
              "forebet",
              "footballbettingtips"
              ],
    "all": list(_CRAWLER_KEYS.keys()),
    "test": ["windrawwin"],
}

MAX_CHUNK_SIZE = {"actions": 100, "local": 1, "all": 1, "test": 1}


def _import(cls: str):
    from bet_crawler import finders

    return getattr(finders, cls)


def get_crawler_class(url: str):
    lower = url.lower()
    for key, loader in _CRAWLER_KEYS.items():
        if key in lower:
            return loader()
    raise ValueError(f"No crawler registered for URL: {url}")


def get_runner_classes(runner: str) -> list:
    keys = _RUNNER_SETS.get(runner, [])
    return [_CRAWLER_KEYS[k]() for k in keys]