"""Shared helpers for browser-driven finders: navigate with Cloudflare solving.

Cloudflare's managed Turnstile challenge is only solvable when both the browser's
fingerprint and the click target's rendered markup look right. When the solver
fails, the helpers here dump exactly that state, so the cause can be read from a
log line or a JSON dump instead of guessed at.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

# Genuine "Cloudflare is still holding the page" markers. Note that
# 'challenge-platform' also appears in the beacon script Cloudflare injects
# into normal pages, so it is deliberately NOT a block signal on its own.
_CHALLENGE_MARKERS = (
    "Just a moment...",
    "Verifying you are human.",
)

# Set this env var on a run to dump full diagnostics for every failed solve.
DIAG_DIR_ENV = "CF_DIAGNOSTICS_DIR"

# Selectors scrapling's solver can click, with the reason each matters.
_CLICK_TARGETS = (
    (
        ".main-content p+div>div>div",
        "non-embedded challenge fallback (the one that times out)",
    ),
    (".main-content", "container of the whole challenge body"),
    (".main-content > div", "direct child div of that container"),
    (".main-content p", "a <p> inside the container"),
    ("#cf_turnstile", "Turnstile iframe root"),
    ("#cf_turnstile > div", "inner div of the Turnstile root"),
    ("#cf-turnstile", "legacy Turnstile root"),
    (".turnstile > div > div", "legacy Turnstile inner"),
    (".zone-name-title", "zone-name element the solver also waits on"),
)

# Fingerprint signals Cloudflare scores. Reported from the live page because
# the wrapped session's own page is pooled and closed after each fetch.
_FINGERPRINT_JS = """() => {
    const nav = navigator, scr = window.screen;
    return {
        userAgent: nav.userAgent,
        platform: nav.platform,
        vendor: nav.vendor,
        webdriver: nav.webdriver,
        hardwareConcurrency: nav.hardwareConcurrency,
        deviceMemory: nav.deviceMemory,
        plugins: nav.plugins ? nav.plugins.length : null,
        screen: {w: scr.width, h: scr.height, dpr: scr.devicePixelRatio, colorDepth: scr.colorDepth},
        window: {innerW: window.innerWidth, innerH: window.innerHeight,
                 outerW: window.outerWidth, outerH: window.outerHeight},
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        timezoneOffset: new Date().getTimezoneOffset(),
        touchPoints: nav.maxTouchPoints,
        pdfViewerEnabled: nav.pdfViewerEnabled,
        chromeObjectPresent: typeof window.chrome !== 'undefined',
        outerWidthZero: window.outerWidth === 0,
        languages: nav.languages,
    };
}"""

_CONTEXT_QUERIES = tuple(sel for sel, _ in _CLICK_TARGETS) + (
    ".main-wrapper",
    ".main-content > noscript",
)


def _safe(fn, default=None):
    """Run a diagnostic probe; never let it break the scrape."""
    try:
        return fn()
    except Exception:  # noqa: BLE001 - diagnostics must never fail the run
        return default


def _details(html: str) -> dict:
    """Extract what identifies the challenge Cloudflare served."""
    out: dict = {"len": len(html)}
    for key, pattern in (
        ("challenge_type", r"cType:\s*'([^']+)'"),
        ("ray_id", r"cRay:\s*'([^']+)'"),
        ("zone", r"cZone:\s*'([^']+)'"),
        ("cf_time", r"cITimeS:\s*'([^']+)'"),
    ):
        m = re.search(pattern, html)
        out[key] = m.group(1) if m else None
    out["has_turnstile_script_tag"] = "challenges.cloudflare.com/turnstile" in html
    out["has_cf_chl_opt"] = "cf_chl_opt" in html
    out["has_main_content"] = "main-content" in html
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    out["title"] = m.group(1).strip() if m else None
    return out


def _markup_probe(html: str) -> dict:
    """Report which of the solver's click targets exist in the served markup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    labels = dict(_CLICK_TARGETS)
    probe = {}
    for selector in _CONTEXT_QUERIES:
        try:
            nodes = soup.select(selector)
        except Exception:  # noqa: BLE001 - unsupported selector syntax
            nodes = []
        probe[selector] = {
            "why": labels.get(selector, "structural context"),
            "count": len(nodes),
            "notes": [n.get("class") for n in nodes[:3]],
        }
    iframes = [
        {"src": (f.get("src") or "")[:120], "id": f.get("id"), "title": f.get("title")}
        for f in soup.find_all("iframe")
    ]
    probe["_challenge_iframes"] = iframes
    return probe


def describe_challenge(session, html: str) -> dict:
    """Everything needed to decide why the solver could not clear the challenge."""
    live_page = _safe(lambda: session.page)
    return {
        "challenge_page_details": _details(html),
        "served_markup_probe": _markup_probe(html),
        "browser_fingerprint": _safe(lambda: live_page.evaluate(_FINGERPRINT_JS)),
        "wrapper_page_url": _safe(lambda: live_page.url),
        "cookies": _safe(lambda: [c["name"] for c in live_page.context.cookies()], []),
        "cf_clearance_present": "cf_clearance"
        in (_safe(lambda: [c["name"] for c in live_page.context.cookies()], []) or []),
    }


def _maybe_dump(details: dict, url: str, html: str) -> None:
    """Write diagnostics to CF_DIAGNOSTICS_DIR when the environment sets it."""
    raw = os.environ.get(DIAG_DIR_ENV)
    if not raw:
        return
    try:
        d = Path(raw)
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:60]
        (d / f"cf_diag_{slug}_{stamp}.json").write_text(
            json.dumps(details, indent=2, default=str), encoding="utf-8"
        )
        (d / f"cf_diag_{slug}_{stamp}.challenge.html").write_text(
            html, encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 - never fail the scrape over diagnostics
        pass


def fetch_page(
    session, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 60000
) -> str:
    """Navigate with Cloudflare solving and return the page HTML.

    InteractiveSession.fetch() calls page.goto() directly, so a browser() opened
    with solve_cloudflare=True never engages scrapling's challenge solver, and
    session.page stays on about:blank. The wrapped scrapling session does run the
    solver, waits for page stability and network idle, and returns the settled
    content, so navigate and read through it.

    Raises:
        RuntimeError: describing the served page when it is still a challenge.
    """
    html = (
        session.session.fetch(
            url, wait_until=wait_until, timeout=timeout_ms
        ).html_content
        or ""
    )
    marker = next((m for m in _CHALLENGE_MARKERS if m in html), None)
    if marker:
        details = describe_challenge(session, html)
        _maybe_dump(details, url, html)
        d = details["challenge_page_details"]
        raise RuntimeError(
            f"len={d['len']}, title={d['title']!r}, final_url={url!r}, "
            f"blocked_marker={marker!r}, cf_clearance_present={details['cf_clearance_present']}, "
            f"challenge_type={d['challenge_type']!r}, ray_id={d['ray_id']!r}"
        )
    return html
