"""
dashboard/components.py
════════════════════════
Pure, stateless UI component builders.

Every function here takes plain data and returns a Dash component tree.
No callbacks, no imports from logic.py, no side-effects.
All visual tokens are sourced from constants.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table
import pandas as pd

from dashboard.constants import (
    ALL_MARKET_TYPES,
    CHART_COLORS,
    COLORS,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    LEG_ICON,
    LEG_ICON_DEFAULT,
    RADIUS_MD,
    RADIUS_SM,
    SHADOW_SM,
    STATUS_STYLES,
    STATUS_STYLES_DEFAULT,
    STYLE_CARD,
    STYLE_LIVE_BADGE,
    STYLE_TOOLTIP_ICON,
    TABLE_STYLE_CELL,
    TABLE_STYLE_DATA,
    TABLE_STYLE_HEADER,
    TOOLTIP_TEXTS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Micro helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_tooltip(field_id: str, text: str) -> html.Span:
    """Small (?) icon with a hover popover."""
    tip_id = f"tip-{field_id}"
    return html.Span([
        html.Span("?", id=tip_id, className="ms-1 text-muted fw-bold",
                  style=STYLE_TOOLTIP_ICON),
        dbc.Tooltip(text, target=tip_id, placement="right",
                    style={"fontSize": FONT_SIZE_SM, "maxWidth": "300px",
                           "whiteSpace": "pre-wrap"}),
    ])


def make_labeled_row(label: str, field_id: str, control: Any) -> dbc.Row:
    """Label + (?) icon on the left, control on the right."""
    return dbc.Row([
        dbc.Col([
            html.Small(label, className="fw-bold text-muted"),
            make_tooltip(field_id, TOOLTIP_TEXTS.get(field_id, "")),
        ], width=5, className="d-flex align-items-center"),
        dbc.Col(control, width=7),
    ], className="mb-2 align-items-center g-1")


def make_nullable_row(
    label:         str,
    field_id:      str,
    switch_id:     str,
    collapse_id:   str,
    inner_control: Any,
    enabled:       bool = False,
) -> html.Div:
    """Config row that can be toggled between Auto (None) and Manual."""
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
                    switch=True, inline=True, className="mb-0",
                )
            ], width=5, className="text-end"),
        ], className="align-items-center g-1"),
        dbc.Collapse(
            html.Div(inner_control,
                     className="mt-1 ps-2 border-start border-2 border-primary-subtle"),
            id=collapse_id,
            is_open=enabled,
        ),
    ], className="mb-2")


def build_config_section(title: str, icon: str, children: list) -> dbc.Card:
    """Titled card section for the builder panel."""
    return dbc.Card([
        dbc.CardHeader(
            html.Small([html.I(className=f"fas {icon} me-2 text-primary"), title],
                       className="fw-bold text-uppercase text-muted"),
            className="bg-transparent border-0 py-2 px-3",
        ),
        dbc.CardBody(children, className="py-2 px-3"),
    ], className="border-0 bg-light rounded-3 mb-2")


# ─────────────────────────────────────────────────────────────────────────────
# Builder panel
# ─────────────────────────────────────────────────────────────────────────────

def build_builder_panel() -> html.Div:
    """Full configuration panel for the Smart Builder tab."""

    shape_section = build_config_section("Bet Shape", "fa-layer-group", [
        make_labeled_row("Target Odds", "target_odds",
            dbc.Input(id="b-target-odds", type="number",
                      value=3.0, min=1.1, max=1000.0, step=0.1, size="sm")),
        make_labeled_row("Target Legs", "target_legs",
            dbc.Input(id="b-target-legs", type="number",
                      value=3, min=1, max=10, step=1, size="sm")),
        make_nullable_row(
            "Max Overflow Legs", "max_legs_overflow",
            switch_id="b-max-overflow-sw", collapse_id="b-max-overflow-collapse",
            inner_control=dbc.Row([
                dbc.Col(html.Small("Extra legs allowed:", className="text-muted"), width=7),
                dbc.Col(dbc.Input(id="b-max-overflow-val", type="number",
                                  value=1, min=0, max=5, step=1, size="sm"), width=5),
            ], className="align-items-center g-1"),
        ),
    ])

    quality_section = build_config_section("Quality Gate", "fa-filter", [
        make_labeled_row("Probability Floor", "probability_floor",
            dcc.Slider(id="b-prob-floor", min=0, max=100, step=1, value=55,
                       marks={0: "0%", 50: "50%", 75: "75%", 100: "100%"},
                       tooltip={"placement": "bottom", "always_visible": True})),
        make_labeled_row("Min Odds", "min_odds",
            dbc.Input(id="b-min-odds", type="number",
                      value=1.05, min=1.01, max=10.0, step=0.01, size="sm")),
    ])

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
                    style={"fontSize": FONT_SIZE_MD},
                ), width=7,
            ),
        ], className="align-items-start g-1"),
    ])

    tol_section = build_config_section("Tolerance & Stop", "fa-crosshairs", [
        make_nullable_row(
            "Tolerance Factor", "tolerance_factor",
            switch_id="b-tolerance-sw", collapse_id="b-tolerance-collapse",
            inner_control=html.Div([
                html.Small("±% band around ideal odds per leg:", className="text-muted"),
                dcc.Slider(id="b-tolerance-val", min=5, max=80, step=1, value=25,
                           marks={5: "5%", 25: "25%", 50: "50%", 80: "80%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ]),
        ),
        make_nullable_row(
            "Stop Threshold", "stop_threshold",
            switch_id="b-stop-sw", collapse_id="b-stop-collapse",
            inner_control=html.Div([
                html.Small("Stop when odds reach X% of target:", className="text-muted"),
                dcc.Slider(id="b-stop-val", min=50, max=100, step=1, value=91,
                           marks={50: "50%", 80: "80%", 95: "95%", 100: "100%"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ]),
        ),
        make_labeled_row("Min Legs Fill Ratio", "min_legs_fill_ratio",
            dcc.Slider(id="b-fill-ratio", min=50, max=100, step=5, value=70,
                       marks={50: "50%", 70: "70%", 100: "100%"},
                       tooltip={"placement": "bottom", "always_visible": True})),
    ])

    scoring_section = build_config_section("Scoring", "fa-sliders-h", [
        make_labeled_row("Quality vs Balance", "quality_vs_balance",
            html.Div([
                html.Div([
                    html.Small("← Balance", className="text-muted",
                               style={"fontSize": FONT_SIZE_XS}),
                    html.Small("Quality →", className="text-muted float-end",
                               style={"fontSize": FONT_SIZE_XS}),
                ]),
                dcc.Slider(id="b-quality-vs-balance", min=0, max=100, step=5, value=50,
                           marks={0: "0", 50: "50", 100: "100"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])),
        make_labeled_row("Prob vs Sources", "prob_vs_sources",
            html.Div([
                html.Div([
                    html.Small("← Sources", className="text-muted",
                               style={"fontSize": FONT_SIZE_XS}),
                    html.Small("Prob →", className="text-muted float-end",
                               style={"fontSize": FONT_SIZE_XS}),
                ]),
                dcc.Slider(id="b-prob-vs-sources", min=0, max=100, step=5, value=50,
                           marks={0: "0", 50: "50", 100: "100"},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ])),
    ])

    return html.Div([shape_section, quality_section, markets_section,
                     tol_section, scoring_section])


# ─────────────────────────────────────────────────────────────────────────────
# Bet preview
# ─────────────────────────────────────────────────────────────────────────────

def render_bet_preview(selections: list) -> html.Div:
    """
    Render the bet-slip preview from the flat list returned by build_slip().
    Each item: {match, market, market_type, prob, odds, result_url, sources, tier, score}
    """
    if not selections:
        return dbc.Alert("No matches meet criteria with current settings.", color="warning")

    total_odds   = 1.0
    tier2_count  = 0
    for s in selections:
        total_odds  *= s.get("odds", 1.0)
        if s.get("tier", 1) == 2:
            tier2_count += 1

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

    cards = []
    for pick in selections:
        conf       = pick["prob"]
        conf_color = "success" if conf >= 80 else "warning" if conf >= 60 else "danger"
        tier       = pick.get("tier", 1)
        score      = pick.get("score", 0.0)

        tier_badge = dbc.Badge(
            "✓ Balanced" if tier == 1 else "⚠ Drift",
            color="success" if tier == 1 else "warning",
            className="me-1",
            style={"fontSize": FONT_SIZE_XS},
        )
        score_badge = dbc.Badge(
            f"Score {score:.2f}",
            color="light", text_color="dark",
            style={"fontSize": FONT_SIZE_XS},
        )

        card = dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(
                            html.H6(pick["match"], className="fw-bold text-dark mb-0",
                                    style={"fontSize": "0.95rem"}),
                            width=10,
                        ),
                        dbc.Col(
                            dbc.Button(
                                html.I(className="fas fa-times"),
                                id={"type": "exclude-btn", "index": pick["result_url"]},
                                color="link", size="sm",
                                className="p-0 text-muted text-decoration-none",
                            ),
                            width=2, className="text-end",
                        ),
                    ], className="mb-2 align-items-center"),

                    dbc.Row([
                        dbc.Col(
                            html.Span(pick["market"], className="fw-bold fs-6"), width=8),
                        dbc.Col(
                            dbc.Badge(f"@{pick['odds']:.2f}",
                                      color="primary", className="fs-6 float-end"),
                            width=4,
                        ),
                    ], className="align-items-center mb-2"),

                    dbc.Progress(value=conf, color=conf_color,
                                 style={"height": "6px"}, className="rounded-pill mb-1"),

                    html.Div([
                        html.Small(f"Conf: {conf}%",
                                   className=f"fw-bold text-{conf_color} me-2",
                                   style={"fontSize": FONT_SIZE_XS}),
                        html.Small(f"Sources: {pick.get('sources', 0)}",
                                   className="text-muted me-2",
                                   style={"fontSize": FONT_SIZE_XS}),
                        tier_badge,
                        score_badge,
                    ], className="d-flex align-items-center flex-wrap"),
                ], className="p-2"),
            ], className="shadow-sm border-0 rounded-3 h-100",
               style={"backgroundColor": COLORS["bg_light"]}),
            xs=12, lg=6, className="mb-3",
        )
        cards.append(card)

    return html.Div([summary, dbc.Row(cards, className="g-2")])


# ─────────────────────────────────────────────────────────────────────────────
# Stats cards
# ─────────────────────────────────────────────────────────────────────────────

def render_stats_cards(stats: dict) -> list:
    """Row of summary metric cards for the Slips tab header."""
    bal_color = "success" if stats["net_profit"] >= 0 else "danger"
    roi_color = "success" if stats["roi_percentage"] >= 0 else "danger"

    def _card(title, value, color, size="H4", col_size=(2, 4, 6)):
        return dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6(title, className="text-muted text-uppercase mb-1",
                        style={"fontSize": FONT_SIZE_XS}),
                getattr(html, size)(value, className=f"mb-0 fw-bold text-{color}"),
            ]),
        ], className="border-0 shadow-sm rounded-3"), lg=col_size[0], md=col_size[1], xs=col_size[2])

    return [
        _card("Total Bet",    f"{stats['total_units_bet']} Units", "primary"),
        _card("Gross Return", f"{stats['gross_return']} Units",    "success"),
        _card("Net Profit",   f"{stats['net_profit']:+g} U",       bal_color, "H3", (3, 4, 12)),
        _card("Win Rate",     f"{stats['win_rate']}%",             "info"),
        _card("ROI %",        f"{stats['roi_percentage']}%",       roi_color),
        _card("Settled",      str(stats["total_settled"]),          "dark", "H4", (1, 4, 6)),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Slip card  (with live match awareness)
# ─────────────────────────────────────────────────────────────────────────────

def render_slip_card(
    slip:      dict,
    live_data: Optional[Dict[str, dict]] = None,
) -> dbc.Card:
    """
    Render one historical / active slip card.

    Parameters
    ----------
    slip       : Slip dict as returned by DashboardLogic.get_slips().
    live_data  : Optional dict keyed by match_name → {score, minute}.
                 When provided, legs with Live status will show a score badge
                 and match minute.
    """
    live_data = live_data or {}

    status_style = STATUS_STYLES.get(slip["slip_status"], STATUS_STYLES_DEFAULT)
    hdr_bg    = status_style["bg"]
    txt_cls   = status_style["text"]
    badge_col = status_style["badge"]

    leg_rows = []
    for leg in slip["legs"]:
        leg_status = leg["status"]
        icon_cls   = LEG_ICON.get(leg_status, LEG_ICON_DEFAULT)

        # ── Live match overlay ─────────────────────────────────────────────
        live_info   = live_data.get(leg["match_name"])
        live_badges = []
        if live_info and leg_status == "Live":
            if live_info.get("score"):
                live_badges.append(
                    html.Span(
                        live_info["score"],
                        style={**STYLE_LIVE_BADGE, "marginLeft": "6px"},
                    )
                )
            if live_info.get("minute"):
                live_badges.append(
                    html.Span(
                        live_info["minute"],
                        style={
                            "backgroundColor": COLORS["warning"],
                            "color": COLORS["text_dark"],
                            "borderRadius": RADIUS_SM,
                            "padding": "2px 6px",
                            "fontSize": FONT_SIZE_XS,
                            "fontWeight": "bold",
                            "marginLeft": "4px",
                        },
                    )
                )

        match_cell = html.Span([
            html.A(
                leg["match_name"],
                href=leg["result_url"],
                target="_blank",
                className="fw-medium text-decoration-none",
                style={
                    "fontSize": FONT_SIZE_MD,
                    "color":    COLORS["accent"],
                    "cursor":   "pointer",
                },
            ),
            *live_badges,
        ], className="d-flex align-items-center flex-wrap gap-1")

        leg_rows.append(
            dbc.Row([
                dbc.Col(html.I(className=f"fas {icon_cls}"),
                        width=1, className="text-center"),
                dbc.Col(match_cell, width=6),
                dbc.Col(html.Span(leg["market"],
                                  style={"fontSize": "0.8rem"}), width=3),
                dbc.Col(html.Span(f"@{leg['odds']:.2f}",
                                  className="fw-bold text-end",
                                  style={"fontSize": FONT_SIZE_MD}),
                        width=2, className="text-end"),
            ], className="py-2 border-bottom align-items-center g-0")
        )

    return dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col(html.Strong(f"Date: {slip['date_generated']}"), width=4),
                dbc.Col(html.Span(f"Profile: {slip['profile'].upper()}",
                                  className="fw-bold"), width=3),
                dbc.Col(html.Span(f"Total Odds: @{slip['total_odds']:.2f}",
                                  className="fw-bold"),
                        width=3, className="text-end"),
                dbc.Col(dbc.Badge(slip["slip_status"], color=badge_col,
                                  className="float-end"), width=2),
            ], className="align-items-center"),
        ], style={"backgroundColor": hdr_bg}, className="border-bottom-0"),
        dbc.CardBody(leg_rows, className="p-2"),
    ], className="mb-3 shadow-sm border-0")


# ─────────────────────────────────────────────────────────────────────────────
# Profile card
# ─────────────────────────────────────────────────────────────────────────────

def render_profile_card(profile_id: str, prof: dict) -> dbc.Card:
    """Profile card for the Profiles tab."""
    def _param_badge(label, value):
        return dbc.Badge(f"{label}: {value}", color="light", text_color="dark",
                         className="me-1 mb-1", style={"fontSize": FONT_SIZE_XS})

    summary_badges = html.Div([
        _param_badge("Odds",     prof.get("target_odds",  "—")),
        _param_badge("Legs",     prof.get("target_legs",  "—")),
        _param_badge("ProbFloor",f"{prof.get('probability_floor', '—')}%"),
        _param_badge("Q/B",      prof.get("quality_vs_balance", "—")),
        _param_badge("P/S",      prof.get("prob_vs_sources", "—")),
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
                    width=3, className="text-end",
                ),
            ], className="align-items-center"),
        ], className="bg-transparent border-0 pt-3 pb-0"),

        dbc.CardBody([
            summary_badges,
            html.Small(f"Markets: {markets_str}",
                       className="text-muted d-block mb-3",
                       style={"fontSize": FONT_SIZE_SM}),
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


# ─────────────────────────────────────────────────────────────────────────────
# Tips DataTable
# ─────────────────────────────────────────────────────────────────────────────

def create_tips_table(df: pd.DataFrame) -> Any:
    """Create the betting tips DataTable from the match DataFrame."""
    if df.empty:
        return dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "No matches found matching your criteria",
        ], color="info", className="text-center m-4")

    def fmt(pct, odds):
        if odds is not None and odds >= 1:
            return f"{pct}%\n{odds:.2f}"
        return f"{pct}%"

    d = df.copy()
    d["home_d"]   = d.apply(lambda r: fmt(r.prob_home,     r.odds_home),     axis=1)
    d["draw_d"]   = d.apply(lambda r: fmt(r.prob_draw,     r.odds_draw),     axis=1)
    d["away_d"]   = d.apply(lambda r: fmt(r.prob_away,     r.odds_away),     axis=1)
    d["over_d"]   = d.apply(lambda r: fmt(r.prob_over,     r.odds_over),     axis=1)
    d["under_d"]  = d.apply(lambda r: fmt(r.prob_under,    r.odds_under),    axis=1)
    d["btts_y_d"] = d.apply(lambda r: fmt(r.prob_btts_yes, r.odds_btts_yes), axis=1)
    d["btts_n_d"] = d.apply(lambda r: fmt(r.prob_btts_no,  r.odds_btts_no),  axis=1)

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
            {"name": "",        "id": "match_id"},
            {"name": "Date",    "id": "datetime"},
            {"name": "Home",    "id": "home"},
            {"name": "Away",    "id": "away"},
            {"name": "Sources", "id": "sources", "type": "numeric"},
            {"name": "1",       "id": "home_d"},
            {"name": "X",       "id": "draw_d"},
            {"name": "2",       "id": "away_d"},
            {"name": "O2.5",    "id": "over_d"},
            {"name": "U2.5",    "id": "under_d"},
            {"name": "BTTS Y",  "id": "btts_y_d"},
            {"name": "BTTS N",  "id": "btts_n_d"},
        ],
        data=show.to_dict("records"),
        sort_action="native", sort_mode="multi",
        style_table={"width": "100%", "minWidth": "100%"},
        style_cell=TABLE_STYLE_CELL,
        style_cell_conditional=[
            {"if": {"column_id": "match_id"}, "display": "none"},
            {"if": {"column_id": "datetime"}, "width": "10%", "textAlign": "center"},
            {"if": {"column_id": "home"},     "width": "20%", "textAlign": "left",
             "paddingLeft": "15px"},
            {"if": {"column_id": "away"},     "width": "20%", "textAlign": "left"},
            {"if": {"column_id": "sources"},  "width": "5%",  "textAlign": "center"},
            *[
                {
                    "if": {"column_id": col},
                    "width": "6.4%",
                    "borderLeft": "2px solid #dee2e6"
                    if col in ("home_d", "over_d", "btts_y_d") else "none",
                }
                for col in ("home_d", "draw_d", "away_d", "over_d",
                            "under_d", "btts_y_d", "btts_n_d")
            ],
        ],
        style_header=TABLE_STYLE_HEADER,
        style_data=TABLE_STYLE_DATA,
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": COLORS["bg_light"]},
            {"if": {"state": "active"},
             "backgroundColor": "#f3e5f5", "border": f"2px solid {COLORS['accent']}"},
            *[
                {"if": {"filter_query": f"{{{prob}}} >= 80", "column_id": disp},
                 "backgroundColor": "#4ce770", "color": "#073F14", "fontWeight": "bold"}
                for prob, disp in [
                    ("prob_home",    "home_d"),  ("prob_draw",    "draw_d"),
                    ("prob_away",    "away_d"),  ("prob_over",    "over_d"),
                    ("prob_under",   "under_d"), ("prob_btts_yes","btts_y_d"),
                    ("prob_btts_no", "btts_n_d"),
                ]
            ],
        ],
        css=[{
            "selector": ".dash-spreadsheet td div",
            "rule": "line-height:1.2;display:block;overflow:hidden;text-overflow:ellipsis;",
        }],
        page_size=25, page_action="native",
    )