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

from dashboard.components import build_builder_panel, make_tooltip
from dashboard.constants import COLORS, RADIUS_LG, SHADOW_LG, STYLE_HEADER_GRADIENT

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
                    dbc.CardBody([
                        # Profile pills
                        html.Div([
                            html.Small("PROFILES", className="fw-bold text-muted d-block mb-1",
                                       style={"fontSize": "0.65rem"}),
                            html.Div(id="profile-pills", className="d-flex flex-wrap mb-3"),
                        ]),
                        html.Hr(className="my-2"),
                        build_builder_panel(),
                    ], className="pt-0 px-3 pb-3"),
                ], className="shadow-sm border-0 rounded-3 h-100"),
            ], lg=4, className="mb-3"),

            # ── Right: Management bar + preview ────────────────────────────
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.InputGroup([
                                    dbc.InputGroupText(html.I(className="fas fa-user-tag")),
                                    dbc.Input(
                                        id="builder-profile-name",
                                        placeholder="manual",
                                        value="manual",
                                        size="sm",
                                    ),
                                    dbc.Button("Save", id="btn-save-profile", color="primary", size="sm"),
                                    dbc.Button("Delete", id="btn-delete-profile", color="danger",  size="sm"),
                                ], className="shadow-sm"),
                            ], lg=4, className="mb-2 mb-lg-0"),

                            dbc.Col([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.InputGroup([
                                            dbc.InputGroupText("Units"),
                                            dbc.Input(id="builder-units", type="number",
                                                    value=1.0, min=0.1, step=0.1, size="sm",
                                                    style={"maxWidth": "70px"}),
                                            dbc.Button(
                                                [html.I(className="fas fa-plus-circle me-1"), "Add to Slips"],
                                                id="btn-add-manual-slip", color="success", size="sm", className="fw-bold",
                                            ),
                                            dbc.Button(
                                                [html.I(className="fas fa-undo me-1"), "Reset excluded"],
                                                id="btn-reset-excluded", color="outline-secondary", size="sm",
                                            ),
                                        ], className="shadow-sm"),
                                    ], width="auto"),

                                    dbc.Col([
                                        html.Div([
                                            html.Small("RUN DAILY", className="text-muted fw-bold d-block",
                                                    style={"fontSize": "0.6rem", "letterSpacing": "0.5px"}),
                                            dbc.Input(
                                                id="builder-run-daily",
                                                type="number",
                                                value=0, min=0, step=1,
                                                size="sm",
                                                style={"maxWidth": "70px"},
                                                className="mt-1",
                                            ),
                                        ], className="d-flex flex-column align-items-center px-2 border-start"),
                                    ], width="auto", className="d-flex align-items-center"),
                                ], className="g-2 align-items-center flex-nowrap"),
                            ], lg=8),

                        ], className="g-2 align-items-center"),
                    ], className="py-2 px-3"),
                ], className="shadow-sm border-0 rounded-3 mb-3"),

                html.Div(id="builder-status-msg", className="mb-2"),

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

                dbc.Collapse(
                    dbc.Card([
                        dbc.CardHeader(
                            html.Small([html.I(className="fas fa-ban me-2 text-danger"),
                                        "Excluded Matches"],
                                    className="fw-bold text-uppercase text-muted"),
                            className="bg-transparent border-0 py-2 px-3",
                        ),
                        dbc.CardBody(html.Div(id="excluded-matches-list"), className="pt-0 px-3 pb-2"),
                    ], className="shadow-sm border-0 rounded-3 mt-3"),
                    id="excluded-collapse",
                    is_open=False,
                ),
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

def services_tab_layout() -> html.Div:
    return html.Div([
        html.H5("Automation Services", className="fw-bold mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        html.Small([html.I(className="fas fa-clock me-2 text-primary"),
                                    "Scheduled Tasks"],
                                   className="fw-bold text-uppercase text-muted"),
                        className="bg-transparent border-0 py-2 px-3",
                    ),
                    dbc.CardBody([
                        html.Small(["Pull DB", make_tooltip("pull-hour",
                            "Hour when the app pulls the latest match database from GitHub.")],
                            className="fw-bold text-muted mb-1 d-block"),
                        dcc.Slider(id="svc-pull-hour", min=0, max=23, step=1, value=6,
                                   marks={h: str(h) for h in range(0, 24, 3)},
                                   tooltip={"placement": "bottom", "always_visible": True},
                                   className="mb-4"),

                        html.Small(["Generate Slips", make_tooltip("gen-hour",
                            "Hour when the app auto-generates bet slips for all active profiles.")],
                            className="fw-bold text-muted mb-1 d-block"),
                        dcc.Slider(id="svc-generate-hour", min=0, max=23, step=1, value=8,
                                   marks={h: str(h) for h in range(0, 24, 3)},
                                   tooltip={"placement": "bottom", "always_visible": True},
                                   className="mb-4"),

                        html.Hr(),

                        dbc.Button(
                            [html.I(className="fas fa-save me-2"), "Save Settings"],
                            id="btn-save-services", color="primary", size="sm",
                            className="shadow-sm",
                        ),
                        html.Span(id="svc-save-status", className="ms-3 small fw-bold"),
                    ], className="px-3 pb-3"),
                ], className="shadow-sm border-0 rounded-3"),
            ], lg=5),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        html.Small([html.I(className="fas fa-heartbeat me-2 text-success"),
                                    "Service Status"],
                                   className="fw-bold text-uppercase text-muted"),
                        className="bg-transparent border-0 py-2 px-3",
                    ),
                    dbc.CardBody(
                        html.Div(id="svc-status-container"),
                        className="px-3 pb-3",
                    ),
                ], className="shadow-sm border-0 rounded-3"),
            ], lg=7),
        ], className="g-3"),
    ], className="p-4")

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
        dcc.Store(id="profiles-updated-store", data=0),
        dcc.Store(id="svc-verify-trigger",  data=0),
        dcc.Store(id="svc-generate-trigger", data=0),
        dcc.Interval(id="svc-poll-interval", interval=5000, n_intervals=0),  # 5s poll
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
                    dbc.Tab(services_tab_layout(),
                            label="Services", tab_id="tab-services",
                            labelClassName="px-4 fw-bold"),
                ], className="nav-pills custom-tabs"),
            ], className="p-4"),
        ], className="border-0 shadow-lg mb-5",
           style={"borderRadius": RADIUS_LG}),

    ], fluid=True, className="px-lg-5",
       style={"backgroundColor": COLORS["bg_page"], "minHeight": "100vh"})