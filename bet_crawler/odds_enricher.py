"""
odds_enricher.py — Enrich matches with odds from Oddsportal.
────────────────────────────────────────────────────────────────────────────
Provides functions for mapping matches to Oddsportal URLs and scraping odds.

Two-Phase Flow
──────────────
  Phase 1 — mapping
    a. Load the Oddsportal date page, scroll to collect all match stubs.
    b. For each DB match, find the best-matching stub via SimilarityEngine.
    c. Save {rowid, odds_url} pairs to odds_mapping.json.

  Phase 2 — scrape
    Accept a mapping list of {rowid, odds_url} dictionaries and scrape odds
    for each match, returning a dictionary mapping rowid to scraped odds objects.
    Supports --concurrency N for parallel browser sessions.

Usage
─────
  python -m bet_crawler.odds_enricher \
      --matches_db_path final.db \
      --config_dir ./config --days 4 --phase mapping

  # Orchestration happens in bet_crawler/crawl.py:
  from bet_crawler.odds_enricher import scrape_odds_from_mapping
  mapping = [{"rowid": 1, "odds_url": "https://..."}, ...]
  results = scrape_odds_from_mapping(mapping, config_dir="./config", concurrency=3)
  # results = {1: {"home": 2.5, "draw": 3.2, "away": 2.8, ...}, ...}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from scrape_kit import SettingsManager, SimilarityEngine, browser, configure, get_logger

logger = get_logger(__name__)

ODDSPORTAL_BASE  = "https://www.oddsportal.com"
MAPPING_FILE     = "odds_mapping.json"
_TAB_SETTLE      = 3.5   # seconds after clicking a tab before reading DOM
_MATCH_DELAY     = 1.5   # seconds between match pages


def _moneyline_to_decimal(moneyline: str) -> float:
    """
    Convert moneyline odds to decimal odds.

    Args:
        moneyline: String like "-2500" or "+1200"

    Returns:
        Decimal odds as float
    """
    value = int(moneyline)
    if value > 0:
        # Positive moneyline: decimal = (moneyline / 100) + 1
        return (value / 100) + 1
    else:
        # Negative moneyline: decimal = (100 / abs(moneyline)) + 1
        return (100 / abs(value)) + 1


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_upcoming(db_path: str, days: int) -> list[dict]:
    today  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today + timedelta(days=days)
    conn   = sqlite3.connect(db_path)
    rows   = conn.execute("""
        SELECT rowid, home_team_name, away_team_name, datetime
        FROM matches
        WHERE datetime >= ?
        AND datetime < ?
        ORDER BY datetime
    """, (today.isoformat(), cutoff.isoformat())).fetchall()
    conn.close()
    return [
        {
            "rowid":    r[0],
            "home":     r[1],
            "away":     r[2],
            "datetime": r[3],
        }
        for r in rows
    ]


def _group_by_date(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["datetime"][:10]].append(row)
    return groups


# ─────────────────────────────────────────────────────────────────────────────
# Oddsportal date page (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

def _scroll_to_load_all(session, pause: float = 2.0, stable_threshold: int = 3) -> int:
    stable = last = 0
    for _ in range(80):
        session.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)
        count = session.execute_script(
            "return document.querySelectorAll('div[class*=\"eventRow\"]').length"
        )
        if count > last:
            stable, last = 0, count
        else:
            stable += 1
            if stable >= stable_threshold:
                break
    logger.info(f"[OddsEnricher] Scrolled — {last} event rows loaded")
    return last


def _parse_date_page(html: str, date_str: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup  = BeautifulSoup(html, "html.parser")
    rows  = soup.find_all("div", class_=re.compile(r"eventRow"))
    stubs = []

    for row in rows:
        participants = row.find_all(
            lambda t: t.get("class")
            and any("participant" in c.lower() for c in t["class"])
        )
        if len(participants) >= 2:
            home = participants[0].get_text(strip=True)
            away = participants[1].get_text(strip=True)
        else:
            anchors = [
                a for a in row.find_all("a", href=True)
                if re.search(r"/football/.+/.+/.+/", a["href"])
            ]
            if len(anchors) < 2:
                continue
            home = anchors[0].get_text(strip=True)
            away = anchors[1].get_text(strip=True)

        if not home or not away or home == away:
            continue

        anchor   = row.find("a", href=re.compile(r"/football/.+/.+/.+/"))
        odds_url = (ODDSPORTAL_BASE + anchor["href"]) if anchor else None
        stubs.append({"home": home, "away": away, "odds_url": odds_url})

    logger.info(f"[OddsEnricher] {date_str}: {len(stubs)} stubs parsed")
    return stubs


# ─────────────────────────────────────────────────────────────────────────────
# Odds scraping helpers (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

def _click_tab(session, labels: list[str]) -> bool:
    """
    Click first VISIBLE element whose trimmed text EXACTLY matches any label.
    Uses offsetParent check to skip hidden elements from inactive tabs.
    """
    labels_js = json.dumps(labels)
    return session.execute_script(f"""
        (function() {{
            const labels = {labels_js};
            for (const el of document.querySelectorAll('a,li,button,span,div')) {{
                if (el.offsetParent === null) continue;
                const txt = el.textContent.trim();
                if (labels.includes(txt)) {{
                    el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                    el.click();
                    return true;
                }}
            }}
            return false;
        }})()
    """)


def _click_ou_subtab(session, threshold: str) -> bool:
    """
    Click an Over/Under threshold sub-tab (e.g. "2.5").

    Root causes of previous failures:
      - Sub-tabs are <div data-testid="sub-nav-inactive-tab"> elements;
        the old code only searched a,li,button,span — never div.
      - Pass 2 endsWith fallback could match Match Facts text ("Under 2.5 Goals"
        was NOT the cause, but a plain <span>2.5</span> or O/U header could be).
        Now scoped to exclude match-facts containers.
    """
    labels_js = json.dumps([f"+{threshold}", threshold])
    thr_js    = json.dumps(threshold)
    return session.execute_script(f"""
        (function() {{
            const exact = {labels_js};
            const thr   = {thr_js};

            // Pass 1: data-testid sub-nav tabs — this is what Oddsportal
            // uses for BOTH period tabs (Full Time/1st Half) AND O/U thresholds.
            // These are <div> elements, missed entirely by the old selector list.
            for (const el of document.querySelectorAll(
                '[data-testid="sub-nav-inactive-tab"],' +
                '[data-testid="sub-nav-active-tab"]'
            )) {{
                const txt = el.textContent.trim();
                if (exact.includes(txt)
                        || txt.endsWith(thr)
                        || txt.endsWith('+' + thr)) {{
                    el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                    el.click();
                    return true;
                }}
            }}

            // Pass 2: visible a,li,button,span — exact match only,
            // skip anything inside the Match Facts section.
            for (const el of document.querySelectorAll('a,li,button,span')) {{
                if (el.offsetParent === null) continue;
                if (!exact.includes(el.textContent.trim())) continue;
                if (el.closest('[data-testid*="match-facts"]')) continue;
                el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                el.click();
                return true;
            }}

            return false;
        }})()
    """)

def _convert_list(values, n):
    """Convert a list of odds strings to decimal floats, handling both decimal and moneyline formats."""
    if not values or len(values) < n:
        return None

    converted = []
    for v in values:
        # Check if it's a moneyline format (no decimal point, optional +/-)
        if re.fullmatch(r'[+-]?\d+', v):
            try:
                converted.append(_moneyline_to_decimal(v))
            except (ValueError, ZeroDivisionError):
                converted.append(None)
        else:
            # Decimal format
            try:
                converted.append(float(v))
            except ValueError:
                converted.append(None)

    valid = [v for v in converted if v is not None]
    return valid[:n] if len(valid) >= n else None

def _read_first_bookmaker_odds(session, n_outcomes: int):
    """
    Extract the first N odds from the first bookmaker on the visible page.
    Works for both decimal and American (moneyline) odds.
    """
    result = session.execute_script(f"""
        (function() {{
            // Decimal (e.g. 2.05) or moneyline (e.g. +1200, -2500)
            const pat = /^(?:\\d{{1,3}}\\.\\d{{2}}|[+-]?\\d+)$/;
            const containers = document.querySelectorAll('[data-testid="odd-container"]');
            const odds = [];
            for (const c of containers) {{
                // Skip hidden elements (inactive tabs, popovers, etc.)
                if (c.offsetParent === null) continue;
                const t = c.textContent.trim();
                if (pat.test(t)) {{
                    odds.push(t);
                    if (odds.length === {n_outcomes}) break;
                }}
            }}
            return odds.length === {n_outcomes} ? odds : null;
        }})()
    """)

    return _convert_list(result, n_outcomes)

def _wait_for_odds_table(session, timeout_ms: int = 10_000) -> bool:
    """Block until at least one [data-testid='odd-container'] is in the DOM."""
    try:
        session.wait_for_selector('[data-testid="odd-container"]', timeout=timeout_ms)
        return True
    except Exception:
        return False

def _read_all_ou_odds(session) -> dict[str, tuple[float, float]] | None:
    """
    Read all Over/Under odds from the table at once.
    Supports both decimal odds (e.g., "2.05") and moneyline odds (e.g., "-2500", "+1200").
    Moneyline odds are converted to decimal format.

    The O/U page displays all thresholds in a single table with rows like:
        "Over/Under +0.5" -> [over_odds, under_odds]
        "Over/Under +1.5" -> [over_odds, under_odds]
        etc.

    Returns a dict mapping threshold (e.g., "0.5", "1.5") to (over, under) odds.
    """
    result = session.execute_script("""
        (function() {
            // Match decimal odds (e.g., "2.05") OR moneyline odds (e.g., "-2500", "+1200")
            const pat = /^(?:\\d{1,3}\\.\\d{2}|[+-]?\\d+)$/;
            const odds = {};

            // Find all paragraphs that contain O/U threshold labels
            // Each label is like "Over/Under +0.5"
            const allPs = document.querySelectorAll('p');

            for (const p of allPs) {
                const label = p.textContent.trim();
                // Match patterns like "Over/Under +0.5", "Over/Under +1.5", etc.
                const match = label.match(/Over\\/Under\\s*\\+(\\d+\\.\\d+)/);
                if (!match) continue;

                const threshold = match[1];  // e.g., "0.5", "1.5", "2.5"

                // Find the parent row/container that contains this label
                const labelContainer = p.closest('div');
                if (!labelContainer) continue;

                // The odds are in the next sibling generic element
                // Find the parent of the label container
                const rowContainer = labelContainer.parentElement;
                if (!rowContainer) continue;

                // Get all children of the row container
                const children = Array.from(rowContainer.children);

                // Find the index of the label container
                const labelIndex = children.indexOf(labelContainer);

                // The odds should be in the next sibling (index + 1)
                if (labelIndex >= 0 && labelIndex + 1 < children.length) {
                    const oddsContainer = children[labelIndex + 1];

                    // Find all odds values in this container
                    const oddPs = oddsContainer.querySelectorAll('p');
                    const values = [];

                    for (const op of oddPs) {
                        const t = op.textContent.trim();
                        if (pat.test(t)) {
                            values.push(t);  // Store raw string, convert later
                        }
                    }

                    // We need at least 2 odds (over and under)
                    if (values.length >= 2) {
                        odds[threshold] = values.slice(0, 2);
                    }
                }
            }

            return odds;
        })()
    """)

    if result:
        # Convert raw strings to decimal odds, handling both decimal and moneyline formats
        def _convert_value(val_str: str) -> float | None:
            # Check if it's a moneyline format (no decimal point, optional +/-)
            if re.fullmatch(r'[+-]?\d+', val_str):
                try:
                    dec = _moneyline_to_decimal(val_str)
                    logger.info(f"    Converted moneyline {val_str} -> decimal {dec:.2f}")
                    return dec
                except (ValueError, ZeroDivisionError):
                    logger.warning(f"    Failed to convert moneyline {val_str}")
                    return None
            else:
                # Decimal format
                try:
                    v = float(val_str)
                    if v >= 1.01 and v <= 200:
                        logger.info(f"    Using decimal value {v:.2f} (no conversion)")
                        return v
                    logger.warning(f"    Decimal value {v} out of range [1.01, 200]")
                    return None
                except ValueError:
                    logger.warning(f"    Invalid decimal value {val_str}")
                    return None

        converted_results = {}
        for threshold, raw_values in result.items():
            logger.debug(f"    O/U {threshold}: raw values {raw_values}")
            converted = [_convert_value(v) for v in raw_values]
            valid = [v for v in converted if v is not None]
            if len(valid) >= 2:
                converted_results[threshold] = (valid[0], valid[1])
                logger.info(f"    O/U {threshold}: final over={valid[0]:.2f}, under={valid[1]:.2f}")

        if converted_results:
            return converted_results
    return None

def _scrape_match_odds(session, odds_url: str) -> dict:
    """
    Navigate to a match page and scrape all available markets.
    Returns a flat dict mapping Odds dataclass field names → float values.
    """
    session.fetch(odds_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.0)

    # ── Wait for the odds table to render (async Vue component) ──────────────
    if not _wait_for_odds_table(session, timeout_ms=12000):
        logger.warning(f"  odds table never appeared on {odds_url}")
        return {}

    odds: dict = {}
    # ── 1x2 (default tab) ──────────────────────────────────────
    odds_1x2 = _read_first_bookmaker_odds(session, n_outcomes=3)
    if odds_1x2:
        odds.update({"home": odds_1x2[0], "draw": odds_1x2[1], "away": odds_1x2[2]})
        logger.info(f"  1x2: {odds_1x2}")
    else:
        logger.warning(f"  1x2: no odds found on {odds_url}")

    # ── Double Chance ─────────────────────────────────────────
    if _click_tab(session, ["Double Chance"]):
        time.sleep(_TAB_SETTLE)
        _wait_for_odds_table(session, timeout_ms=6_000)
        v = _read_first_bookmaker_odds(session, n_outcomes=3)
        if v:
            odds.update({"dc_1x": v[0], "dc_12": v[1], "dc_x2": v[2]})
            logger.info(f"  DC: {v}")
        else:
            logger.warning("  DC: tab clicked but no odds read")
    else:
        logger.warning("  DC: tab not found")

    # ── Both Teams to Score ───────────────────────────────────
    if _click_tab(session, ["Both Teams to Score"]):
        time.sleep(_TAB_SETTLE)
        _wait_for_odds_table(session, timeout_ms=6_000)
        v = _read_first_bookmaker_odds(session, n_outcomes=2)
        if v:
            odds.update({"btts_y": v[0], "btts_n": v[1]})
            logger.info(f"  BTTS: {v}")
        else:
            logger.warning("  BTTS: tab clicked but no odds read")
    else:
        logger.warning("  BTTS: tab not found")
    # ── Over/Under ────────────────────────────────────────────────────────────
    ou_tab_clicked = _click_tab(session, ["Over/Under", "Over/Under *", "O/U"])
    if ou_tab_clicked:
        time.sleep(_TAB_SETTLE)
        _wait_for_odds_table(session, timeout_ms=6_000)
        logger.info("  O/U: top tab clicked")

        # Read all O/U odds from the table at once
        # The page displays all thresholds (0.5, 1.5, 2.5, 3.5, 4.5, etc.) in a single table
        all_ou_odds = _read_all_ou_odds(session)

        if all_ou_odds:
            # Map thresholds to the field names we need
            for threshold, (over_f, under_f) in {
                "0.5": ("over_05", "under_05"),
                "1.5": ("over_15", "under_15"),
                "2.5": ("over_25", "under_25"),
                "3.5": ("over_35", "under_35"),
                "4.5": ("over_45", "under_45"),
            }.items():
                if threshold in all_ou_odds:
                    over_val, under_val = all_ou_odds[threshold]
                    odds[over_f] = over_val
                    odds[under_f] = under_val
                    logger.info(f"  O/U {threshold}: over={over_val}, under={under_val}")
                else:
                    logger.warning(f"  O/U {threshold}: not found in table")
        else:
            logger.warning("  O/U: no odds read from table")
    else:
        logger.warning("  O/U: top-level tab not found — check label on the page")

    return odds


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: create mapping
# ─────────────────────────────────────────────────────────────────────────────

def create_mapping(matches_db_path: str, config_dir: str, days: int = 4) -> list[dict]:
    """
    Create a mapping of database matches to Oddsportal URLs.

    Args:
        matches_db_path: Path to the matches SQLite database
        config_dir: Directory containing configuration files
        days: Number of days ahead to look for upcoming matches

    Returns:
        List of dictionaries with "rowid" and "odds_url" keys
    """
    configure(config_dir)
    sm     = SettingsManager(config_dir)
    engine = SimilarityEngine(sm.get("similarity_config"))

    rows = _load_upcoming(matches_db_path, days)
    if not rows:
        logger.info("[OddsEnricher] No upcoming matches in DB.")
        return []

    groups = _group_by_date(rows)
    logger.info(f"[OddsEnricher] {len(rows)} matches across {len(groups)} date(s)")

    mapping: list[dict] = []

    with browser(solve_cloudflare=True, interactive=True) as session:
        for date_str, db_rows in sorted(groups.items()):
            op_url = f"{ODDSPORTAL_BASE}/matches/football/{date_str.replace('-', '')}"
            logger.info(f"[OddsEnricher] === {date_str} ({len(db_rows)} DB rows) ===")

            session.fetch(op_url, wait_until="domcontentloaded", timeout=60000)
            try:
                session.wait_for_selector("div[class*='eventRow']", timeout=20000)
            except Exception:
                logger.warning(f"[OddsEnricher] No event rows for {date_str} — skip")
                continue

            _scroll_to_load_all(session)
            stubs = _parse_date_page(session.page.content(), date_str)
            if not stubs:
                logger.warning(f"[OddsEnricher] No stubs parsed for {date_str}")
                continue

            for db_row in db_rows:
                # Find best-matching Oddsportal stub for this DB row
                best_stub, best_score = None, -1.0
                for stub in stubs:
                    if (db_row["home"].lower() == stub["home"].lower()
                            and db_row["away"].lower() == stub["away"].lower()):
                        best_stub = stub
                        break
                    ok_h, sc_h = engine.is_similar(db_row["home"], stub["home"])
                    if not ok_h:
                        continue
                    ok_a, sc_a = engine.is_similar(db_row["away"], stub["away"])
                    if not ok_a:
                        continue
                    avg = (sc_h + sc_a) / 2
                    if avg > best_score:
                        best_score, best_stub = avg, stub

                if best_stub is None:
                    logger.warning(
                        f"[OddsEnricher] No OP match for: "
                        f"{db_row['home']} vs {db_row['away']}"
                    )
                    continue

                if not best_stub["odds_url"]:
                    logger.warning(
                        f"[OddsEnricher] No odds_url for: "
                        f"{best_stub['home']} vs {best_stub['away']}"
                    )
                    continue

                logger.info(
                    f"[OddsEnricher] ✓ OP [{best_stub['home']} vs {best_stub['away']}] "
                    f"→ DB [{db_row['home']} vs {db_row['away']}] "
                    f"rowid={db_row['rowid']}"
                )
                mapping.append({
                    "rowid":    db_row["rowid"],
                    "odds_url": best_stub["odds_url"],
                })

    logger.info(f"[OddsEnricher] Created {len(mapping)} mapping entries")
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: scrape odds from mapping
# ─────────────────────────────────────────────────────────────────────────────

def scrape_odds_from_mapping(
    mapping: list[dict],
    config_dir: str,
    concurrency: int = 1,
) -> dict[int, dict]:
    """
    Scrape odds from Oddsportal for each entry in the mapping list.

    Args:
        mapping: List of dictionaries with "rowid" and "odds_url" keys
        config_dir: Directory containing configuration files
        concurrency: Number of parallel browser sessions to use

    Returns:
        Dictionary mapping rowid to scraped odds objects.
        Example: {1: {"home": 2.5, "draw": 3.2, "away": 2.8, ...}, ...}
    """
    configure(config_dir)

    logger.info(f"[OddsEnricher] {len(mapping)} entries to scrape (concurrency={concurrency})")

    results: dict[int, dict] = {}

    def scrape_chunk(chunk: list[dict]) -> dict[int, dict]:
        chunk_results: dict[int, dict] = {}
        with browser(solve_cloudflare=True, interactive=True) as session:
            for entry in chunk:
                rowid    = entry["rowid"]
                odds_url = entry["odds_url"]
                try:
                    logger.info(f"[OddsEnricher] Scraping rowid={rowid} — {odds_url}")
                    scraped = _scrape_match_odds(session, odds_url)

                    if not scraped:
                        logger.warning(f"[OddsEnricher] No odds scraped for rowid={rowid}")
                        continue

                    chunk_results[rowid] = scraped
                    logger.info(
                        f"[OddsEnricher] ✓ rowid={rowid} — "
                        f"scraped {len(scraped)} fields: {sorted(scraped.keys())}"
                    )
                except Exception as exc:
                    logger.error(f"[OddsEnricher] Error rowid={rowid}: {exc}")

                time.sleep(_MATCH_DELAY)
        return chunk_results

    # Split into chunks for parallel browser sessions
    size   = max(1, len(mapping) // concurrency)
    chunks = [mapping[i:i + size] for i in range(0, len(mapping), size)]

    if concurrency == 1:
        results = scrape_chunk(chunks[0] if chunks else [])
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(scrape_chunk, c) for c in chunks]
            for f in as_completed(futures):
                chunk_results = f.result()
                results.update(chunk_results)

    logger.info(f"[OddsEnricher] ✅ Scraped {len(results)} odds entries.")
    return results
