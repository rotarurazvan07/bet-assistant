"""Shared helpers for browser-driven finders: wait for content, diagnose failures."""

from bet_crawler.crawler_logging import get_logger

logger = get_logger(__name__)

# Markers that identify a page Cloudflare served instead of the site's content.
_CF_MARKERS = (
    "Just a moment...",
    "Verifying you are human.",
    "challenge-platform",
    "cf-browser-verification",
    "Access Denied",
    "Attention Required",
)


def describe_page(session) -> str:
    """Summarise what the browser is actually showing, for failure diagnostics."""
    try:
        html = session.page.content()
    except Exception:  # noqa: BLE001 - diagnostics must never mask the original error
        return "page content unavailable"
    marker = next((m for m in _CF_MARKERS if m in html), None)
    try:
        title = session.page.title() or ""
    except Exception:  # noqa: BLE001
        title = ""
    return (
        f"len={len(html)}, title={title!r}, final_url={session.page.url!r}, "
        f"blocked_marker={marker!r}, has_target={'#body-main' in html or 'wdwtablest' in html or 'featurescore' in html}"
    )


def wait_for_content(session, selector: str, timeout_ms: int) -> str:
    """Wait for the client-rendered content container, then return the settled HTML.

    Raises:
        TimeoutError: with a description of what the page actually contained.
    """
    try:
        session.page.wait_for_selector(selector, state="attached", timeout=timeout_ms)
    except Exception as exc:
        raise TimeoutError(
            f"{describe_page(session)} | waiting for {selector!r}: {exc}"
        ) from exc
    return session.page.content()
