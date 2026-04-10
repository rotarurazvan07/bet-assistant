from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request

from core.schemas import ServicesSettingsIn

router = APIRouter(prefix="/api/services", tags=["services"])

_DESCRIPTIONS = {
    "puller":    "Downloads the latest matches database from GitHub Releases",
    "generator": "Runs all active betting profiles and creates new slips",
    "verifier":  "Checks live scores and settles pending legs every 60 s",
}


def _get(request: Request):
    return request.app.state.app_logic


def _next_run(hour: int | None) -> str | None:
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


@router.get("")
def get_services(request: Request):
    app = _get(request)
    svc_cfg = app.settings.get("services") or {}
    now = datetime.now().isoformat()

    services_out = {}
    for name, svc in app.services.items():
        services_out[name] = {
            "name": name,
            "description": _DESCRIPTIONS.get(name, ""),
            "enabled": getattr(svc, "enabled", True),
            "alive": svc.is_alive(),
            "hour": svc.hour,
            "interval_seconds": svc.interval,
            "next_run": _next_run(svc.hour) if svc.hour is not None else "Every 60 s",
        }

    return {
        "services": services_out,
        "pull_hour": svc_cfg.get("pull_hour", 6),
        "generate_hour": svc_cfg.get("generate_hour", 8),
        "server_time": now,
    }


@router.post("/settings")
def save_settings(request: Request, body: ServicesSettingsIn):
    _get(request).save_service_settings(body.pull_hour, body.generate_hour)
    return {"pull_hour": body.pull_hour, "generate_hour": body.generate_hour}


@router.post("/{name}/toggle")
def toggle_service(request: Request, name: str):
    new_state = _get(request).toggle_service(name)
    return {"name": name, "enabled": new_state}
