"""
odds_enricher.py — Enrich an existing matches DB with odds from Oddsportal.
────────────────────────────────────────────────────────────────────────────
Assumes the DB already has home_team_name / away_team_name / datetime populated
by the prediction scrapers.  This script only writes to the `odds` column.

Two-Phase Flow
──────────────
  Phase 1 — mapping
    a. Load the Oddsportal date page, scroll to collect all match stubs.
    b. For each DB match, find the best-matching stub via SimilarityEngine.
    c. Save {rowid, odds_url} pairs to odds_mapping.json.

  Phase 2 — scrape
    Load odds_mapping.json and scrape each match page for all markets,
    writing results directly back to the DB by rowid.
    Supports --concurrency N for parallel browser sessions.

Usage
─────
  python -m bet_crawler.odds_enricher \
      --matches_db_path final.db \
      --config_dir ./config --days 4 --phase mapping

  python -m bet_crawler.odds_enricher \
      --matches_db_path final.db \
      --config_dir ./config --phase scrape --concurrency 3
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


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_upcoming(db_path: str, days: int) -> list[dict]:
    today  = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today + timedelta(days=days)
    conn   = sqlite3.connect(db_path)
    rows   = conn.execute("""
        SELECT rowid, home_team_name, away_team_name, datetime, odds
        FROM matches
        WHERE datetime >= ? AND datetime < ?
        ORDER BY datetime
    """, (today.isoformat(), cutoff.isoformat())).fetchall()
    conn.close()
    return [
        {
            "rowid":    r[0],
            "home":     r[1],
            "away":     r[2],
            "datetime": r[3],
            "odds":     json.loads(r[4]) if r[4] else {},
        }
        for r in rows
    ]


def _load_existing_odds(db_path: str, rowid: int) -> dict:
    conn = sqlite3.connect(db_path)
    row  = conn.execute(
        "SELECT odds FROM matches WHERE rowid = ?", (rowid,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else {}


def _write_odds(db_path: str, rowid: int, odds: dict) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE matches SET odds = ? WHERE rowid = ?",
        (json.dumps(odds), rowid),
    )
    conn.commit()
    conn.close()


def _group_by_date(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["datetime"][:10]].append(row)
    return groups


# ─────────────────────────────────────────────────────────────────────────────
# Similarity matching
# ─────────────────────────────────────────────────────────────────────────────

def _best_match(
    op_home: str,
    op_away: str,
    db_rows: list[dict],
    engine: SimilarityEngine,
) -> dict | None:
    best_row, best_score = None, -1.0
    for row in db_rows:
        if (row["home"].lower() == op_home.lower()
                and row["away"].lower() == op_away.lower()):
            return row
        ok_h, sc_h = engine.is_similar(row["home"], op_home)
        if not ok_h:
            continue
        ok_a, sc_a = engine.is_similar(row["away"], op_away)
        if not ok_a:
            continue
        avg = (sc_h + sc_a) / 2
        if avg > best_score:
            best_score, best_row = avg, row
    return best_row


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
    Click an Over/Under sub-tab.  Tries exact match first, then startsWith
    fallback (e.g. "2.5" matches "2.5 Goals" or "+2.5").
    """
    thr_js = json.dumps(threshold)
    return session.execute_script(f"""
        (function() {{
            const thr = {thr_js};
            // Pass 1: exact match
            for (const el of document.querySelectorAll('a,li,button,span')) {{
                if (el.offsetParent === null) continue;
                if (el.textContent.trim() === thr) {{
                    el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                    el.click();
                    return true;
                }}
            }}
            // Pass 2: starts-with match (handles "+2.5", "2.5 Goals", etc.)
            for (const el of document.querySelectorAll('a,li,button,span')) {{
                if (el.offsetParent === null) continue;
                const txt = el.textContent.trim();
                if (txt.startsWith(thr) || txt.endsWith(thr)) {{
                    el.scrollIntoView({{behavior: 'auto', block: 'center'}});
                    el.click();
                    return true;
                }}
            }}
            return false;
        }})()
    """)


