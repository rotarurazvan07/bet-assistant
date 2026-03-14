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
from dash import ALL, Input, Output, State, callback_context, dcc

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
    render_profile_pills,
    alert_msg,
    status_msg,
    render_excluded_badge,
    render_service_row,
)
from dashboard.constants import ALL_MARKET_TYPES, DASHBOARD_ONLY_KEYS, RUNTIME_ONLY_FIELDS
from dashboard.layouts import build_main_layout
from dashboard.logic import DashboardLogic
from dashboard.services import init_services

# ─────────────────────────────────────────────────────────────────────────────
# Profile YAML helpers
# ─────────────────────────────────────────────────────────────────────────────

_BETSLIP_CONFIG_FIELDS = {f.name for f in dc_fields(BetSlipConfig)}


def config_to_yaml_dict(cfg: BetSlipConfig,
                         units: float = 1.0,
                         run_daily_count: bool = False) -> dict:
    d = asdict(cfg)
    for k in RUNTIME_ONLY_FIELDS:
        d[k] = None
    d["units"]     = units
    d["run_daily_count"] = run_daily_count
    return d


def yaml_dict_to_config(data: dict) -> BetSlipConfig:
    cfg_kwargs = {k: v for k, v in data.items()
                  if k in _BETSLIP_CONFIG_FIELDS and k not in RUNTIME_ONLY_FIELDS}
    return BetSlipConfig(**cfg_kwargs)


