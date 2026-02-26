"""
Web Scraping Framework using Scrapling
Static utility with three entry points:
    WebScraper.fetch(url)          — fast HTTP GET with stealth headers
    WebScraper.browser(...)        — interactive headless browser session
    WebScraper.scrape(urls, ...)   — batch scrape with concurrency + callback

REQUIREMENTS:
    pip install "scrapling[fetchers]"
    scrapling install
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from scrapling.fetchers import (
    Fetcher,
    DynamicSession,
    StealthySession,
    AsyncStealthySession,
)


class ScrapeMode:
    """Scraping mode constants."""
    FAST = "fast"          # Simple HTTP with TLS impersonation
    STEALTH = "stealth"    # Headless browser, Cloudflare bypass


class WebScraper:
    """
    Static scraping utility.

    Usage — fast HTTP:
        html = WebScraper.fetch("https://example.com")

    Usage — browser session:
        with WebScraper.browser(solve_cloudflare=True) as session:
            page = session.fetch("https://example.com")
            session.execute_script("return document.title")

    Usage — batch scrape with concurrency:
        WebScraper.scrape(urls, callback=my_handler, mode=ScrapeMode.FAST, max_concurrency=5)
    """

    @staticmethod
    def fetch(url: str) -> str:
        """Fast HTTP GET with TLS impersonation and stealth headers.
        Returns HTML string, or empty string on error.
        """
        try:
            page = Fetcher.get(url, stealthy_headers=True)
            return page.html_content
        except Exception as e:
            print(f"[fetch] Error fetching {url}: {e}")
            return ""

    @staticmethod
    def browser(headless: bool = True, solve_cloudflare: bool = False):
        """Get an interactive browser session as a context manager.

        Returns a context manager. The session supports:
            session.fetch(url)              — navigate and get page
            session.execute_script(script)  — run JS on current page
        """
        if solve_cloudflare:
            return StealthySession(headless=headless, solve_cloudflare=True)
        return DynamicSession(headless=headless, disable_resources=False, network_idle=True)

    @staticmethod
    def scrape(urls, callback, mode=ScrapeMode.FAST, max_concurrency=1):
        """Batch scrape URLs with concurrency.

        Calls callback(url, html) for each successfully fetched page.

        Args:
            urls:             List of URLs to scrape.
            callback:         Called as callback(url, html) for each result.
            mode:             ScrapeMode.FAST or ScrapeMode.STEALTH.
            max_concurrency:  Maximum concurrent requests.
        """
        if not urls:
            return

        if mode == ScrapeMode.FAST:
            def _fetch(url):
                try:
                    html = WebScraper.fetch(url)
                    if html:
                        callback(url, html)
                except Exception as e:
                    print(f"[scrape/fast] Error on {url}: {e}")

            with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
                pool.map(_fetch, urls)

        elif mode == ScrapeMode.STEALTH:
            async def _run():
                async with AsyncStealthySession(
                    max_pages=max_concurrency, headless=True, solve_cloudflare=True
                ) as session:
                    sem = asyncio.Semaphore(max_concurrency)

                    async def _fetch_one(url):
                        async with sem:
                            try:
                                page = await session.fetch(url)
                                callback(url, page.html_content)
                            except Exception as e:
                                print(f"[scrape/stealth] Error on {url}: {e}")

                    await asyncio.gather(*[_fetch_one(u) for u in urls])

            asyncio.run(_run())
