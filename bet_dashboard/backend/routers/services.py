from __future__ import annotations

from datetime import datetime, timedelta

from core.schemas import ServicesSettingsIn
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/services", tags=["services"])

_DESCRIPTIONS = {
    "puller": "Downloads the latest matches database from GitHub Releases",
    "generator": "Runs all active betting profiles and creates new slips",
    "verifier": "Checks live scores and settles pending legs every 60 s",
}


def _get(request: Request):
    return request.app.state.app_logic


def _next_run_hour(hour: int | None) -> str | None:
    """Human-readable 'next run' for scheduled (hourly) services."""
    if hour is None:
        return None
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
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


@router.get("")
def get_services(request: Request):
    app = _get(request)
    svc_cfg = app.settings.get("services") or {}
    now = datetime.now().isoformat()

    services_out = {}
    for name, svc in app.services.items():
        # Determine next_run based on whether service is hour-based or interval-based
        # We now look at the config for 'hour' metadata as TickerService is pure polling
        hour = None
        if name == "generator":
            hour = svc_cfg.get("generate_hour")

        if hour is not None:
            next_run = _next_run_hour(hour)
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
            "interval_seconds": svc.interval,
            "next_run": next_run,
        }

    return {
        "services": services_out,
        "generate_hour": svc_cfg.get("generate_hour", 8),
        "server_time": now,
    }


@router.post("/settings")
def save_settings(request: Request, body: ServicesSettingsIn):
    _get(request).save_service_settings(body.generate_hour)
    return {"generate_hour": body.generate_hour}


@router.post("/{name}/toggle")
def toggle_service(request: Request, name: str):
    new_state = _get(request).toggle_service(name)
    return {"name": name, "enabled": new_state}
