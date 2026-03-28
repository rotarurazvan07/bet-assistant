from scrape_kit import (  # noqa: F401 — ScrapeMode re-exported for crawlers
    ScrapeMode,
    WebFetcher,
)
from scrape_kit.fetcher import InteractiveSession  # noqa: F401

_w = WebFetcher(
    retry_indicators=[
        "403 Forbidden",
        "Access Denied",
        "429 Too Many Requests",
        "Too Many Requests",
        "rate limit exceeded",
        "rate limited",
        "Request throttled",
        "Service Unavailable",
        "503 Service Unavailable",
        "Temporarily Unavailable",
        "overloaded",
        "quota exceeded",
        "Just a moment",
        "Checking your browser",
        "verify you are a human",
        # "turnstile", "cf-chl-widget", "Cloudflare",
    ],
    block_indicators=[
        "Just a moment...",
        "cf-browser-verification",
        "Access Denied",
        "Checking your browser",
        "verify you are a human",
        "403 Forbidden",
        "429 Too Many Requests",
        "Attention Required!",
    ],
)


class WebScraper:
    fetch = staticmethod(_w.fetch)
    is_blocked = staticmethod(_w.is_blocked)
    browser = staticmethod(_w.browser)
    scrape = staticmethod(_w.scrape)