def ensure_default_profiles(profiles_dir: str) -> None:
    p = Path(profiles_dir)
    if p.is_dir() and any(p.glob("*.yaml")):
        return

    p.mkdir(parents=True, exist_ok=True)
    for name, cfg in PROFILES.items():
        data = config_to_yaml_dict(cfg, units=1.0, run_daily_count=0)
        SettingsManager(profiles_dir).write(profiles_dir, name, data)


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
        self._verify_counter   = [0]
        self._generate_counter = [0]
        self._last_verify      = 0
        self._last_generate    = 0
        self.settings_manager = SettingsManager(config_path)

        svc_cfg = self.settings_manager.get("services") or {}
        self._services = init_services(
            pull_hour     = int(svc_cfg.get("pull_hour",     6)),
            generate_hour = int(svc_cfg.get("generate_hour", 8)),
            on_pull       = self._do_pull,
            on_verify     = self._inc_verify,
            on_generate   = self._inc_generate,
        )

        ensure_default_profiles(profiles_dir=config_path + "/profiles")

        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
        )
        self.app.title = "Bet Assistant"
        self.app.layout = build_main_layout()
        self._setup_callbacks()

    def _do_pull(self) -> str:
        repo     = os.environ.get("REPO",          "rotarurazvan07/bet-assistant")
        artifact = os.environ.get("ARTIFACT_NAME", "all-matches-combined-db")
        cmd = (
            f"rm -f {self.matches_db_path} && "
            f"gh run download -R {repo} -n {artifact} --dir {os.path.dirname(self.matches_db_path)}"
        )
        subprocess.run(cmd, shell=True, check=True)
        self.logic.refresh_data()
        return "Pull successful"

    def _inc_verify(self):
        self._verify_counter[0] += 1

    def _inc_generate(self):
        self._generate_counter[0] += 1

    # ── Callback registration ─────────────────────────────────────────────────

    def _setup_callbacks(self) -> None:
        self._cb_refresh_data()
        self._cb_tips_table()
        self._cb_nullable_toggles()
        self._cb_builder_preview()
        self._cb_save_profile()
        self._cb_delete_profile()
        self._cb_profile_pills()
        self._cb_refresh_pills()
        self._cb_add_to_slips()
        self._cb_exclude_match()
        self._cb_excluded_list()
        self._cb_remove_excluded()
        self._cb_slips_tab()
        self._cb_pull_update()
        self._cb_save_services()
        self._cb_services_tab()
        self._cb_service_sync()

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
                return alert_msg("No data available. Click Refresh Data to load matches.", "warning")
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
            def _make(sw, col):
                @self.app.callback(Output(col, "is_open"), Input(sw, "value"))
                def toggle_collapse(val):
                    return bool(val)
            _make(sw_id, col_id)

    # ── Builder live preview ──────────────────────────────────────────────────

    def _cb_builder_preview(self) -> None:
        @self.app.callback(
            [Output("builder-output-container", "children"),
            Output("builder-last-selections",  "data"),
            Output("builder-profile-name",     "value", allow_duplicate=True)],
            [Input("matches-data-store",    "data"),
            Input("main-tabs",             "active_tab"),
            Input("date-from",             "value"),
            Input("date-to",               "value"),
            Input("excluded-urls-store",   "data"),
            Input("b-target-odds",         "value"),
            Input("b-target-legs",         "value"),
            Input("b-max-overflow-sw",     "value"),
            Input("b-max-overflow-val",    "value"),
            Input("b-prob-floor",          "value"),
            Input("b-min-odds",            "value"),
            Input("b-markets",             "value"),
            Input("b-tolerance-sw",        "value"),
            Input("b-tolerance-val",       "value"),
            Input("b-stop-sw",             "value"),
            Input("b-stop-val",            "value"),
            Input("b-fill-ratio",          "value"),
            Input("b-quality-vs-balance",  "value"),
            Input("b-prob-vs-sources",     "value"),
            Input({"type": "profile-pill", "index": ALL}, "n_clicks"),
            Input("btn-add-manual-slip",   "n_clicks"),],
            State("builder-profile-name",   "value"),
            prevent_initial_call=True,
            allow_duplicate=True,
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
            n_pill_clicks, n_add,
            profile_name,
        ):
            if not data_json or active_tab != "tab-builder":
                return dash.no_update, dash.no_update, dash.no_update

            config_inputs = {
                "b-target-odds", "b-target-legs", "b-max-overflow-sw", "b-max-overflow-val",
                "b-prob-floor", "b-min-odds", "b-markets", "b-tolerance-sw", "b-tolerance-val",
                "b-stop-sw", "b-stop-val", "b-fill-ratio", "b-quality-vs-balance", "b-prob-vs-sources",
            }

            triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

            is_pill_load = "profile-pill" in triggered

            included_markets = (
                None if set(markets or []) == set(ALL_MARKET_TYPES) else (markets or [])
            )

            if is_pill_load:
                profile_out = dash.no_update
            elif triggered in config_inputs and profile_name and profile_name != "manual":
                profile_out = "manual"
            else:
                profile_out = dash.no_update

            cfg = BetSlipConfig(
                date_from=date_from,
                date_to=date_to,
                excluded_urls=excluded_urls or None,
                included_market_types=included_markets,
                target_odds=float(target_odds or 3.0),
                target_legs=int(target_legs or 3),
                max_legs_overflow=int(max_overflow_val) if max_overflow_sw else None,
                probability_floor=float(prob_floor or 50.0),
                min_odds=float(min_odds or 1.05),
                tolerance_factor=(tolerance_val / 100.0) if tolerance_sw else None,
                stop_threshold=(stop_val / 100.0)         if stop_sw      else None,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0,
            )
            selections   = self.logic.build_slip(cfg)
            pending_urls = self.logic.get_pending_urls()
            return render_bet_preview(selections, pending_urls=pending_urls), selections, profile_out

    def _cb_save_profile(self) -> None:
        @self.app.callback(
            [Output("builder-status-msg", "children"),
            Output("profiles-updated-store",  "data")],
            Input("btn-save-profile", "n_clicks"),
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
            State("b-prob-vs-sources",     "value"),
            State("builder-units",     "value"),
            State("builder-run-daily", "value"),
            State("profiles-updated-store", "data")],
            prevent_initial_call=True,
        )
        def save_profile(n, name, target_odds, target_legs, max_overflow_sw, max_overflow_val,
                        prob_floor, min_odds, markets, tolerance_sw, tolerance_val,
                        stop_sw, stop_val, fill_ratio, quality_vs_balance, prob_vs_sources,
                        units, run_daily, store_val):
            if not n:
                return dash.no_update, dash.no_update
            if not name or name == "manual":
                return alert_msg("Enter a profile name first (not 'manual').", "warning"), dash.no_update

            clean = "".join(c for c in name if c.isalnum() or c in ("_", "-")).lower()
            cfg = BetSlipConfig(
                included_market_types=(
                    None if set(markets or []) == set(ALL_MARKET_TYPES) else (markets or [])
                ),
                target_odds=float(target_odds or 3.0),
                target_legs=int(target_legs or 3),
                max_legs_overflow=int(max_overflow_val) if max_overflow_sw else None,
                probability_floor=float(prob_floor or 50.0),
                min_odds=float(min_odds or 1.05),
                tolerance_factor=(tolerance_val / 100.0) if tolerance_sw else None,
                stop_threshold=(stop_val / 100.0)         if stop_sw      else None,
                min_legs_fill_ratio=float(fill_ratio or 70) / 100.0,
                quality_vs_balance=float(quality_vs_balance or 50) / 100.0,
                prob_vs_sources=float(prob_vs_sources or 50) / 100.0,
            )
            data = config_to_yaml_dict(cfg,
                                        units=units or 1.0,
                                        run_daily_count=int(run_daily or 0))
            self.settings_manager.write(self.config_path + "/profiles", clean, data)
            return alert_msg(f"✅ Profile '{clean}' saved!", "success"), (store_val or 0) + 1

    def _cb_delete_profile(self) -> None:
        @self.app.callback(
            [Output("builder-status-msg",     "children", allow_duplicate=True),
            Output("profiles-updated-store", "data",     allow_duplicate=True),
            Output("builder-profile-name",   "value",    allow_duplicate=True)],
            Input("btn-delete-profile", "n_clicks"),
            [State("builder-profile-name",   "value"),
            State("profiles-updated-store", "data")],
            prevent_initial_call=True,
        )
        def delete_profile(n, name, store_val):
            if not n:
                return dash.no_update, dash.no_update, dash.no_update
            if not name or name == "manual":
                return alert_msg("Nothing to delete.", "warning"), dash.no_update, dash.no_update

            self.settings_manager.delete(self.config_path + "/profiles", name)
            return (
                alert_msg(f"🗑️ Profile '{name}' deleted.", "danger"),
                (store_val or 0) + 1,
                "manual",
            )

    def _cb_profile_pills(self) -> None:
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
            Output("builder-profile-name", "value", allow_duplicate=True),
            Output("builder-units",     "value",    allow_duplicate=True),
            Output("builder-run-daily", "value",    allow_duplicate=True),],
            Input({"type": "profile-pill", "index": ALL}, "n_clicks"),
            prevent_initial_call=True,
        )
        def load_profile_from_pill(n_clicks_list):
            ctx = dash.callback_context
            if not ctx.triggered or not any(n_clicks_list):
                return [dash.no_update] * 17

            triggered_id = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
            profile_name = triggered_id["index"]

            prof = self.settings_manager.get("profiles", profile_name)
            if not prof:
                return [dash.no_update] * 17

            mkt_raw  = prof.get("included_market_types")
            tol_raw  = prof.get("tolerance_factor")
            stop_raw = prof.get("stop_threshold")
            ovf_raw  = prof.get("max_legs_overflow")

            return [
                prof.get("target_odds",         3.0),
                prof.get("target_legs",         3),
                [1] if ovf_raw  is not None else [],
                int(ovf_raw) if ovf_raw is not None else 1,
                prof.get("probability_floor",   50.0),
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
                prof.get("units", 1.0),
                prof.get("run_daily_count", 0),
            ]

    def _cb_refresh_pills(self) -> None:
        @self.app.callback(
            Output("profile-pills", "children"),
            [Input("profiles-updated-store", "data"),
            Input("main-tabs",              "active_tab")],
            prevent_initial_call=False,
        )
        def refresh_pills(_, active_tab):
            profiles = self.settings_manager.get("profiles") or {}
            return render_profile_pills(profiles)

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
                return alert_msg("No slip to add — preview must have selections first.", "warning")

            profile   = (profile_name or "manual").strip() or "manual"
            units_val = float(units or 1.0)

            try:
                slip_id    = self.logic.save_slip(profile, selections, units_val)
                total_odds = 1.0
                for s in selections:
                    total_odds *= s.get("odds", 1.0)
                return alert_msg(
                    f"✅ Slip #{slip_id} added to '{profile}' — "
                    f"{len(selections)} legs @ {total_odds:.2f} ({units_val}u)",
                    "success",
                )
            except Exception as exc:
                return alert_msg(f"❌ Failed to add slip: {exc}", "danger")

    # ── Exclude match from builder ────────────────────────────────────────────

    def _cb_exclude_match(self) -> None:
        @self.app.callback(
            Output("excluded-urls-store", "data"),
            [Input({"type": "exclude-btn", "index": ALL}, "n_clicks"),
            Input("btn-reset-excluded", "n_clicks")],
            State("excluded-urls-store", "data"),
            prevent_initial_call=True,
        )
        def exclude_match(n_clicks_list, n_reset, current_excluded):
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if triggered_id == "btn-reset-excluded":
                return []

            prop = ctx.triggered[0]["prop_id"]
            if ".n_clicks" not in prop:
                return dash.no_update

            try:
                tid = json.loads(prop.split(".n_clicks")[0])
                url = tid["index"]
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

    def _cb_excluded_list(self) -> None:
        @self.app.callback(
            [Output("excluded-matches-list", "children"),
            Output("excluded-collapse",     "is_open")],
            Input("excluded-urls-store", "data"),
        )
        def update_excluded(excluded_urls):
            if not excluded_urls:
                return [], False

            df = self.logic.match_df
            items = []
            for url in excluded_urls:
                if df is not None and not df.empty:
                    row = df[df["result_url"] == url]
                    label = row.iloc[0]["home"] + " vs " + row.iloc[0]["away"] if not row.empty else url
                else:
                    label = url
                items.append(render_excluded_badge(url, label))
            return items, True

    def _cb_remove_excluded(self) -> None:
        @self.app.callback(
            Output("excluded-urls-store", "data", allow_duplicate=True),
            Input({"type": "exclude-remove-btn", "index": ALL}, "n_clicks"),
            State("excluded-urls-store", "data"),
            prevent_initial_call=True,
        )
        def remove_excluded(n_clicks_list, current_excluded):
            if not any(n_clicks_list) or not current_excluded:
                return dash.no_update
            triggered_id = dash.callback_context.triggered_id
            if not triggered_id:
                return dash.no_update
            url_to_remove = triggered_id["index"]
            return [u for u in current_excluded if u != url_to_remove]

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
             Input("btn-generate-slips",      "n_clicks"),
             Input("btn-add-manual-slip",     "n_clicks"),
             Input({"type": "delete-slip-btn", "index": ALL}, "n_clicks"),
             Input("svc-verify-trigger",      "data"),
             Input("svc-generate-trigger",    "data"),],
            State("live-matches-store", "data"),
            prevent_initial_call=True,
        )
        def update_slips_tab(
            active_tab, profile_filter,
            n_validate, n_generate, n_add,
            n_delete_list,
            v_trigger, g_trigger,
            current_live,
        ):
            ctx       = dash.callback_context
            triggered = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""

            if "delete-slip-btn" in triggered:
                slip_id = int(json.loads(triggered.split(".n_clicks")[0])["index"])
                self.logic.delete_slip(slip_id)

            refresh_msg = dash.no_update
            live_store  = current_live if isinstance(current_live, dict) else {}
            live_out    = dash.no_update

            if triggered in ("btn-force-refresh", "svc-verify-trigger"):
                result     = self.logic.validate_slips()
                live_store = {item["match_name"]: {"score": item["score"], "minute": item["minute"]}
                              for item in result.get("live", [])}
                for item in result.get("finished", []):
                    live_store[item["match_name"]] = {
                        "score":   item["score"],
                        "minute":  "FT",
                        "outcome": item["outcome"],
                    }
                live_out    = live_store
                refresh_msg = status_msg(
                    f"✅ Checked {result['checked']} · Settled {result['settled']} · "
                    f"Live {len(live_store)} · Errors {result['errors']}"
                )

            elif triggered in ("btn-generate-slips", "svc-generate-trigger"):
                all_profiles = self.settings_manager.get("profiles") or {}
                profiles = {
                    name: (yaml_dict_to_config(cfg), cfg.get("units", 1.0), cfg.get("run_daily_count", 1))
                    for name, cfg in all_profiles.items()
                    if cfg.get("run_daily_count")
                }
                results     = self.logic.generate_slips(profiles)
                total       = sum(len(v) for v in results.values())
                refresh_msg = status_msg(f"✅ Generated {total} slip(s)")

            if active_tab != "tab-historic" and triggered != "btn-add-manual-slip":
                return (dash.no_update, dash.no_update,
                        dash.no_update, refresh_msg, live_out)

            stats  = self.logic.stats(profile_filter if profile_filter != "all" else None)
            slips  = self.logic.get_slips(profile_filter if profile_filter != "all" else None)

            stats_ui = render_stats_cards(stats)
            slips_ui = (
                [render_slip_card(s, live_data=live_store) for s in slips]
                if slips
                else [alert_msg(f"No {profile_filter} slips found.", "info")]
            )

            profile_names = [p.stem for p in Path(self.config_path + "/profiles").glob("*.yaml")]
            options = (
                [{"label": "📊 All Profiles", "value": "all"}] +
                [{"label": f"👤 {n.upper()}", "value": n} for n in profile_names]
            )

            return stats_ui, slips_ui, options, refresh_msg, live_out

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
                self._do_pull()
                return "Pull successful", (current_clicks or 0) + 1
            except Exception as exc:
                return f"Pull failed: {exc}", dash.no_update

    def _cb_save_services(self) -> None:
        @self.app.callback(
            Output("svc-save-status", "children"),
            Input("btn-save-services", "n_clicks"),
            [State("svc-pull-hour",     "value"),
            State("svc-generate-hour", "value")],
            prevent_initial_call=True,
        )
        def save_services(n, pull_hour, generate_hour):
            if not n:
                return dash.no_update
            self.settings_manager.write(self.config_path, "services", {
                "pull_hour":     int(pull_hour     or 6),
                "generate_hour": int(generate_hour or 8),
            })
            self._services["puller"].pull_hour        = int(pull_hour     or 6)
            self._services["generator"].generate_hour = int(generate_hour or 8)
            return "✅ Saved — takes effect next cycle"


    def _cb_services_tab(self) -> None:
        @self.app.callback(
            [Output("svc-status-container", "children"),
            Output("svc-pull-hour",        "value"),
            Output("svc-generate-hour",    "value")],
            Input("main-tabs", "active_tab"),
        )
        def update_services_tab(active_tab):
            if active_tab != "tab-services":
                return dash.no_update, dash.no_update, dash.no_update

            cfg = self.settings_manager.get("services") or {}
            return (
                [render_service_row(n, s) for n, s in self._services.items()],
                cfg.get("pull_hour",     6),
                cfg.get("generate_hour", 8),
            )

    def _cb_service_sync(self) -> None:
        @self.app.callback(
            [Output("svc-verify-trigger",   "data"),
            Output("svc-generate-trigger", "data")],
            Input("svc-poll-interval", "n_intervals"),
        )
        def sync_service_triggers(_):
            verify_val   = self._verify_counter[0]
            generate_val = self._generate_counter[0]

            # only return new values when they've actually changed
            if verify_val   == self._last_verify:
                verify_out = dash.no_update
            else:
                self._last_verify = verify_val
                verify_out = verify_val

            if generate_val == self._last_generate:
                generate_out = dash.no_update
            else:
                self._last_generate = generate_val
                generate_out = generate_val

            return verify_out, generate_out
    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, debug: bool = True, port: int = 8050) -> None:
        print(f"Starting dashboard on http://0.0.0.0:{port}")
        self.app.run(debug=debug, host="0.0.0.0", port=port, dev_tools_hot_reload=False)


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