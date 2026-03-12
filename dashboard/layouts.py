"""
dashboard/layouts.py
═════════════════════
Layout builders for every tab and the main page frame.

All functions are pure — they return Dash component trees.
Callbacks are wired in app.py.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dashboard.components import build_builder_panel
from dashboard.constants import COLORS, RADIUS_LG, SHADOW_LG, STYLE_HEADER_GRADIENT


# ─────────────────────────────────────────────────────────────────────────────
# Shared card wrapper
# ─────────────────────────────────────────────────────────────────────────────

def _chart_section(icon_cls: str, title: str, content_id: str,
                   col_size: int = 12) -> dbc.Col:
    """A titled card containing a placeholder for chart content."""
    return dbc.Col(
        dbc.Card([
            dbc.CardHeader(
                html.Small([html.I(className=f"fas {icon_cls} me-2"), title],
                           className="fw-bold text-uppercase text-muted"),
                className="bg-transparent border-0 py-2 px-3",
            ),
            dbc.CardBody(
                html.Div(id=f"analytics-{content_id}"),
                className="pt-0 px-2 pb-2",
            ),
        ], className="shadow-sm border-0 rounded-3 h-100"),
        lg=col_size, className="mb-3",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tips tab
# ─────────────────────────────────────────────────────────────────────────────

def tips_tab_layout() -> html.Div:
    return html.Div(id="tips-table-container", className="py-4")


# ─────────────────────────────────────────────────────────────────────────────
# Smart Builder tab
# ─────────────────────────────────────────────────────────────────────────────

def builder_tab_layout() -> html.Div:
    return html.Div([
        dbc.Row([
            # ── Left: Config panel ──────────────────────────────────────────
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        html.Small([html.I(className="fas fa-cog me-2 text-primary"),
                                    "Configuration"],
                                   className="fw-bold text-uppercase text-muted"),
                        className="bg-transparent border-0 py-2 px-3",
                    ),
                    dbc.CardBody(build_builder_panel(), className="pt-0 px-3 pb-3"),
                ], className="shadow-sm border-0 rounded-3 h-100"),
            ], lg=4, className="mb-3"),

            # ── Right: Management bar + preview ────────────────────────────
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            # Save profile
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText(html.I(className="fas fa-save")),
                                    dbc.Input(id="builder-profile-name",
                                              placeholder="Profile name…", size="sm"),
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
                                        "Add to Slips",
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

                # Preview card
                dbc.Card([
                    dbc.CardHeader(
                        html.Small([html.I(className="fas fa-eye me-2 text-primary"),
                                    "Live Preview — updates with every config change"],
                                   className="fw-bold text-uppercase text-muted"),
                        className="bg-transparent border-0 py-2 px-3",
                    ),
                    html.Hr(),
                    dbc.CardBody(
                        html.Div(id="builder-output-container"),
                        className="pt-0 px-3 pb-3",
                    ),
                ], className="shadow-sm border-0 rounded-3"),
            ], lg=8),
        ], className="g-3 mt-2"),
    ], className="p-3")


# ─────────────────────────────────────────────────────────────────────────────
# Slips tab
# ─────────────────────────────────────────────────────────────────────────────

def slips_tab_layout() -> html.Div:
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    dbc.InputGroup([
                        dbc.InputGroupText("Filter Profile:"),
                        dbc.Select(
                            id="historic-profile-filter",
                            options=[{"label": "📊 All Profiles", "value": "all"}],
                            value="all", size="sm",
                        ),
                    ], className="shadow-sm", style={"width": "250px"}),

                    dbc.Button(
                        [html.I(className="fas fa-check-double me-2"), "Validate Results"],
                        id="btn-force-refresh", color="primary",
                        size="sm", className="ms-3 shadow-sm",
                    ),

                    dbc.Button(
                        [html.I(className="fas fa-magic me-2"), "Generate Slips"],
                        id="btn-generate-slips", color="success",
                        size="sm", className="ms-2 shadow-sm",
                    ),
                ], className="d-flex align-items-center mb-4"),
            ]),
            dbc.Col([
                dbc.Spinner(html.Div(id="refresh-status"), size="sm", color="primary"),
            ], width="auto"),
        ]),

        dbc.Row(id="historic-stats-cards", className="mb-4 g-3"),
        html.Div(id="historic-slips-container"),
    ], className="p-3")


# ─────────────────────────────────────────────────────────────────────────────
# Profiles tab
# ─────────────────────────────────────────────────────────────────────────────

def profiles_tab_layout() -> html.Div:
    return html.Div([
        dbc.Row([
            dbc.Col(html.H5("Betting Strategies", className="mb-0 fw-bold"), width=8),
            dbc.Col(
                dbc.Button([html.I(className="fas fa-plus me-2"), "Add Profile"],
                           id="add-profile-btn", color="primary", size="sm",
                           className="float-end shadow-sm"),
                width=4,
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


# ─────────────────────────────────────────────────────────────────────────────
# Analytics tab
# ─────────────────────────────────────────────────────────────────────────────

def analytics_tab_layout() -> html.Div:
    return html.Div([
        # Filter bar
        dbc.Row([
            dbc.Col(
                dbc.InputGroup([
                    dbc.InputGroupText(html.I(className="fas fa-filter text-primary")),
                    dbc.Select(
                        id="analytics-profile-filter",
                        options=[{"label": "📊 All Profiles", "value": "all"}],
                        value="all", size="sm",
                    ),
                ], className="shadow-sm", style={"width": "260px"}),
                className="d-flex align-items-center",
            ),
        ], className="mb-3"),

        # Row 1: Running Balance (full width)
        dbc.Row([_chart_section("fa-chart-line text-primary",
                                "Running Balance", "balance-chart", 12)]),

        # Row 2: Profile ROI | Market Accuracy
        dbc.Row([
            _chart_section("fa-users text-success",  "ROI by Profile",  "profile-chart", 5),
            _chart_section("fa-tags text-warning",   "Market Accuracy", "market-chart",  7),
        ], className="g-3"),

        # Row 3: Source Reliability
        dbc.Row([
            _chart_section(
                "fa-database text-info",
                "Source Reliability — does more data coverage actually mean more wins?",
                "source-chart", 12,
            ),
        ]),
    ], className="p-3")


# ─────────────────────────────────────────────────────────────────────────────
# Full page layout
# ─────────────────────────────────────────────────────────────────────────────

def build_main_layout() -> dbc.Container:
    """Assemble the complete page layout with all tabs."""
    return dbc.Container([
        # Stores
        dcc.Store(id="excluded-urls-store",      data=[]),
        dcc.Store(id="matches-data-store"),
        dcc.Store(id="builder-last-selections",  data=[]),
        dcc.Store(id="live-matches-store",       data={}),   # match_name → {score, minute}

        # ── Header ──────────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H1([html.I(className="fas fa-chart-line me-3"), "Bet Assistant"],
                            className="fw-bold text-white mb-1",
                            style={"letterSpacing": "-1px"}),
                    dbc.Button(
                        [html.I(className="fas fa-sync-alt me-2"), "Refresh Data"],
                        id="refresh-btn",
                        className="ms-auto shadow-sm fw-bold me-2",
                        style={"borderRadius": "10px",
                               "background": "rgba(255,255,255,0.2)",
                               "border": "1px solid rgba(255,255,255,0.3)"},
                    ),
                    dbc.Button(
                        [html.I(className="fas fa-cloud-download-alt me-2"), "Pull Update"],
                        id="btn-pull-update",
                        className="shadow-sm fw-bold",
                        style={"borderRadius": "10px",
                               "background": "rgba(255,193,7,0.4)",
                               "border": "1px solid rgba(255,193,7,0.5)"},
                    ),
                ], className="d-flex align-items-center p-4 shadow-lg",
                   style=STYLE_HEADER_GRADIENT),
            ]),
        ], className="mb-4"),

        # ── Global Filters ───────────────────────────────────────────────────
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
                            dbc.InputGroupText(
                                html.I(className="fas fa-calendar-alt text-success")),
                            dbc.Input(id="date-from", type="date",
                                      className="border-end-0"),
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

        # ── Tabs ─────────────────────────────────────────────────────────────
        dbc.Card([
            dbc.CardBody([
                dbc.Tabs(id="main-tabs", active_tab="tab-tips", children=[
                    dbc.Tab(tips_tab_layout(),
                            label="Betting Tips",  tab_id="tab-tips",
                            labelClassName="px-4 fw-bold"),
                    dbc.Tab(builder_tab_layout(),
                            label="Smart Builder", tab_id="tab-builder",
                            labelClassName="px-4 fw-bold"),
                    dbc.Tab(slips_tab_layout(),
                            label="Slips",         tab_id="tab-historic",
                            labelClassName="px-4 fw-bold"),
                    dbc.Tab(profiles_tab_layout(),
                            label="Profiles",      tab_id="tab-profiles",
                            labelClassName="px-4 fw-bold"),
                    dbc.Tab(analytics_tab_layout(),
                            label="Analytics",     tab_id="tab-analytics",
                            labelClassName="px-4 fw-bold"),
                ], className="nav-pills custom-tabs"),
            ], className="p-4"),
        ], className="border-0 shadow-lg mb-5",
           style={"borderRadius": RADIUS_LG}),

    ], fluid=True, className="px-lg-5",
       style={"backgroundColor": COLORS["bg_page"], "minHeight": "100vh"})