def _read_n_odds(session, n: int) -> list[float] | None:
    """
    Read the first n decimal odds from VISIBLE elements only.

    Critical: offsetParent === null check ensures we only read from the
    currently active tab, not from hidden/stale content of other tabs.
    """
    result = session.execute_script(f"""
        (function() {{
            const n = {n};
            // Matches odds like "1.85", "12.50", "100.00"
            const pat = /^\\d{{1,3}}\\.\\d{{2}}$/;
            const found = [];

            // Strategy 1: visible elements whose class contains "odds"
            for (const el of document.querySelectorAll('[class*="odds"]')) {{
                if (el.offsetParent === null) continue;
                const t = el.textContent.trim();
                if (pat.test(t)) {{
                    const v = parseFloat(t);
                    if (v >= 1.01 && v <= 200) {{
                        found.push(v);
                        if (found.length === n) return found;
                    }}
                }}
            }}

            // Strategy 2: first visible table row with enough numeric cells
            for (const tbl of document.querySelectorAll('table')) {{
                if (tbl.offsetParent === null) continue;
                const rows = Array.from(tbl.querySelectorAll('tr')).slice(1);
                for (const row of rows) {{
                    if (row.offsetParent === null) continue;
                    const vals = [];
                    for (const c of row.querySelectorAll('td, th')) {{
                        const t = c.textContent.trim();
                        if (pat.test(t)) {{
                            const v = parseFloat(t);
                            if (v >= 1.01 && v <= 200) vals.push(v);
                        }}
                    }}
                    if (vals.length >= n) return vals.slice(0, n);
                }}
            }}

            return found.length >= n ? found.slice(0, n) : null;
        }})()
    """)

    if result and len(result) >= n:
        return [float(v) for v in result[:n]]
    return None


def _scrape_match_odds(session, odds_url: str) -> dict:
    """
    Navigate to a match page and scrape all available markets.
    Returns a flat dict mapping Odds dataclass field names → float values.
    """
    session.fetch(odds_url, wait_until="domcontentloaded", timeout=30_000)
    time.sleep(2.0)   # let React finish initial render

    odds: dict = {}

    # ── 1x2 (default tab — already visible on load) ───────────────────────────
    v = _read_n_odds(session, 3)
    if v:
        odds.update({"home": v[0], "draw": v[1], "away": v[2]})
        logger.debug(f"  1x2: {v}")
    else:
        logger.warning(f"  1x2: no odds found on {odds_url}")

    # ── Double Chance ─────────────────────────────────────────────────────────
    if _click_tab(session, ["Double Chance"]):
        time.sleep(_TAB_SETTLE)
        v = _read_n_odds(session, 3)
        if v:
            odds.update({"dc_1x": v[0], "dc_12": v[1], "dc_x2": v[2]})
            logger.debug(f"  DC: {v}")
        else:
            logger.warning("  DC: tab clicked but no odds read")
    else:
        logger.debug("  DC: tab not found")

    # ── Both Teams to Score ───────────────────────────────────────────────────
    if _click_tab(session, ["Both Teams to Score"]):
        time.sleep(_TAB_SETTLE)
        v = _read_n_odds(session, 2)
        if v:
            odds.update({"btts_y": v[0], "btts_n": v[1]})
            logger.debug(f"  BTTS: {v}")
        else:
            logger.warning("  BTTS: tab clicked but no odds read")
    else:
        logger.debug("  BTTS: tab not found")

    # ── Over/Under ────────────────────────────────────────────────────────────
    # Click the top-level O/U tab first, then iterate threshold sub-tabs.
    if _click_tab(session, ["Over/Under", "O/U"]):
        time.sleep(_TAB_SETTLE)

        for threshold, (over_f, under_f) in {
            "0.5": ("over_05", "under_05"),
            "1.5": ("over_15", "under_15"),
            "2.5": ("over_25", "under_25"),
            "3.5": ("over_35", "under_35"),
            "4.5": ("over_45", "under_45"),
        }.items():
            if _click_ou_subtab(session, threshold):
                time.sleep(_TAB_SETTLE)
                v = _read_n_odds(session, 2)
                if v:
                    odds[over_f]  = v[0]
                    odds[under_f] = v[1]
                    logger.debug(f"  O/U {threshold}: {v}")
                else:
                    logger.warning(f"  O/U {threshold}: sub-tab clicked but no odds read")
            else:
                logger.debug(f"  O/U {threshold}: sub-tab not found")
    else:
        logger.debug("  O/U: top-level tab not found")

    return odds


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: create mapping
# ─────────────────────────────────────────────────────────────────────────────

