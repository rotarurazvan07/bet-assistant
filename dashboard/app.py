"""
dashboard/app.py
════════════════
BetAssistantDashboard — Dash application class.

Responsibilities
────────────────
  • Initialise the Dash app and wire callbacks.
  • Delegate ALL data operations to DashboardLogic.
  • Delegate ALL UI rendering to components.py / charts.py / layouts.py.
  • No business logic here; no inline styles here.

Entry point
───────────
  python -m dashboard.app  <db_path>  [--port 8050]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, fields as dc_fields
from pathlib import Path
from typing import Any, Dict, List, Optional

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback_context, dcc, html

from bet_framework.BetAssistant import BetSlipConfig, PROFILES
from bet_framework.SettingsManager import SettingsManager

from dashboard.charts import (
    render_balance_chart,
    render_market_accuracy,
    render_profile_comparison,
    render_source_analysis,
)
from dashboard.components import (
    create_tips_table,
    render_bet_preview,
    render_profile_card,
    render_slip_card,
    render_stats_cards,
)
from dashboard.constants import ALL_MARKET_TYPES, DASHBOARD_ONLY_KEYS, RUNTIME_ONLY_FIELDS
from dashboard.layouts import build_main_layout
from dashboard.logic import DashboardLogic


# ─────────────────────────────────────────────────────────────────────────────
# Profile YAML helpers
# ─────────────────────────────────────────────────────────────────────────────

_BETSLIP_CONFIG_FIELDS = {f.name for f in dc_fields(BetSlipConfig)}


def config_to_yaml_dict(cfg: BetSlipConfig,
                         units: float = 1.0,
                         run_daily: bool = False) -> dict:
    d = asdict(cfg)
    for k in RUNTIME_ONLY_FIELDS:
        d[k] = None
    d["units"]     = units
    d["run_daily"] = run_daily
    return d


def yaml_dict_to_config(data: dict) -> BetSlipConfig:
    cfg_kwargs = {k: v for k, v in data.items()
                  if k in _BETSLIP_CONFIG_FIELDS and k not in RUNTIME_ONLY_FIELDS}
    return BetSlipConfig(**cfg_kwargs)


def ensure_default_profiles(profiles_dir: str) -> None:
    os.makedirs(profiles_dir, exist_ok=True)
    for name, cfg in PROFILES.items():
        path = os.path.join(profiles_dir, f"{name}.yaml")
        if not os.path.exists(path):
            data = config_to_yaml_dict(cfg, units=1.0, run_daily=False)
            self.settings_manager.write(profiles_dir, name, data)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class BetAssistantDashboard:
    """
    Dash application for the Bet Assistant.

    Parameters
    ----------
    db_path : Path to the BetAssistant SQLite file (slips + legs).
    """

    def __init__(self, matches_db_path: str, slips_db_path: str, config_path: str) -> None:
        self.logic     = DashboardLogic(matches_db_path, slips_db_path)
        self.matches_db_path = matches_db_path
        self.slips_db_path   = slips_db_path
        self.config_path     = config_path

        self.settings_manager = SettingsManager(config_path)

        ensure_default_profiles(profiles_dir=config_path + "/profiles")

        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
        )
        self.app.title = "Bet Assistant"
        self.app.layout = build_main_layout()
        self._setup_callbacks()

    # ── Callback registration ─────────────────────────────────────────────────

    def _setup_callbacks(self) -> None:
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
        self._cb_analytics()

    # ── Refresh match data ────────────────────────────────────────────────────

    def _cb_refresh_data(self) -> None:
        @self.app.callback(
            Output("matches-data-store", "data"),
            Input("refresh-btn", "n_clicks"),
            prevent_initial_call=False,
        )
        def refresh_data(_):
            df = self.logic.refresh_data()
            return df.to_json(date_format="iso", orient="split")

    # ── Tips table ────────────────────────────────────────────────────────────

    def _cb_tips_table(self) -> None:
        @self.app.callback(
            Output("tips-table-container", "children"),
            [Input("matches-data-store", "data"),
             Input("search-input",       "value"),
             Input("date-from",          "value"),
             Input("date-to",            "value")],
        )
        def update_tips_table(data_json, search_text, date_from, date_to):
            if not data_json:
                return dbc.Alert(
                    [html.I(className="fas fa-info-circle me-2"),
                     "No data available. Click Refresh Data to load matches."],
                    color="warning", className="m-4",
                )
            filtered = self.logic.filter_matches(
                search_text=search_text,
                date_from=date_from,
                date_to=date_to,
            )
            return create_tips_table(filtered)

    # ── Nullable field toggles ────────────────────────────────────────────────

    def _cb_nullable_toggles(self) -> None:
        for sw_id, col_id in [
            ("b-max-overflow-sw",  "b-max-overflow-collapse"),
            ("b-tolerance-sw",     "b-tolerance-collapse"),
            ("b-stop-sw",          "b-stop-collapse"),
        ]:
            @self.app.callback(Output(col_id, "is_open"), Input(sw_id, "value"))
            def toggle_collapse(val):
                return bool(val)

    # ── Builder live preview ──────────────────────────────────────────────────

    def _cb_builder_preview(self) -> None:
        @self.app.callback(
            [Output("builder-output-container", "children"),
             Output("builder-last-selections",  "data")],
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

            included_markets = (
                None if set(markets or []) == set(ALL_MARKET_TYPES)
                else (markets or [])
            )

            cfg = BetSlipConfig(
                date_from=date_from,
                date_to=date_to,
                excluded_urls=excluded_urls or None,
                included_market_types=included_markets,
                target_odds=float(target_odds or 3.0),
                target_legs=int(target_legs or 3),
                max_legs_overflow=int(max_overflow_val) if max_overflow_sw else None,
                probability_floor=float(prob_floor or 55.0),
                min_odds=float(min_odds or 1.05),
                tolerance_factor=(tolerance_val / 100.0) if tolerance_sw else None,
                stop_threshold=(stop_val / 100.0)         if stop_sw      else None,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0,
            )

            selections = self.logic.build_slip(cfg)
            return render_bet_preview(selections), selections

    # ── Load profile into builder ─────────────────────────────────────────────

    def _cb_load_profile(self) -> None:
        @self.app.callback(
            [Output("b-target-odds",        "value"),
             Output("b-target-legs",        "value"),
             Output("b-max-overflow-sw",    "value"),
             Output("b-max-overflow-val",   "value"),
             Output("b-prob-floor",         "value"),
             Output("b-min-odds",           "value"),
             Output("b-markets",            "value"),
             Output("b-tolerance-sw",       "value"),
             Output("b-tolerance-val",      "value"),
             Output("b-stop-sw",            "value"),
             Output("b-stop-val",           "value"),
             Output("b-fill-ratio",         "value"),
             Output("b-quality-vs-balance", "value"),
             Output("b-prob-vs-sources",    "value"),
             Output("builder-profile-name", "value")],
            Input("builder-profile-selector", "value"),
            prevent_initial_call=True,
        )
        def load_profile(profile_name):
            no = dash.no_update
            if not profile_name:
                return [no] * 15

            prof = self.settings_manager.get(profile_name)
            if not prof:
                return [no] * 15

            mkt_raw  = prof.get("included_market_types")
            tol_raw  = prof.get("tolerance_factor")
            stop_raw = prof.get("stop_threshold")
            ovf_raw  = prof.get("max_legs_overflow")

            return [
                prof.get("target_odds",         3.0),
                prof.get("target_legs",         3),
                [1] if ovf_raw  is not None else [],
                int(ovf_raw) if ovf_raw is not None else 1,
                prof.get("probability_floor",   55.0),
                prof.get("min_odds",            1.05),
                mkt_raw if mkt_raw else ALL_MARKET_TYPES,
                [1] if tol_raw  is not None else [],
                int((tol_raw  or 0.25) * 100),
                [1] if stop_raw is not None else [],
                int((stop_raw or 0.91) * 100),
                int(prof.get("min_legs_fill_ratio", 0.70) * 100),
                int(prof.get("quality_vs_balance",  0.5)  * 100),
                int(prof.get("prob_vs_sources",     0.5)  * 100),
                profile_name,
            ]

    # ── Save builder config as profile ────────────────────────────────────────

    def _cb_save_profile(self) -> None:
        @self.app.callback(
            Output("builder-status-msg", "children"),
            Input("save-profile-btn", "n_clicks"),
            [State("builder-profile-name",  "value"),
             State("b-target-odds",         "value"),
             State("b-target-legs",         "value"),
             State("b-max-overflow-sw",     "value"),
             State("b-max-overflow-val",    "value"),
             State("b-prob-floor",          "value"),
             State("b-min-odds",            "value"),
             State("b-markets",             "value"),
             State("b-tolerance-sw",        "value"),
             State("b-tolerance-val",       "value"),
             State("b-stop-sw",             "value"),
             State("b-stop-val",            "value"),
             State("b-fill-ratio",          "value"),
             State("b-quality-vs-balance",  "value"),
             State("b-prob-vs-sources",     "value")],
            prevent_initial_call=True,
        )
        def save_profile(
            n, name,
            target_odds, target_legs,
            max_overflow_sw, max_overflow_val,
            prob_floor, min_odds,
            markets,
            tolerance_sw, tolerance_val,
            stop_sw, stop_val,
            fill_ratio,
            quality_vs_balance, prob_vs_sources,
        ):
            if not n:
                return dash.no_update
            if not name:
                return dbc.Alert("Profile name is required.", color="danger",
                                 dismissable=True)

            clean = "".join(c for c in name if c.isalnum() or c in ("_", "-")).lower()
            included_markets = (
                None if set(markets or []) == set(ALL_MARKET_TYPES)
                else (markets or [])
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
                stop_threshold=(stop_val / 100.0)         if stop_sw      else None,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0,
            )

            existing = self.settings_manager.get(clean) or {}
            data = config_to_yaml_dict(
                cfg,
                units=existing.get("units", 1.0),
                run_daily=existing.get("run_daily", False),
            )

            if self.settings_manager.write(self.config_path + "/profiles", clean, data):
                return dbc.Alert(f"✅ Profile '{clean}' saved!",
                                 color="success", dismissable=True)
            return dbc.Alert("❌ Failed to save profile.", color="danger", dismissable=True)

    # ── Add to Slips ──────────────────────────────────────────────────────────

    def _cb_add_to_slips(self) -> None:
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
                return dbc.Alert(
                    "No slip to add — preview must have selections first.",
                    color="warning", dismissable=True,
                )

            profile   = (profile_name or "manual").strip() or "manual"
            units_val = float(units or 1.0)

            try:
                slip_id    = self.logic.save_slip(profile, selections, units_val)
                total_odds = 1.0
                for s in selections:
                    total_odds *= s.get("odds", 1.0)

                return dbc.Alert(
                    f"✅ Slip #{slip_id} added to '{profile}' — "
                    f"{len(selections)} legs @ {total_odds:.2f} ({units_val}u)",
                    color="success", dismissable=True,
                )
            except Exception as exc:
                return dbc.Alert(f"❌ Failed to add slip: {exc}",
                                 color="danger", dismissable=True)

    # ── Exclude match from builder ────────────────────────────────────────────

    def _cb_exclude_match(self) -> None:
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

    def _cb_profiles_tab(self) -> None:
        @self.app.callback(
            [Output("profiles-container",       "children"),
             Output("builder-profile-selector", "options")],
            [Input("main-tabs",                 "active_tab"),
             Input("add-profile-btn",           "n_clicks"),
             Input({"type": "delete-profile-btn", "index": ALL}, "n_clicks")],
            State("profiles-container", "children"),
            prevent_initial_call=False,
        )
        def render_profiles(active_tab, n_add, n_delete_list, _):
            ctx       = dash.callback_context
            triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            profiles = {
                name: cfg
                for name, cfg in self.settings_manager.get("profiles").items()
            }

            # Deletion
            if "delete-profile-btn" in triggered:
                try:
                    btn_id = json.loads(triggered.split(".n_clicks")[0])
                    pid    = btn_id["index"]
                    self.logic.settings_manager.delete("config/profiles", pid)
                except Exception:
                    pass

            # Addition
            if triggered == "add-profile-btn.n_clicks" and n_add:
                new_id = f"profile_{n_add}"
                cfg    = BetSlipConfig()
                data   = config_to_yaml_dict(cfg, units=1.0, run_daily=False)
                self.settings_manager.write(self.config_path + "/profiles", new_id, data)
                profiles[new_id] = data

            cards   = [dbc.Col(render_profile_card(pid, pdata), lg=4, md=6, xs=12)
                       for pid, pdata in profiles.items()]
            options = [{"label": f"👤 {pid.upper()}", "value": pid}
                       for pid in profiles]
            return cards, options

    # ── Save all profiles (units + run_daily) ─────────────────────────────────

    def _cb_save_all_profiles(self) -> None:
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
                pid     = item["index"]
                current = self.settings_manager.get(pid) or {}
                current.update({
                    "units":     units_list[i],
                    "run_daily": (1 in daily_list[i]) if daily_list[i] else False,
                })
                if not self.settings_manager.write(self.config_path + "/profiles", pid, current):
                    success_all = False

            if success_all:
                return "✅ All profiles saved", "ms-3 fw-bold text-success"
            return "❌ Some profiles failed to save", "ms-3 fw-bold text-danger"

    # ── Slips tab ─────────────────────────────────────────────────────────────

    def _cb_slips_tab(self) -> None:
        @self.app.callback(
            [Output("historic-stats-cards",      "children"),
             Output("historic-slips-container",  "children"),
             Output("historic-profile-filter",   "options"),
             Output("refresh-status",            "children"),
             Output("live-matches-store",        "data")],
            [Input("main-tabs",               "active_tab"),
             Input("historic-profile-filter", "value"),
             Input("btn-force-refresh",       "n_clicks"),
             Input("btn-generate-slips",      "n_clicks")],
            State("live-matches-store", "data"),
            prevent_initial_call=True,
        )
        def update_slips_tab(
            active_tab, profile_filter,
            n_validate, n_generate,
            current_live,
        ):
            ctx       = dash.callback_context
            triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

            refresh_msg  = dash.no_update
            live_store   = current_live or {}

            # ── Validate results (inline, no subprocess) ───────────────────
            if triggered == "btn-force-refresh":
                result     = self.logic.validate_slips()
                live_store = {item["match_name"]: {"score": item["score"], "minute": item["minute"]}
                            for item in result.get("live", [])}
                refresh_msg = html.Span(
                    f"✅ Checked {result['checked']} · Settled {result['settled']} · "
                    f"Live {len(live_store)} · Errors {result['errors']}",
                    className="text-success ms-2", style={"fontSize": "0.8rem"},
                )

            elif triggered == "btn-generate-slips":
                all_profiles = self.settings_manager.get("profiles") or {}

                profiles = {
                    name: (yaml_dict_to_config(cfg), cfg.get("units", 1.0))
                    for name, cfg in all_profiles.items()
                    if cfg.get("run_daily")
                }

                results = self.logic.generate_slips(profiles)
                refresh_msg = html.Span(f"✅ Generated {len(results)} slip(s)",
                                        className="text-success ms-2", style={"fontSize": "0.8rem"})
            if active_tab != "tab-historic":
                return (dash.no_update, dash.no_update,
                        dash.no_update, refresh_msg, live_store)

            # ── Build UI ───────────────────────────────────────────────────
            stats  = self.logic.stats(profile_filter if profile_filter != "all" else None)
            slips  = self.logic.get_slips(profile_filter if profile_filter != "all" else None)

            stats_ui = render_stats_cards(stats)
            slips_ui = (
                [render_slip_card(s, live_data=live_store) for s in slips]
                if slips
                else [dbc.Alert(f"No {profile_filter} slips found.", color="info")]
            )

            profile_names = [p.stem for p in Path(self.config_path + "/profiles").glob("*.yaml")]
            options = (
                [{"label": "📊 All Profiles", "value": "all"}] +
                [{"label": f"👤 {n.upper()}", "value": n} for n in profile_names]
            )

            return stats_ui, slips_ui, options, refresh_msg, live_store

    # ── Pull DB update ─────────────────────────────────────────────────────────

    def _cb_pull_update(self) -> None:
        @self.app.callback(
            [Output("last-updated-text", "children"),
             Output("refresh-btn",       "n_clicks")],
            Input("btn-pull-update",  "n_clicks"),
            State("refresh-btn",      "n_clicks"),
            prevent_initial_call=True,
        )
        def pull_update(n, current_clicks):
            if not n:
                return dash.no_update, dash.no_update
            try:
                repo     = os.environ.get("REPO", "rotarurazvan07/bet-assistant")
                artifact = os.environ.get("ARTIFACT_NAME", "all-matches-combined-db")
                cmd = (
                    f"rm -f /app/data/final_matches.db* && "
                    f"gh run download -R {repo} -n {artifact} --dir /app/data"
                )
                subprocess.run(cmd, shell=True, check=True)
                return "Pull successful", (current_clicks or 0) + 1
            except Exception as exc:
                return f"Pull failed: {exc}", dash.no_update

    # ── Analytics tab ─────────────────────────────────────────────────────────

    def _cb_analytics(self) -> None:
        @self.app.callback(
            [Output("analytics-balance-chart", "children"),
             Output("analytics-profile-chart", "children"),
             Output("analytics-market-chart",  "children"),
             Output("analytics-source-chart",  "children"),
             Output("analytics-profile-filter","options")],
            [Input("main-tabs",                "active_tab"),
             Input("analytics-profile-filter", "value"),
             Input("matches-data-store",        "data")],
        )
        def update_analytics(active_tab, profile_filter, _data_trigger):
            if active_tab != "tab-analytics":
                return [dash.no_update] * 5

            pf = profile_filter if profile_filter != "all" else None

            history       = self.logic.balance_history(pf)
            profile_stats = self.logic.stats_by_profile()
            market_stats  = self.logic.stats_by_market(pf)
            settled_legs  = self.logic.get_settled_legs(pf)

            balance_chart = render_balance_chart(history)
            profile_chart = render_profile_comparison(profile_stats)
            market_chart  = render_market_accuracy(market_stats)
            source_chart  = render_source_analysis(settled_legs, self.logic.match_df)

            profile_names = [p.stem for p in Path(self.config_path + "/profiles").glob("*.yaml")]
            options = (
                [{"label": "📊 All Profiles", "value": "all"}] +
                [{"label": f"👤 {n.upper()}", "value": n} for n in profile_names]
            )
            return balance_chart, profile_chart, market_chart, source_chart, options

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, debug: bool = True, port: int = 8050) -> None:
        print(f"Starting dashboard on http://0.0.0.0:{port}")
        self.app.run(debug=debug, host="0.0.0.0", port=port)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Bet Assistant Dashboard")
    parser.add_argument("--matches_db_path", help="Path to the BetAssistant SQLite matches database")
    parser.add_argument("--slips_db_path", help="Path to the BetAssistant SQLite slips database")
    parser.add_argument("--config_path", help="Path to the BetAssistant config directory")
    parser.add_argument("--port", type=int, default=8050, help="Port (default 8050)")
    parser.add_argument("--no-debug", action="store_true",
                        help="Disable Dash debug mode")
    args = parser.parse_args()

    dashboard = BetAssistantDashboard(args.matches_db_path, args.slips_db_path, args.config_path)
    dashboard.run(debug=not args.no_debug, port=args.port)