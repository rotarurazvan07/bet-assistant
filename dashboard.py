"""
Bet Assistant Dashboard — refactored.

Architecture
────────────
Pure UI builders (module-level functions, no side effects):
  make_tooltip           — renders a (?) popover for any field
  make_nullable_row      — label + (?) + switch + optional collapse content
  build_config_section   — titled card section for the builder panel
  build_builder_panel    — full left-hand config panel (all BetSlipConfig fields)
  render_bet_preview     — takes flat list of picks from _select_legs, returns grid
  render_profile_card    — one profile card (units + run_daily, read-only BetSlipConfig summary)
  render_stats_cards     — stats summary row
  render_slip_card       — one historical slip card

Profile YAML schema (1-to-1 with BetSlipConfig + operational fields):
  All BetSlipConfig fields present.
  date_from / date_to are always null — driven by the global Time Horizon filter.
  excluded_urls is always null — managed at runtime by the builder.
  Additional keys: units (float), run_daily (bool).
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, fields as dc_fields
from pathlib import Path
from typing import Any, Dict, Optional

import dash
import dash_bootstrap_components as dbc
from dash import ALL, MATCH, Input, Output, State, callback_context, dcc, html, dash_table
import pandas as pd

from bet_framework.BettingAnalyzer import BetSlipConfig, BettingAnalyzer, PROFILES
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager
from bet_framework.BetSlipManager import BetSlipManager


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ALL_MARKET_TYPES = ["result", "over_under_2.5", "btts"]

# Fields that live in the YAML but are NOT part of BetSlipConfig
_DASHBOARD_ONLY_KEYS = {"units", "run_daily"}

# BetSlipConfig fields that are always None in saved profiles (runtime-only)
_RUNTIME_ONLY_FIELDS = {"date_from", "date_to", "excluded_urls"}

# Fields that are Optional[...] and can be set to None via the UI toggle
_NULLABLE_CONFIG_FIELDS = {"max_legs_overflow", "tolerance_factor", "stop_threshold"}

# All valid BetSlipConfig field names
_BETSLIP_CONFIG_FIELDS = {f.name for f in dc_fields(BetSlipConfig)}


TOOLTIP_TEXTS: Dict[str, str] = {
    "target_odds": (
        "Desired cumulative odds for the entire slip. "
        "The algorithm stops building once it gets close enough to this number."
    ),
    "target_legs": (
        "Desired number of selections (legs) on the slip. "
        "Range: 1–10."
    ),
    "max_legs_overflow": (
        "How many extra legs beyond target_legs are allowed. "
        "Auto = 0 for singles, +1 for 2–4 legs, +2 for 5+ legs. "
        "Override only if you need tighter control."
    ),
    "probability_floor": (
        "Minimum prediction confidence (%). Picks below this threshold are "
        "discarded before any scoring. E.g. 55 = only picks where 55 %+ of "
        "historical results agree with the prediction."
    ),
    "min_odds": (
        "Minimum bookmaker odds to consider. "
        "Filters out near-certain outcomes where the margin is unattractive. "
        "Range: 1.01–10.0."
    ),
    "included_market_types": (
        "Which bet markets to include. "
        "Results = 1/X/2, O/U 2.5 = goals over/under, BTTS = both teams score."
    ),
    "tolerance_factor": (
        "±% band around the ideal per-leg odds. A pick within this band is "
        "'Tier 1 balanced' and always ranked above out-of-band picks. "
        "Auto = wider for few legs, tighter for many (prevents drift). "
        "Range: 5 %–80 %."
    ),
    "stop_threshold": (
        "The builder stops when current_total_odds ≥ target_odds × threshold "
        "AND enough legs are filled. E.g. 0.95 = stop within 5 % of target. "
        "Auto is derived per target_legs. Range: 0.50–1.00."
    ),
    "min_legs_fill_ratio": (
        "Fraction of target_legs that must be filled before early-stop is allowed. "
        "E.g. 0.70 = need at least 70 % of legs before stopping early. "
        "Range: 0.50–1.00."
    ),
    "quality_vs_balance": (
        "Trade-off between pick quality and odds balance.\n"
        "0.0 = care only about matching the target odds per leg\n"
        "0.5 = equal weight (default)\n"
        "1.0 = care only about quality (best prob/sources wins)"
    ),
    "prob_vs_sources": (
        "Within the quality score, how much weight goes to probability vs data sources.\n"
        "0.0 = sources only\n"
        "0.5 = equal weight (default)\n"
        "1.0 = probability only"
    )
}


# ─────────────────────────────────────────────────────────────────────────────
# Profile helpers
# ─────────────────────────────────────────────────────────────────────────────

def config_to_yaml_dict(cfg: BetSlipConfig, units: float = 1.0, run_daily: bool = False) -> dict:
    """Serialise a BetSlipConfig + operational fields into the profile YAML dict."""
    d = asdict(cfg)
    # Always store runtime-only fields as None (time horizon is global, not per-profile)
    for k in _RUNTIME_ONLY_FIELDS:
        d[k] = None
    d["units"] = units
    d["run_daily"] = run_daily
    return d


def yaml_dict_to_config(data: dict) -> BetSlipConfig:
    """Construct a BetSlipConfig from a profile YAML dict (ignores dashboard-only keys)."""
    cfg_kwargs = {k: v for k, v in data.items()
                  if k in _BETSLIP_CONFIG_FIELDS and k not in _RUNTIME_ONLY_FIELDS}
    return BetSlipConfig(**cfg_kwargs)


def ensure_default_profiles(profiles_dir: str = "config/profiles"):
    """Write built-in PROFILES to disk if they do not already exist."""
    os.makedirs(profiles_dir, exist_ok=True)
    for name, cfg in PROFILES.items():
        path = os.path.join(profiles_dir, f"{name}.yaml")
        if not os.path.exists(path):
            data = config_to_yaml_dict(cfg, units=1.0, run_daily=False)
            settings_manager.write_settings(name, data, config_dir=profiles_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Pure UI component builders
# ─────────────────────────────────────────────────────────────────────────────

def make_tooltip(field_id: str, text: str) -> html.Span:
    """Return a small (?) icon with a hover popover."""
    tip_id = f"tip-{field_id}"
    return html.Span([
        html.Span("?", id=tip_id,
                  className="ms-1 text-muted fw-bold",
                  style={
                      "cursor": "pointer",
                      "fontSize": "0.65rem",
                      "border": "1px solid #adb5bd",
                      "borderRadius": "50%",
                      "padding": "1px 5px",
                      "verticalAlign": "middle",
                  }),
        dbc.Tooltip(text, target=tip_id, placement="right",
                    style={"fontSize": "0.75rem", "maxWidth": "300px",
                           "whiteSpace": "pre-wrap"}),
    ])


def make_labeled_row(label: str, field_id: str, control: Any) -> dbc.Row:
    """Label on left, (?) icon, control on right."""
    return dbc.Row([
        dbc.Col([
            html.Small(label, className="fw-bold text-muted"),
            make_tooltip(field_id, TOOLTIP_TEXTS.get(field_id, "")),
        ], width=5, className="d-flex align-items-center"),
        dbc.Col(control, width=7),
    ], className="mb-2 align-items-center g-1")


def make_nullable_row(label: str, field_id: str, switch_id: str,
                       collapse_id: str, inner_control: Any,
                       enabled: bool = False) -> html.Div:
    """
    A config row where the field can be toggled between Auto (None) and Manual.
    When toggled on, inner_control is revealed via Collapse.
    """
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Small(label, className="fw-bold text-muted"),
                make_tooltip(field_id, TOOLTIP_TEXTS.get(field_id, "")),
            ], width=7, className="d-flex align-items-center"),
            dbc.Col([
                dbc.Checklist(
                    options=[{"label": html.Small("Manual", className="text-muted"), "value": 1}],
                    value=[1] if enabled else [],
                    id=switch_id,
                    switch=True, inline=True, className="mb-0"
                )
            ], width=5, className="text-end")
        ], className="align-items-center g-1"),
        dbc.Collapse(
            html.Div(inner_control, className="mt-1 ps-2 border-start border-2 border-primary-subtle"),
            id=collapse_id,
            is_open=enabled
        )
    ], className="mb-2")


def build_config_section(title: str, icon: str, children: list) -> dbc.Card:
    """Titled collapsible section card for the builder panel."""
    return dbc.Card([
        dbc.CardHeader(
            html.Small([html.I(className=f"fas {icon} me-2 text-primary"), title],
                       className="fw-bold text-uppercase text-muted"),
            className="bg-transparent border-0 py-2 px-3"
        ),
        dbc.CardBody(children, className="py-2 px-3")
    ], className="border-0 bg-light rounded-3 mb-2")


def build_builder_panel() -> html.Div:
    """
    Build the full configuration panel for the Smart Builder tab.
    Every BetSlipConfig field is represented here.
    """

    # ── Bet Shape ──────────────────────────────────────────────────────────
    shape_section = build_config_section("Bet Shape", "fa-layer-group", [
        make_labeled_row("Target Odds", "target_odds",
            dbc.Input(id="b-target-odds", type="number",
                      value=3.0, min=1.1, max=1000.0, step=0.1, size="sm")
        ),
        make_labeled_row("Target Legs", "target_legs",
            dbc.Input(id="b-target-legs", type="number",
                      value=3, min=1, max=10, step=1, size="sm")
        ),
        make_nullable_row(
            "Max Overflow Legs", "max_legs_overflow",
            switch_id="b-max-overflow-sw", collapse_id="b-max-overflow-collapse",
            inner_control=dbc.Row([
                dbc.Col(html.Small("Extra legs allowed:", className="text-muted"), width=7),
                dbc.Col(dbc.Input(id="b-max-overflow-val", type="number",
                                   value=1, min=0, max=5, step=1, size="sm"), width=5),
            ], className="align-items-center g-1")
        ),
    ])

    # ── Quality Gate ───────────────────────────────────────────────────────
    quality_section = build_config_section("Quality Gate", "fa-filter", [
        make_labeled_row("Probability Floor", "probability_floor",
            html.Div([
                dcc.Slider(id="b-prob-floor", min=0, max=100, step=1, value=55,
                           marks={0: "0%", 50: "50%", 75: "75%", 100: "100%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        ),
        make_labeled_row("Min Odds", "min_odds",
            dbc.Input(id="b-min-odds", type="number",
                      value=1.05, min=1.01, max=10.0, step=0.01, size="sm")
        ),
    ])

    # ── Markets ────────────────────────────────────────────────────────────
    markets_section = build_config_section("Markets", "fa-tags", [
        dbc.Row([
            dbc.Col([
                html.Small("Included Markets", className="fw-bold text-muted"),
                make_tooltip("included_market_types",
                             TOOLTIP_TEXTS.get("included_market_types", "")),
            ], width=5, className="d-flex align-items-center"),
            dbc.Col(
                dbc.Checklist(
                    id="b-markets",
                    options=[
                        {"label": "Results (1/X/2)", "value": "result"},
                        {"label": "Over/Under 2.5", "value": "over_under_2.5"},
                        {"label": "BTTS",            "value": "btts"},
                    ],
                    value=ALL_MARKET_TYPES,
                    inline=False, switch=True,
                    style={"fontSize": "0.8rem"}
                ), width=7
            ),
        ], className="align-items-start g-1")
    ])

    # ── Tolerance & Stop ───────────────────────────────────────────────────
    tol_section = build_config_section("Tolerance & Stop", "fa-crosshairs", [
        make_nullable_row(
            "Tolerance Factor", "tolerance_factor",
            switch_id="b-tolerance-sw", collapse_id="b-tolerance-collapse",
            inner_control=html.Div([
                html.Small("±% band around ideal odds per leg:", className="text-muted"),
                dcc.Slider(id="b-tolerance-val", min=5, max=80, step=1, value=25,
                           marks={5: "5%", 25: "25%", 50: "50%", 80: "80%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        ),
        make_nullable_row(
            "Stop Threshold", "stop_threshold",
            switch_id="b-stop-sw", collapse_id="b-stop-collapse",
            inner_control=html.Div([
                html.Small("Stop when odds reach X% of target:", className="text-muted"),
                dcc.Slider(id="b-stop-val", min=50, max=100, step=1, value=91,
                           marks={50: "50%", 80: "80%", 95: "95%", 100: "100%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        ),
        make_labeled_row("Min Legs Fill Ratio", "min_legs_fill_ratio",
            html.Div([
                dcc.Slider(id="b-fill-ratio", min=50, max=100, step=5, value=70,
                           marks={50: "50%", 70: "70%", 100: "100%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        ),
    ])

    # ── Scoring ────────────────────────────────────────────────────────────
    scoring_section = build_config_section("Scoring", "fa-sliders-h", [
        make_labeled_row("Quality vs Balance", "quality_vs_balance",
            html.Div([
                html.Div([
                    html.Small("← Balance", className="text-muted", style={"fontSize": "0.65rem"}),
                    html.Small("Quality →", className="text-muted float-end", style={"fontSize": "0.65rem"}),
                ]),
                dcc.Slider(id="b-quality-vs-balance", min=0, max=100, step=5, value=50,
                           marks={0: "0", 50: "50", 100: "100"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        ),
        make_labeled_row("Prob vs Sources", "prob_vs_sources",
            html.Div([
                html.Div([
                    html.Small("← Sources", className="text-muted", style={"fontSize": "0.65rem"}),
                    html.Small("Prob →", className="text-muted float-end", style={"fontSize": "0.65rem"}),
                ]),
                dcc.Slider(id="b-prob-vs-sources", min=0, max=100, step=5, value=50,
                           marks={0: "0", 50: "50", 100: "100"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])
        )
    ])

    return html.Div([
        shape_section,
        quality_section,
        markets_section,
        tol_section,
        scoring_section,
    ])


def render_bet_preview(selections: list) -> html.Div:
    """
    Render the bet slip preview from the flat list returned by _select_legs.
    Each item: {match, market, market_type, prob, odds, result_url, sources, tier, score}
    """
    if not selections:
        return dbc.Alert("No matches meet criteria with current settings.", color="warning")

    total_odds = 1.0
    for s in selections:
        total_odds *= s.get("odds", 1.0)

    # Summary bar
    tier2_count = sum(1 for s in selections if s.get("tier", 1) == 2)
    drift_badge = (
        dbc.Badge(f"{tier2_count} out-of-band", color="warning", className="ms-2")
        if tier2_count else None
    )

    summary = dbc.Row([
        dbc.Col([
            html.Span("Total Odds: ", className="text-muted small"),
            html.Span(f"@{total_odds:.2f}", className="fw-bold fs-5 text-primary"),
        ], width="auto"),
        dbc.Col([
            html.Span("Legs: ", className="text-muted small"),
            html.Span(str(len(selections)), className="fw-bold text-dark"),
            drift_badge,
        ], width="auto"),
    ], className="align-items-center g-3 mb-3 p-2 bg-white rounded-3 shadow-sm")

    # Cards grid
    cards = []
    for pick in selections:
        conf = pick["prob"]
        conf_color = "success" if conf >= 80 else "warning" if conf >= 60 else "danger"
        tier = pick.get("tier", 1)
        score = pick.get("score", 0.0)

        tier_badge = dbc.Badge(
            "✓ Balanced" if tier == 1 else "⚠ Drift",
            color="success" if tier == 1 else "warning",
            className="me-1",
            style={"fontSize": "0.6rem"}
        )
        score_badge = dbc.Badge(
            f"Score {score:.2f}",
            color="light", text_color="dark",
            style={"fontSize": "0.6rem"}
        )

        card = dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    # Match name + exclude button
                    dbc.Row([
                        dbc.Col(
                            html.H6(pick["match"], className="fw-bold text-dark mb-0",
                                    style={"fontSize": "0.95rem"}),
                            width=10
                        ),
                        dbc.Col(
                            dbc.Button(
                                html.I(className="fas fa-times"),
                                id={"type": "exclude-btn", "index": pick["result_url"]},
                                color="link", size="sm",
                                className="p-0 text-muted text-decoration-none"
                            ),
                            width=2, className="text-end"
                        ),
                    ], className="mb-2 align-items-center"),

                    # Market + odds
                    dbc.Row([
                        dbc.Col(
                            html.Span(pick["market"], className="fw-bold fs-6"), width=8
                        ),
                        dbc.Col(
                            dbc.Badge(f"@{pick['odds']:.2f}",
                                      color="primary", className="fs-6 float-end"),
                            width=4
                        ),
                    ], className="align-items-center mb-2"),

                    # Confidence bar
                    dbc.Progress(value=conf, color=conf_color,
                                 style={"height": "6px"}, className="rounded-pill mb-1"),

                    # Meta row
                    html.Div([
                        html.Small(f"Conf: {conf}%",
                                   className=f"fw-bold text-{conf_color} me-2",
                                   style={"fontSize": "0.7rem"}),
                        html.Small(f"Sources: {pick.get('sources', 0)}",
                                   className="text-muted me-2",
                                   style={"fontSize": "0.7rem"}),
                        tier_badge,
                        score_badge,
                    ], className="d-flex align-items-center flex-wrap"),
                ], className="p-2")
            ], className="shadow-sm border-0 rounded-3 h-100",
               style={"backgroundColor": "#f8f9fa"}),
            xs=12, lg=6, className="mb-3"
        )
        cards.append(card)

    return html.Div([summary, dbc.Row(cards, className="g-2")])


def render_stats_cards(stats: dict) -> list:
    bal_color = "success" if stats["net_profit"] >= 0 else "danger"
    roi_color = "success" if stats["roi_percentage"] >= 0 else "danger"

    def card(title, value, color, size="H4", col_size=(2, 4, 6)):
        return dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6(title, className="text-muted text-uppercase mb-1",
                        style={"fontSize": "0.7rem"}),
                getattr(html, size)(value, className=f"mb-0 fw-bold text-{color}")
            ])
        ], className="border-0 shadow-sm rounded-3"), lg=col_size[0], md=col_size[1], xs=col_size[2])

    return [
        card("Total Bet",   f"{stats['total_units_bet']} Units",  "primary"),
        card("Gross Return",   f"{stats['gross_return']} Units",  "success"),
        card("Net Profit", f"{stats['net_profit']:+g} U",       bal_color, "H3", (3, 4, 12)),
        card("Win Rate",    f"{stats['win_rate']}%",              "info"),
        card("ROI %",       f"{stats['roi_percentage']}%",        roi_color),
        card("Settled",     str(stats["total_settled"]),          "dark", "H4", (1, 4, 6)),
    ]


def render_slip_card(slip: dict) -> dbc.Card:
    """Render one historical slip card."""
    status_map = {
        "Won":  ("#d1e7dd", "text-success", "success"),
        "Lost": ("#f8d7da", "text-danger",  "danger"),
    }
    hdr_bg, txt_cls, badge_col = status_map.get(
        slip["slip_status"], ("#f8f9fa", "text-dark", "secondary")
    )

    leg_rows = []
    for leg in slip["legs"]:
        icon_cls = {
            "Won":  "fa-check-circle text-success",
            "Lost": "fa-times-circle text-danger",
        }.get(leg["status"], "fa-clock text-secondary")

        leg_rows.append(dbc.Row([
            dbc.Col(html.I(className=f"fas {icon_cls}"), width=1, className="text-center"),
            dbc.Col(html.Span(leg["match_name"], className="fw-medium",
                              style={"fontSize": "0.85rem"}), width=6),
            dbc.Col(html.Span(leg["market"], style={"fontSize": "0.8rem"}), width=3),
            dbc.Col(html.Span(f"@{leg['odds']:.2f}", className="fw-bold text-end",
                              style={"fontSize": "0.85rem"}), width=2, className="text-end"),
        ], className="py-2 border-bottom align-items-center g-0"))

    return dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.Strong(f"Date: {slip['date_generated']}"), width=4),
                dbc.Col(html.Span(f"Profile: {slip['profile'].upper()}", className="fw-bold"), width=3),
                dbc.Col(html.Span(f"Total Odds: @{slip['total_odds']:.2f}", className="fw-bold"),
                        width=3, className="text-end"),
                dbc.Col(dbc.Badge(slip["slip_status"], color=badge_col, className="float-end"), width=2),
            ], className="align-items-center"),
        ], style={"backgroundColor": hdr_bg, "color": txt_cls}, className="border-bottom-0"),
        dbc.CardBody(leg_rows, className="p-2"),
    ], className="mb-3 shadow-sm border-0")


def render_profile_card(profile_id: str, prof: dict) -> dbc.Card:
    """
    Profile card for the Profiles tab.
    Shows a summary of key BetSlipConfig parameters (read-only) plus editable
    operational fields (units, run_daily).
    """
    def param_badge(label, value):
        return dbc.Badge(f"{label}: {value}", color="light", text_color="dark",
                         className="me-1 mb-1", style={"fontSize": "0.7rem"})

    summary_badges = html.Div([
        param_badge("Odds",     prof.get("target_odds",  "—")),
        param_badge("Legs",     prof.get("target_legs",  "—")),
        param_badge("ProbFloor",f"{prof.get('probability_floor', '—')}%"),
        param_badge("Q/B",      prof.get("quality_vs_balance", "—")),
        param_badge("P/S",      prof.get("prob_vs_sources", "—"))
    ], className="mt-2 mb-3")

    markets_raw = prof.get("included_market_types")
    markets_str = "All" if not markets_raw else ", ".join(markets_raw)

    return dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.H6(profile_id.upper(),
                                className="mb-0 fw-bold text-primary small"), width=9),
                dbc.Col(
                    dbc.Button(html.I(className="fas fa-trash-alt"),
                               id={"type": "delete-profile-btn", "index": profile_id},
                               color="danger", size="sm", outline=True,
                               className="p-1 border-0"),
                    width=3, className="text-end"
                ),
            ], className="align-items-center"),
        ], className="bg-transparent border-0 pt-3 pb-0"),

        dbc.CardBody([
            summary_badges,
            html.Small(f"Markets: {markets_str}",
                       className="text-muted d-block mb-3",
                       style={"fontSize": "0.75rem"}),

            dbc.Row([
                dbc.Col([
                    dbc.Label("Units", className="small fw-bold text-muted"),
                    dbc.Input(id={"type": "prof-units", "index": profile_id},
                              type="number", value=prof.get("units", 1.0),
                              step=0.1, size="sm"),
                ], width=12, className="mb-3"),
            ]),
            dbc.Row([
                dbc.Col(dbc.Label("Run Daily",
                                  className="small fw-bold text-muted mb-0"), width=8),
                dbc.Col(dbc.Checklist(
                    options=[{"label": "", "value": 1}],
                    value=[1] if prof.get("run_daily") else [],
                    id={"type": "prof-daily", "index": profile_id},
                    switch=True, inline=True,
                ), width=4, className="text-end"),
            ], className="align-items-center g-0 pt-3 border-top"),
        ]),
    ], className="shadow-sm border-0 mb-3 h-100")


def create_tips_table(df: pd.DataFrame) -> Any:
    """Create the betting tips DataTable."""
    if df.empty:
        return dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "No matches found matching your criteria"
        ], color="info", className="text-center m-4")

    def fmt(pct, odds):
        if odds is not None and odds >= 1:
            return f"{pct}%\n{odds:.2f}"
        return f"{pct}%"

    d = df.copy()
    d["home_d"]    = d.apply(lambda r: fmt(r.prob_home,     r.odds_home),     axis=1)
    d["draw_d"]    = d.apply(lambda r: fmt(r.prob_draw,     r.odds_draw),     axis=1)
    d["away_d"]    = d.apply(lambda r: fmt(r.prob_away,     r.odds_away),     axis=1)
    d["over_d"]    = d.apply(lambda r: fmt(r.prob_over,     r.odds_over),     axis=1)
    d["under_d"]   = d.apply(lambda r: fmt(r.prob_under,    r.odds_under),    axis=1)
    d["btts_y_d"]  = d.apply(lambda r: fmt(r.prob_btts_yes, r.odds_btts_yes), axis=1)
    d["btts_n_d"]  = d.apply(lambda r: fmt(r.prob_btts_no,  r.odds_btts_no),  axis=1)

    show = d[["match_id", "datetime_str", "home", "away", "sources",
              "prob_home",    "home_d",
              "prob_draw",    "draw_d",
              "prob_away",    "away_d",
              "prob_over",    "over_d",
              "prob_under",   "under_d",
              "prob_btts_yes","btts_y_d",
              "prob_btts_no", "btts_n_d"]].rename(columns={"datetime_str": "datetime"})

    return dash_table.DataTable(
        id={"type": "match-table", "index": "tips"},
        columns=[
            {"name": "",         "id": "match_id"},
            {"name": "Date",     "id": "datetime"},
            {"name": "Home",     "id": "home"},
            {"name": "Away",     "id": "away"},
            {"name": "Sources",  "id": "sources", "type": "numeric"},
            {"name": "1",        "id": "home_d"},
            {"name": "X",        "id": "draw_d"},
            {"name": "2",        "id": "away_d"},
            {"name": "O2.5",     "id": "over_d"},
            {"name": "U2.5",     "id": "under_d"},
            {"name": "BTTS Y",   "id": "btts_y_d"},
            {"name": "BTTS N",   "id": "btts_n_d"},
        ],
        data=show.to_dict("records"),
        sort_action="native", sort_mode="multi",
        style_table={
            'width': '100%',
            'minWidth': '100%',
        },
        style_cell={
            "textAlign": "center", "padding": "12px",
            "fontFamily": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            "fontSize": "13px", "whiteSpace": "pre-line", "height": "auto",
        },
        style_cell_conditional=[
            # 1. The ID Column (Hidden)
            {"if": {"column_id": "match_id"}, "display": "none"},
            
            # 2. The "Big Chunks" (Text Columns)
            {"if": {"column_id": "datetime"}, "width": "10%", "textAlign": "center"},
            {"if": {"column_id": "home"},     "width": "20%", "textAlign": "left", "paddingLeft": "15px"},
            {"if": {"column_id": "away"},     "width": "20%", "textAlign": "left"},
            
            # 3. The "Small Chunk" (Source)
            {"if": {"column_id": "sources"},  "width": "5%",  "textAlign": "center"},

            # 4. The Data Columns (Split Equally ~6.4% each)
            # We add the left borders here for visual grouping
            *[
                {
                    "if": {"column_id": col}, 
                    "width": "6.4%", 
                    "borderLeft": "2px solid #dee2e6" if col in ["home_d", "over_d", "btts_y_d"] else "none"
                }
                for col in ["home_d", "draw_d", "away_d", "over_d", "under_d", "btts_y_d", "btts_n_d"]
            ],
        ],
        style_header={
            "backgroundColor": "#764ba2", "color": "white",
            "fontWeight": "bold", "textAlign": "center",
            "padding": "14px", "border": "none",
        },
        style_data={
            "backgroundColor": "white", "border": "none",
            "borderBottom": "1px solid #e9ecef",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
            {"if": {"state": "active"},  "backgroundColor": "#f3e5f5",
             "border": "2px solid #764ba2"},
            # Green highlights ≥ 80 %
            *[
                {"if": {"filter_query": f"{{{prob}}} >= 80", "column_id": disp},
                 "backgroundColor": "#4ce770", "color": "#073F14", "fontWeight": "bold"}
                for prob, disp in [
                    ("prob_home", "home_d"), ("prob_draw", "draw_d"),
                    ("prob_away", "away_d"), ("prob_over", "over_d"),
                    ("prob_under", "under_d"), ("prob_btts_yes", "btts_y_d"),
                    ("prob_btts_no", "btts_n_d"),
                ]
            ],
        ],
        css=[{
            'selector': '.dash-spreadsheet td div',
            'rule': '''
                line-height: 1.2;
                display: block;
                overflow: hidden;
                text-overflow: ellipsis;
            '''
        }],
        page_size=25, page_action="native",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard class
# ─────────────────────────────────────────────────────────────────────────────

class BetAssistantDashboard:

    def __init__(self, db_path: str):
        self.db_manager     = DatabaseManager(db_path)
        self.betting_analyzer = BettingAnalyzer(self.db_manager)

        self.slips_path = os.path.join(os.path.dirname(db_path), "slips.db")
        self.slip_manager = BetSlipManager(self.slips_path)

        ensure_default_profiles()

        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
        )
        self.app.title = "Bet Assistant"
        self._setup_layout()
        self._setup_callbacks()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _setup_layout(self):
        self.app.layout = dbc.Container([
            # Stores
            dcc.Store(id="excluded-urls-store", data=[]),
            dcc.Store(id="matches-data-store"),
            dcc.Store(id="builder-last-selections", data=[]),  # flat list of picks

            # ── Header ────────────────────────────────────────────────────────
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H1([html.I(className="fas fa-chart-line me-3"), "Bet Assistant"],
                                className="fw-bold text-white mb-1",
                                style={"letterSpacing": "-1px"}),
                        dbc.Button([html.I(className="fas fa-sync-alt me-2"), "Refresh Data"],
                                   id="refresh-btn", className="ms-auto shadow-sm fw-bold me-2",
                                   style={"borderRadius": "10px",
                                          "background": "rgba(255,255,255,0.2)",
                                          "border": "1px solid rgba(255,255,255,0.3)"}),
                        dbc.Button([html.I(className="fas fa-cloud-download-alt me-2"), "Pull Update"],
                                   id="btn-pull-update", className="shadow-sm fw-bold",
                                   style={"borderRadius": "10px",
                                          "background": "rgba(255,193,7,0.4)",
                                          "border": "1px solid rgba(255,193,7,0.5)"}),
                    ], className="d-flex align-items-center p-4 shadow-lg",
                       style={"background": "linear-gradient(135deg, #4361ee 0%, #3f37c9 100%)",
                              "borderRadius": "20px", "marginTop": "20px"}),
                ])
            ], className="mb-4"),

            # ── Global Filters ────────────────────────────────────────────────
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Small("SEARCH", className="fw-bold text-muted mb-2 d-block",
                                       style={"fontSize": "0.7rem"}),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-search text-primary")),
                                dbc.Input(id="search-input", placeholder="Filter by team",
                                          className="border-start-0"),
                            ], className="shadow-sm rounded-3"),
                        ], lg=3, md=6),

                        dbc.Col([
                            html.Small("TIME HORIZON",
                                       className="fw-bold text-muted mb-2 d-block",
                                       style={"fontSize": "0.7rem"}),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-calendar-alt text-success")),
                                dbc.Input(id="date-from", type="date", className="border-end-0"),
                                dbc.Input(id="date-to",   type="date"),
                            ], className="shadow-sm rounded-3"),
                        ], lg=4, md=6),

                        dbc.Col(
                            html.Div(id="last-updated-text",
                                     className="text-muted small text-end mt-3"),
                            lg=5, md=12,
                        ),
                    ], className="g-2 align-items-end"),
                ], className="py-2"),
            ], className="shadow-sm mb-3 border-0"),

            # ── Tabs ──────────────────────────────────────────────────────────
            dbc.Card([
                dbc.CardBody([
                    dbc.Tabs(id="main-tabs", active_tab="tab-tips", children=[

                        # ── Tab 1: Betting Tips ──────────────────────────────
                        dbc.Tab(
                            html.Div(id="tips-table-container", className="py-4"),
                            label="Betting Tips", tab_id="tab-tips",
                            labelClassName="px-4 fw-bold",
                        ),

                        # ── Tab 2: Smart Builder ─────────────────────────────
                        dbc.Tab(
                            self._builder_tab_layout(),
                            label="Smart Builder", tab_id="tab-builder",
                            labelClassName="px-4 fw-bold",
                        ),

                        # ── Tab 3: Slips ─────────────────────────────────────
                        dbc.Tab(
                            self._slips_tab_layout(),
                            label="Slips", tab_id="tab-historic",
                            labelClassName="px-4 fw-bold",
                        ),

                        # ── Tab 4: Profiles ───────────────────────────────────
                        dbc.Tab(
                            self._profiles_tab_layout(),
                            label="Profiles", tab_id="tab-profiles",
                            labelClassName="px-4 fw-bold",
                        ),
                    ], className="nav-pills custom-tabs"),
                ], className="p-4"),
            ], className="border-0 shadow-lg mb-5", style={"borderRadius": "20px"}),

        ], fluid=True, className="px-lg-5",
           style={"backgroundColor": "#f8f9fe", "minHeight": "100vh"})

    def _builder_tab_layout(self) -> html.Div:
        return html.Div([
            dbc.Row([
                # ── Left: Config Panel ─────────────────────────────────────
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(
                            html.Small([html.I(className="fas fa-cog me-2 text-primary"),
                                        "Configuration"],
                                       className="fw-bold text-uppercase text-muted"),
                            className="bg-transparent border-0 py-2 px-3"
                        ),
                        dbc.CardBody(build_builder_panel(), className="pt-0 px-3 pb-3"),
                    ], className="shadow-sm border-0 rounded-3 h-100"),
                ], lg=4, className="mb-3"),

                # ── Right: Management + Preview ────────────────────────────
                dbc.Col([
                    # Management bar
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Row([
                                # Save profile
                                dbc.Col([
                                    dbc.InputGroup([
                                        dbc.InputGroupText(html.I(className="fas fa-save")),
                                        dbc.Input(id="builder-profile-name",
                                                  placeholder="Profile name...", size="sm"),
                                        dbc.Button("Save Profile",
                                                   id="save-profile-btn",
                                                   color="primary", size="sm"),
                                    ], className="shadow-sm"),
                                ], lg=5, className="mb-2 mb-lg-0"),

                                # Load profile
                                dbc.Col([
                                    dbc.InputGroup([
                                        dbc.InputGroupText("Load"),
                                        dbc.Select(id="builder-profile-selector",
                                                   options=[], size="sm"),
                                    ], className="shadow-sm"),
                                ], lg=4, className="mb-2 mb-lg-0"),

                                # Add to slips
                                dbc.Col([
                                    dbc.InputGroup([
                                        dbc.InputGroupText("Units"),
                                        dbc.Input(id="builder-units", type="number",
                                                  value=1.0, min=0.1, step=0.1, size="sm",
                                                  style={"maxWidth": "70px"}),
                                        dbc.Button([
                                            html.I(className="fas fa-plus-circle me-1"),
                                            "Add to Slips"
                                        ], id="btn-add-manual-slip",
                                           color="success", size="sm",
                                           className="fw-bold"),
                                    ], className="shadow-sm"),
                                ], lg=3),
                            ], className="g-2 align-items-center"),
                        ], className="py-2 px-3"),
                    ], className="shadow-sm border-0 rounded-3 mb-3"),

                    # Status message
                    html.Div(id="builder-status-msg", className="mb-2"),

                    # Preview
                    dbc.Card([
                        dbc.CardHeader(
                            html.Small([html.I(className="fas fa-eye me-2 text-primary"),
                                        "Live Preview — updates with every config change"],
                                       className="fw-bold text-uppercase text-muted"),
                            className="bg-transparent border-0 py-2 px-3"
                        ),
                        html.Hr(),
                        dbc.CardBody(
                            html.Div(id="builder-output-container"),
                            className="pt-0 px-3 pb-3"
                        ),
                    ], className="shadow-sm border-0 rounded-3"),
                ], lg=8),
            ], className="g-3 mt-2"),
        ], className="p-3")

    def _slips_tab_layout(self) -> html.Div:
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.InputGroup([
                            dbc.InputGroupText("Filter Profile:"),
                            dbc.Select(id="historic-profile-filter",
                                       options=[{"label": "📊 All Profiles", "value": "all"}],
                                       value="all", size="sm"),
                        ], className="shadow-sm", style={"width": "250px"}),

                        dbc.Button([html.I(className="fas fa-check-double me-2"),
                                    "Validate Results"],
                                   id="btn-force-refresh", color="primary",
                                   size="sm", className="ms-3 shadow-sm"),

                        dbc.Button([html.I(className="fas fa-magic me-2"),
                                    "Generate Slips"],
                                   id="btn-generate-slips", color="success",
                                   size="sm", className="ms-2 shadow-sm"),
                    ], className="d-flex align-items-center mb-4"),
                ]),
                dbc.Col([
                    dbc.Spinner(html.Div(id="refresh-status"), size="sm", color="primary")
                ], width="auto"),
            ]),
            dbc.Row(id="historic-stats-cards", className="mb-4 g-3"),
            html.Div(id="historic-slips-container"),
        ], className="p-3")

    def _profiles_tab_layout(self) -> html.Div:
        return html.Div([
            dbc.Row([
                dbc.Col(html.H5("Betting Strategies", className="mb-0 fw-bold"), width=8),
                dbc.Col(
                    dbc.Button([html.I(className="fas fa-plus me-2"), "Add Profile"],
                               id="add-profile-btn", color="primary", size="sm",
                               className="float-end shadow-sm"),
                    width=4
                ),
            ], className="mb-4 align-items-center"),

            dbc.Row(id="profiles-container", className="g-3"),

            html.Div([
                dbc.Button([html.I(className="fas fa-save me-2"), "Save All Profiles"],
                           id="save-config-btn", color="success",
                           className="shadow-sm px-4 mt-4"),
                html.Span(id="save-config-status", className="ms-3 fw-bold"),
            ], className="text-start"),
        ], className="p-4")

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _setup_callbacks(self):
        self._cb_refresh_data()
        self._cb_tips_table()
        self._cb_nullable_toggles()
        self._cb_builder_preview()
        self._cb_load_profile()
        self._cb_save_profile()
        self._cb_add_to_slips()
        self._cb_exclude_match()
        self._cb_profiles_tab()
        self._cb_save_all_profiles()
        self._cb_slips_tab()
        self._cb_pull_update()

    # ── Refresh data ──────────────────────────────────────────────────────────

    def _cb_refresh_data(self):
        @self.app.callback(
            Output("matches-data-store", "data"),
            Input("refresh-btn", "n_clicks"),
            prevent_initial_call=False,
        )
        def refresh_data(_):
            df = self.betting_analyzer.refresh_data()
            return df.to_json(date_format="iso", orient="split")

    # ── Tips table ────────────────────────────────────────────────────────────

    def _cb_tips_table(self):
        @self.app.callback(
            Output("tips-table-container", "children"),
            [Input("matches-data-store", "data"),
             Input("search-input",       "value"),
             Input("date-from",          "value"),
             Input("date-to",            "value")],
        )
        def update_tips_table(data_json, search_text, date_from, date_to):
            if not data_json:
                return dbc.Alert([
                    html.I(className="fas fa-info-circle me-2"),
                    "No data available. Click Refresh Data to load matches."
                ], color="warning", className="m-4")

            filtered = self.betting_analyzer.get_filtered_matches(
                search_text=search_text,
                date_from=date_from,
                date_to=date_to,
            )
            return create_tips_table(filtered)

    # ── Nullable field toggles ────────────────────────────────────────────────

    def _cb_nullable_toggles(self):
        for sw_id, col_id in [
            ("b-max-overflow-sw",  "b-max-overflow-collapse"),
            ("b-tolerance-sw",     "b-tolerance-collapse"),
            ("b-stop-sw",          "b-stop-collapse"),
        ]:
            @self.app.callback(
                Output(col_id, "is_open"),
                Input(sw_id, "value"),
            )
            def toggle_collapse(val):
                return bool(val)

    # ── Builder live preview ──────────────────────────────────────────────────

    def _cb_builder_preview(self):
        @self.app.callback(
            [Output("builder-output-container",  "children"),
             Output("builder-last-selections",   "data")],
            [Input("matches-data-store",        "data"),
             Input("main-tabs",                 "active_tab"),
             Input("date-from",                 "value"),
             Input("date-to",                   "value"),
             Input("excluded-urls-store",        "data"),
             # Bet shape
             Input("b-target-odds",             "value"),
             Input("b-target-legs",             "value"),
             Input("b-max-overflow-sw",         "value"),
             Input("b-max-overflow-val",        "value"),
             # Quality gate
             Input("b-prob-floor",              "value"),
             Input("b-min-odds",                "value"),
             # Markets
             Input("b-markets",                 "value"),
             # Tolerance & stop
             Input("b-tolerance-sw",            "value"),
             Input("b-tolerance-val",           "value"),
             Input("b-stop-sw",                 "value"),
             Input("b-stop-val",                "value"),
             Input("b-fill-ratio",              "value"),
             # Scoring
             Input("b-quality-vs-balance",      "value"),
             Input("b-prob-vs-sources",         "value")],
        )
        def update_builder_preview(
            data_json, active_tab, date_from, date_to, excluded_urls,
            target_odds, target_legs,
            max_overflow_sw, max_overflow_val,
            prob_floor, min_odds,
            markets,
            tolerance_sw, tolerance_val,
            stop_sw, stop_val,
            fill_ratio,
            quality_vs_balance, prob_vs_sources,
        ):
            if not data_json or active_tab != "tab-builder":
                return dash.no_update, dash.no_update

            # Resolve nullable fields
            max_overflow = int(max_overflow_val) if max_overflow_sw else None
            tolerance    = (tolerance_val / 100.0) if tolerance_sw else None
            stop_thr     = (stop_val / 100.0)      if stop_sw      else None

            # Markets: None when all selected = same behaviour, but cleaner YAML
            included_markets = None if set(markets or []) == set(ALL_MARKET_TYPES) else (markets or [])

            cfg = BetSlipConfig(
                date_from=date_from,
                date_to=date_to,
                excluded_urls=excluded_urls or None,
                included_market_types=included_markets,
                target_odds=float(target_odds or 3.0),
                target_legs=int(target_legs or 3),
                max_legs_overflow=max_overflow,
                probability_floor=float(prob_floor or 55.0),
                min_odds=float(min_odds or 1.05),
                tolerance_factor=tolerance,
                stop_threshold=stop_thr,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0,
            )

            selections = self.betting_analyzer.build_bet_slip(cfg)
            preview = render_bet_preview(selections)
            return preview, selections

    # ── Load profile into builder ─────────────────────────────────────────────

    def _cb_load_profile(self):
        @self.app.callback(
            [Output("b-target-odds",           "value"),
             Output("b-target-legs",           "value"),
             Output("b-max-overflow-sw",       "value"),
             Output("b-max-overflow-val",      "value"),
             Output("b-prob-floor",            "value"),
             Output("b-min-odds",              "value"),
             Output("b-markets",               "value"),
             Output("b-tolerance-sw",          "value"),
             Output("b-tolerance-val",         "value"),
             Output("b-stop-sw",               "value"),
             Output("b-stop-val",              "value"),
             Output("b-fill-ratio",            "value"),
             Output("b-quality-vs-balance",    "value"),
             Output("b-prob-vs-sources",       "value"),
             Output("builder-profile-name",    "value")],
            Input("builder-profile-selector", "value"),
            prevent_initial_call=True,
        )
        def load_profile(profile_name):
            no = dash.no_update
            if not profile_name:
                return [no] * 16

            prof = settings_manager.get_config(profile_name)
            if not prof:
                return [no] * 16

            mkt_raw = prof.get("included_market_types")
            markets = mkt_raw if mkt_raw else ALL_MARKET_TYPES

            tol_raw  = prof.get("tolerance_factor")
            stop_raw = prof.get("stop_threshold")
            ovf_raw  = prof.get("max_legs_overflow")

            return [
                prof.get("target_odds",         3.0),
                prof.get("target_legs",         3),
                [1] if ovf_raw is not None else [],
                int(ovf_raw) if ovf_raw is not None else 1,
                prof.get("probability_floor",   55.0),
                prof.get("min_odds",            1.05),
                markets,
                [1] if tol_raw is not None else [],
                int((tol_raw or 0.25) * 100),
                [1] if stop_raw is not None else [],
                int((stop_raw or 0.91) * 100),
                int(prof.get("min_legs_fill_ratio", 0.70) * 100),
                int(prof.get("quality_vs_balance", 0.5) * 100),
                int(prof.get("prob_vs_sources",    0.5) * 100),
                profile_name,
            ]

    # ── Save builder config as profile ───────────────────────────────────────

    def _cb_save_profile(self):
        @self.app.callback(
            Output("builder-status-msg", "children"),
            Input("save-profile-btn", "n_clicks"),
            [State("builder-profile-name",   "value"),
             State("b-target-odds",          "value"),
             State("b-target-legs",          "value"),
             State("b-max-overflow-sw",      "value"),
             State("b-max-overflow-val",     "value"),
             State("b-prob-floor",           "value"),
             State("b-min-odds",             "value"),
             State("b-markets",              "value"),
             State("b-tolerance-sw",         "value"),
             State("b-tolerance-val",        "value"),
             State("b-stop-sw",              "value"),
             State("b-stop-val",             "value"),
             State("b-fill-ratio",           "value"),
             State("b-quality-vs-balance",   "value"),
             State("b-prob-vs-sources",      "value")],
            prevent_initial_call=True,
        )
        def save_profile(n, name,
                         target_odds, target_legs,
                         max_overflow_sw, max_overflow_val,
                         prob_floor, min_odds,
                         markets,
                         tolerance_sw, tolerance_val,
                         stop_sw, stop_val,
                         fill_ratio,
                         quality_vs_balance, prob_vs_sources):
            if not n:
                return dash.no_update
            if not name:
                return dbc.Alert("Profile name is required.", color="danger", dismissable=True)

            clean = "".join(c for c in name if c.isalnum() or c in ("_", "-")).lower()

            included_markets = (
                None if set(markets or []) == set(ALL_MARKET_TYPES) else (markets or [])
            )

            cfg = BetSlipConfig(
                date_from=None, date_to=None, excluded_urls=None,
                included_market_types=included_markets,
                target_odds=float(target_odds or 3.0),
                target_legs=int(target_legs or 3),
                max_legs_overflow=int(max_overflow_val) if max_overflow_sw else None,
                probability_floor=float(prob_floor or 55.0),
                min_odds=float(min_odds or 1.05),
                tolerance_factor=(tolerance_val / 100.0) if tolerance_sw else None,
                stop_threshold=(stop_val / 100.0) if stop_sw else None,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0
            )

            # Preserve existing units/run_daily if the profile already exists
            existing = settings_manager.get_config(clean) or {}
            data = config_to_yaml_dict(
                cfg,
                units=existing.get("units", 1.0),
                run_daily=existing.get("run_daily", False),
            )

            if settings_manager.write_settings(clean, data, config_dir="config/profiles"):
                return dbc.Alert(f"✅ Profile '{clean}' saved!", color="success", dismissable=True)
            return dbc.Alert("❌ Failed to save profile.", color="danger", dismissable=True)

    # ── Add to Slips ──────────────────────────────────────────────────────────
    def _cb_add_to_slips(self):
        @self.app.callback(
            Output("builder-status-msg", "children", allow_duplicate=True),
            Input("btn-add-manual-slip", "n_clicks"),
            [State("builder-last-selections", "data"),
            State("builder-profile-name",    "value"),
            State("builder-units",           "value")],
            prevent_initial_call=True,
        )
        def add_to_slips(n, selections, profile_name, units):
            if not n:
                return dash.no_update
            if not selections:
                return dbc.Alert("No slip to add — preview must have selections first.",
                                color="warning", dismissable=True)

            profile   = (profile_name or "manual").strip() or "manual"
            units_val = float(units or 1.0)

            try:
                slip_id = self.slip_manager.insert_slip(
                    profile=profile,
                    legs_list=selections,   # each item already has match/market/market_type/odds/result_url
                    units=units_val,
                )
                total_odds = 1.0
                for s in selections:
                    total_odds *= s.get("odds", 1.0)

                return dbc.Alert(
                    f"✅ Slip #{slip_id} added to '{profile}' — "
                    f"{len(selections)} legs @ {total_odds:.2f} ({units_val}u)",
                    color="success", dismissable=True,
                )
            except Exception as e:
                return dbc.Alert(f"❌ Failed to add slip: {e}", color="danger", dismissable=True)

    # ── Exclude match from builder ────────────────────────────────────────────

    def _cb_exclude_match(self):
        @self.app.callback(
            Output("excluded-urls-store", "data"),
            Input({"type": "exclude-btn", "index": ALL}, "n_clicks"),
            State("excluded-urls-store", "data"),
            prevent_initial_call=True,
        )
        def exclude_match(n_clicks_list, current_excluded):
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            prop = ctx.triggered[0]["prop_id"]
            if ".n_clicks" not in prop:
                return dash.no_update

            try:
                triggered_id = json.loads(prop.split(".n_clicks")[0])
                url = triggered_id["index"]
            except Exception:
                return dash.no_update

            # Find which index was actually clicked
            for i, inp in enumerate(ctx.inputs_list[0]):
                if inp["id"]["index"] == url:
                    if not n_clicks_list[i]:
                        return dash.no_update
                    break
            else:
                return dash.no_update

            current_excluded = current_excluded or []
            if url not in current_excluded:
                return current_excluded + [url]
            return dash.no_update

    # ── Profiles tab ──────────────────────────────────────────────────────────

    def _cb_profiles_tab(self):
        @self.app.callback(
            [Output("profiles-container",        "children"),
             Output("builder-profile-selector",  "options")],
            [Input("main-tabs",                  "active_tab"),
             Input("add-profile-btn",            "n_clicks"),
             Input({"type": "delete-profile-btn", "index": ALL}, "n_clicks")],
            State("profiles-container", "children"),
            prevent_initial_call=False,
        )
        def render_profiles(active_tab, n_add, n_delete_list, _):
            ctx = dash.callback_context
            triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            settings_manager.load_settings("config/profiles")
            profiles = {
                name: cfg
                for name, cfg in settings_manager.configs.items()
                if os.path.exists(f"config/profiles/{name}.yaml")
            }

            # Deletion
            if "delete-profile-btn" in triggered:
                try:
                    btn_id = json.loads(triggered.split(".n_clicks")[0])
                    pid = btn_id["index"]
                    path = f"config/profiles/{pid}.yaml"
                    if os.path.exists(path):
                        os.remove(path)
                    profiles.pop(pid, None)
                    settings_manager.configs.pop(pid, None)
                except Exception:
                    pass

            # Addition
            if triggered == "add-profile-btn.n_clicks" and n_add:
                new_id = f"profile_{n_add}"
                cfg = BetSlipConfig()
                data = config_to_yaml_dict(cfg, units=1.0, run_daily=False)
                settings_manager.write_settings(new_id, data, config_dir="config/profiles")
                profiles[new_id] = data

            cards = [
                dbc.Col(render_profile_card(pid, pdata), lg=4, md=6, xs=12)
                for pid, pdata in profiles.items()
            ]
            options = [{"label": f"👤 {pid.upper()}", "value": pid} for pid in profiles]
            return cards, options

    # ── Save all profiles (units + run_daily) ─────────────────────────────────

    def _cb_save_all_profiles(self):
        @self.app.callback(
            [Output("save-config-status", "children"),
             Output("save-config-status", "className")],
            Input("save-config-btn", "n_clicks"),
            [State({"type": "prof-units", "index": ALL}, "value"),
             State({"type": "prof-daily", "index": ALL}, "value"),
             State({"type": "prof-units", "index": ALL}, "id")],
            prevent_initial_call=True,
        )
        def save_all_profiles(n, units_list, daily_list, ids_list):
            if not n:
                return "", ""

            success_all = True
            for i, item in enumerate(ids_list):
                pid = item["index"]
                current = settings_manager.get_config(pid) or {}
                current.update({
                    "units":     units_list[i],
                    "run_daily": (1 in daily_list[i]) if daily_list[i] else False,
                })
                if not settings_manager.write_settings(pid, current, config_dir="config/profiles"):
                    success_all = False

            if success_all:
                return "✅ All profiles saved", "ms-3 fw-bold text-success"
            return "❌ Some profiles failed to save", "ms-3 fw-bold text-danger"

    # ── Slips tab ─────────────────────────────────────────────────────────────

    def _cb_slips_tab(self):
        @self.app.callback(
            [Output("historic-stats-cards",     "children"),
             Output("historic-slips-container", "children"),
             Output("historic-profile-filter",  "options"),
             Output("refresh-status",           "children")],
            [Input("main-tabs",             "active_tab"),
             Input("historic-profile-filter", "value"),
             Input("btn-force-refresh",     "n_clicks"),
             Input("btn-generate-slips",    "n_clicks")],
            prevent_initial_call=True,
        )
        def update_slips_tab(active_tab, profile_filter, n_validate, n_generate):
            ctx = dash.callback_context
            triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

            refresh_msg = dash.no_update

            if triggered == "btn-force-refresh":
                try:
                    subprocess.run(
                        [sys.executable, "-m", "main", "--mode", "validate-slips",
                         "--db_path", self.slips_path],
                        capture_output=True, text=True, check=True,
                    )
                    refresh_msg = html.Span("✅ Validation done", className="text-success ms-2",
                                            style={"fontSize": "0.8rem"})
                except subprocess.CalledProcessError as e:
                    refresh_msg = html.Span("❌ Validation failed", className="text-danger ms-2",
                                            style={"fontSize": "0.8rem"})

            elif triggered == "btn-generate-slips":
                try:
                    subprocess.run(
                        [sys.executable, "-m", "main", "--mode", "generate-slips",
                         "--db_path", self.db_manager.db_path],
                        capture_output=True, text=True, check=True,
                    )
                    refresh_msg = html.Span("✅ Generation done", className="text-success ms-2",
                                            style={"fontSize": "0.8rem"})
                except subprocess.CalledProcessError as e:
                    refresh_msg = html.Span("❌ Generation failed", className="text-danger ms-2",
                                            style={"fontSize": "0.8rem"})

            if active_tab != "tab-historic":
                return dash.no_update, dash.no_update, dash.no_update, refresh_msg

            stats = self.slip_manager.get_historic_stats(profile_filter=profile_filter)
            slips = self.slip_manager.get_all_slips_with_legs(profile_filter=profile_filter)

            stats_ui = render_stats_cards(stats)
            slips_ui = (
                [render_slip_card(s) for s in slips]
                if slips
                else [dbc.Alert(f"No {profile_filter} slips found.", color="info")]
            )

            profile_names = [p.stem for p in Path("config/profiles").glob("*.yaml")]
            options = (
                [{"label": "📊 All Profiles", "value": "all"}] +
                [{"label": f"👤 {n.upper()}", "value": n} for n in profile_names]
            )

            return stats_ui, slips_ui, options, refresh_msg

    # ── Pull DB update ────────────────────────────────────────────────────────

    def _cb_pull_update(self):
        @self.app.callback(
            [Output("last-updated-text",  "children"),
             Output("refresh-btn",        "n_clicks")],
            Input("btn-pull-update", "n_clicks"),
            State("refresh-btn",     "n_clicks"),
            prevent_initial_call=True,
        )
        def pull_update(n, current_clicks):
            if not n:
                return dash.no_update, dash.no_update
            try:
                repo     = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
                artifact = os.environ.get("ARTIFACT_NAME", "final-database")
                cmd = (f"rm -f /app/data/final_matches.db* && "
                       f"gh run download -R {repo} -n {artifact} --dir /app/data")
                subprocess.run(cmd, shell=True, check=True)
                return "Pull successful", (current_clicks or 0) + 1
            except Exception as e:
                return f"Pull failed: {e}", dash.no_update

    # ── Run ────────────────────────────────────────────────────────────────────

    def run(self, debug: bool = True, port: int = 8050):
        print(f"Starting dashboard on http://0.0.0.0:{port}")
        self.app.run(debug=debug, host="0.0.0.0", port=port)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Bet Assistant Dashboard")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    args = parser.parse_args()

    settings_manager.load_settings("config")
    if os.path.exists("config/profiles"):
        settings_manager.load_settings("config/profiles")

    dashboard = BetAssistantDashboard(args.db_path)
    dashboard.run()