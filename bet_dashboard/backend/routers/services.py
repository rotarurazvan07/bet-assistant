"""Services API: status, settings and toggles."""

from datetime import datetime, timedelta

from core.schemas import ServicesSettingsIn
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/services", tags=["services"])

_DESCRIPTIONS = {
    "puller": "Checks every 5 minutes if a new database exists on GitHub (via ETag) and downloads it when updated.",
    "generator": "Checks every 5 minutes whether any profile's own scheduled time has arrived to build today's betting slips.",
    "verifier": "Polls every 60 seconds to fetch live scores and settle completed matches on pending slips.",
}


def _get(request: Request):
    """Dependency: yield the shared AppLogic instance."""
    return request.app.state.app_logic


def _next_run_hour(hour: int | None, minute: int | None = 0) -> str | None:
    """Human-readable 'next run' for scheduled (daily) services."""
    if hour is None:
        return None
    if minute is None:
        minute = 0
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delta = target - now
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m = rem // 60
    label = "Today" if target.date() == now.date() else "Tomorrow"
    return f"{label} {target.strftime('%H:%M')} (in {h}h {m:02d}m)"


def _next_run_interval(interval_seconds: int | None) -> str | None:
    """Human-readable 'next run' for interval-based services."""
    if interval_seconds is None:
        return None
    minutes = interval_seconds // 60
    return f"Every {minutes} min"


def _earliest_profile_window(rows: list[dict]) -> tuple[int, int] | None:
    """Earliest per-profile generate window among active profiles.

    Per-profile windows only (user decision 2026-10-25): a profile without its
    own generate_hour/generate_minute has no window at all. Returns None when
    no active profile carries a window.
    """
    windows = [
        (int(r["generate_hour"]), int(r["generate_minute"] or 0))
        for r in rows
        if r.get("auto_generate") and r.get("generate_hour") is not None and r.get("generate_minute") is not None
    ]
    return min(windows) if windows else None


@router.get("")
def get_services(request: Request):
    """Return service info plus scheduler settings."""
    app = _get(request)
    runtime_cfg = app.settings.get("runtime_state") or {}
    now = datetime.now().isoformat()
    profile_rows = app.get_profile_schedules()
    # Generator scheduling is per-profile only: the generator card mirrors the
    # earliest active per-profile window (None when no profile has one).
    generator_window = _earliest_profile_window(profile_rows)

    services_out = {}
    for name, svc in app.services.items():
        # Determine next_run based on whether service is hour-based or interval-based
        # We now look at the config for 'hour' metadata as TickerService is pure polling
        hour = None
        minute = None
        if name == "generator" and generator_window is not None:
            hour, minute = generator_window

        if hour is not None:
            next_run = _next_run_hour(hour, minute)
        elif name == "generator":
            # Per-profile windows only: no active profile window -> no scheduled
            # next run (the ticker just polls and fires nothing).
            next_run = None
        elif svc.interval is not None:
            next_run = _next_run_interval(svc.interval)
        else:
            next_run = "Unknown"

        services_out[name] = {
            "name": name,
            "description": _DESCRIPTIONS.get(name, ""),
            "enabled": getattr(svc, "enabled", True),
            "alive": svc.is_alive(),
            "hour": hour,
            "minute": minute,
            "interval_seconds": svc.interval,
            "next_run": next_run,
            "last_time_generated": runtime_cfg.get("last_time_generated") if name == "generator" else None,
        }

    return {
        "services": services_out,
        "profile_schedules": profile_rows,
        "server_time": now,
    }


@router.post("/settings")
def save_settings(request: Request, body: ServicesSettingsIn):
    """Persist per-profile schedules (the only scheduling payload)."""
    app = _get(request)
    rows = [row.model_dump() for row in body.profile_schedules]
    app.save_profile_schedules(rows)
    return {"profile_schedules": rows}


@router.post("/{name}/toggle")
def toggle_service(request: Request, name: str):
    """Toggle a named service and return its new state."""
    new_state = _get(request).toggle_service(name)
    return {"name": name, "enabled": new_state}
