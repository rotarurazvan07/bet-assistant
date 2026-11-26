"""Shared helpers for browser-driven finders: navigate with Cloudflare solving."""

# Genuine "Cloudflare is still holding the page" markers. Note that
# 'challenge-platform' also appears in the beacon script Cloudflare injects
# into normal pages, so it is deliberately NOT a block signal on its own.
_CHALLENGE_MARKERS = (
    "Just a moment...",
    "Verifying you are human.",
)


def fetch_page(session, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 60000) -> str:
    """Navigate with Cloudflare solving and return the page HTML.

    InteractiveSession.fetch() calls page.goto() directly, so a browser() opened
    with solve_cloudflare=True never engages scrapling's challenge solver, and
    session.page stays on about:blank. The wrapped scrapling session does run the
    solver, waits for page stability and network idle, and returns the settled
    content, so navigate and read through it.

    Raises:
        RuntimeError: describing the served page when it is still a challenge.
    """
    html = session.session.fetch(url, wait_until=wait_until, timeout=timeout_ms).html_content or ""
    marker = next((m for m in _CHALLENGE_MARKERS if m in html), None)
    if marker:
        import re

        title = re.search(r"<title>(.*?)</title>", html, re.S)
        raise RuntimeError(
            f"len={len(html)}, title={title.group(1) if title else ''!r}, final_url={url!r}, blocked_marker={marker!r}"
        )
    return html
