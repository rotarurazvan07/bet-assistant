"""Contract: exactly one layer owns CORS for /api.

The CI e2e stack serves the SPA from nginx on :3002 and proxies /api to uvicorn.
nginx `add_header` APPENDS to the upstream response headers instead of replacing
them, and FastAPI's CORSMiddleware already emits `Access-Control-Allow-Origin`
for the allowlisted e2e origin. An nginx-level ACAO therefore ships the header
twice and the browser rejects the response outright ("the value of the
'Access-Control-Allow-Origin' header contains multiple values"), which surfaces
as every /api XHR failing its access-control check. This is the PR #104
two-stage regression: allow_origins first, then a duplicate nginx header.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NGINX_CONF = REPO_ROOT / "setup" / "nginx.conf"
MAIN_PY = REPO_ROOT / "bet_dashboard" / "backend" / "main.py"


def _api_location_body() -> list[str]:
    """Lines of the `location /api/ { ... }` block (braces on their own lines)."""
    inside = False
    body: list[str] = []
    for line in NGINX_CONF.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("location /api/ {"):
            inside = True
            continue
        if inside:
            if stripped == "}":
                break
            body.append(line)
    return body


def test_nginx_api_location_adds_no_access_control_headers() -> None:
    offenders = [
        line.strip()
        for line in _api_location_body()
        if "add_header" in line and "Access-Control-Allow" in line
    ]
    assert not offenders, (
        "nginx /api/ must not add Access-Control-Allow-* headers: add_header appends to the "
        "upstream response, so FastAPI's CORSMiddleware value is shipped twice and browsers "
        "reject the duplicate. Offenders: " + repr(offenders)
    )


def test_fastapi_allowlists_the_e2e_stack_origin() -> None:
    source = MAIN_PY.read_text(encoding="utf-8")
    assert '"http://localhost:3002"' in source, (
        "CORSMiddleware allow_origins must keep the CI e2e stack origin "
        "(http://localhost:3002); nginx does not compensate for its absence."
    )


def test_fastapi_uses_cors_middleware() -> None:
    assert "CORSMiddleware" in MAIN_PY.read_text(encoding="utf-8"), (
        "main.py must register CORSMiddleware for /api."
    )


def test_nginx_api_location_does_not_hide_upstream_cors_headers() -> None:
    """A proxy_hide_header/proxy_pass_header workaround would reintroduce the split owner."""
    body = "\n".join(_api_location_body()).lower()
    assert "proxy_hide_header" not in body and "proxy_pass_header" not in body, (
        "keep CORS ownership in one layer: do not add proxy_hide_header/proxy_pass_header "
        "workarounds to the nginx /api/ location."
    )