def create_mapping(matches_db_path: str, config_dir: str, days: int = 4) -> None:
    configure(config_dir)
    sm     = SettingsManager(config_dir)
    engine = SimilarityEngine(sm.get("similarity_config"))

    rows = _load_upcoming(matches_db_path, days)
    if not rows:
        logger.info("[OddsEnricher] No upcoming matches in DB.")
        return

    groups = _group_by_date(rows)
    logger.info(f"[OddsEnricher] {len(rows)} matches across {len(groups)} date(s)")

    mapping: list[dict] = []

    with browser(solve_cloudflare=True, interactive=True) as session:
        for date_str, db_rows in sorted(groups.items()):
            op_url = f"{ODDSPORTAL_BASE}/matches/football/#{date_str.replace('-', '')}"
            logger.info(f"[OddsEnricher] === {date_str} ({len(db_rows)} DB rows) ===")

            session.fetch(op_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                session.wait_for_selector("div[class*='eventRow']", timeout=20_000)
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

    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)
    logger.info(f"[OddsEnricher] Saved {len(mapping)} entries to {MAPPING_FILE}")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: scrape odds from mapping
# ─────────────────────────────────────────────────────────────────────────────

def scrape_odds_from_mapping(
    matches_db_path: str,
    config_dir: str,
    concurrency: int = 1,
) -> None:
    configure(config_dir)

    if not os.path.exists(MAPPING_FILE):
        logger.error(f"[OddsEnricher] Mapping file not found: {MAPPING_FILE}")
        return

    with open(MAPPING_FILE) as f:
        mapping: list[dict] = json.load(f)

    logger.info(f"[OddsEnricher] {len(mapping)} entries to scrape (concurrency={concurrency})")

    def scrape_chunk(chunk: list[dict]) -> None:
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

                    # Load existing DB odds and merge — scraped fills gaps,
                    # existing non-null values are preserved
                    existing = _load_existing_odds(matches_db_path, rowid)
                    merged   = {**scraped, **{k: v for k, v in existing.items() if v}}
                    _write_odds(matches_db_path, rowid, merged)

                    logger.info(
                        f"[OddsEnricher] ✓ rowid={rowid} — "
                        f"wrote {len(merged)} fields: {sorted(merged.keys())}"
                    )
                except Exception as exc:
                    logger.error(f"[OddsEnricher] Error rowid={rowid}: {exc}")

                time.sleep(_MATCH_DELAY)

    # Split into chunks for parallel browser sessions
    size   = max(1, len(mapping) // concurrency)
    chunks = [mapping[i:i + size] for i in range(0, len(mapping), size)]

    if concurrency == 1:
        scrape_chunk(chunks[0] if chunks else [])
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(scrape_chunk, c) for c in chunks]
            for f in as_completed(futures):
                f.result()

    logger.info("[OddsEnricher] ✅ Phase 2 complete.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Enrich match odds from Oddsportal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--matches_db_path", required=True)
    p.add_argument("--config_dir",      required=True)
    p.add_argument("--days",        type=int, default=4)
    p.add_argument("--phase",       choices=["mapping", "scrape"], default="mapping")
    p.add_argument("--concurrency", type=int, default=1)
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    if args.phase == "mapping":
        create_mapping(args.matches_db_path, args.config_dir, args.days)
    else:
        scrape_odds_from_mapping(
            args.matches_db_path, args.config_dir, args.concurrency
        )