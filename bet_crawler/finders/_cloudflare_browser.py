"""Cloudflare-aware browser session helper for bet-assistant finders.

Wraps scrape_kit.browser with a configuration that lowers headless-detection
signals, used by sources that Cloudflare escalates to a managed Turnstile challenge.
"""

from scrape_kit import browser

# Chromium flags that reduce the automated-browser surface.
_CF_EXTRA_FLAGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-translate",
]

# Playwright *context* options, not CLI flags (see __generate_options__).
_CF_ADDITIONAL_ARGS = {
    "hide_canvas": True,
    "block_webrtc": True,
}


def cf_browser(
    *,
    headless: bool = True,
    solve_cloudflare: bool = True,
    interactive: bool = True,
    **kwargs,
):
    """Open a browser session configured to reduce Cloudflare headless detection.

    Args:
        headless: Run the browser in headless mode.
        solve_cloudflare: Enable scrapling's Cloudflare solver.
        interactive: Enable interactive features (network idle, etc.).
        **kwargs: Extra keyword arguments forwarded to scrape_kit.browser.

    Returns:
        An InteractiveSession instance from scrape_kit.browser.
    """
    kwargs.setdefault(
        "useragent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    kwargs.setdefault("extra_flags", [])
    kwargs.setdefault("additional_args", {})
    kwargs["extra_flags"] = kwargs["extra_flags"] + _CF_EXTRA_FLAGS
    kwargs["additional_args"] = {**_CF_ADDITIONAL_ARGS, **kwargs["additional_args"]}

    return browser(
        headless=headless,
        solve_cloudflare=solve_cloudflare,
        interactive=interactive,
        **kwargs,
    )
