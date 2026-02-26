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


class InteractiveSession:
    """Wrapper around Scrapling session to provide persistent page and JS execution."""
    def __init__(self, session):
        self.session = session
        self.page = None

    def __enter__(self):
        self.session.start()
        # Create a persistent page that we control
        self.page = self.session.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.page:
                self.page.close()
        except:
            pass
        self.session.close()

    def fetch(self, url, timeout=60000):
        if not self.page:
            raise RuntimeError("Session not started. Use 'with WebScraper.browser(...) as session:'")

        self.page.goto(url, wait_until="load", timeout=timeout)
        # Forebet and others need a moment for background scripts to run
        self.page.wait_for_timeout(2000)

        class ResponseStub:
            def __init__(self, content):
                self.html_content = content
        return ResponseStub(self.page.content())

    def execute_script(self, script):
        if not self.page:
            raise RuntimeError("Call fetch() first")

        clean_script = script.strip()
        try:
            if clean_script.startswith("return "):
                return self.page.evaluate(f"() => {{ {clean_script} }}")
            return self.page.evaluate(script)
        except Exception as e:
            raise e

    def wait_for_selector(self, selector, timeout=30000):
        if not self.page:
            raise RuntimeError("Call fetch() first")
        self.page.wait_for_selector(selector, timeout=timeout)

    def wait_for_function(self, expression, timeout=30000):
        if not self.page:
            raise RuntimeError("Call fetch() first")
        self.page.wait_for_function(expression, timeout=timeout)

    def click(self, selector, timeout=30000):
        if not self.page:
            raise RuntimeError("Call fetch() first")
        self.page.click(selector, timeout=timeout)

    def wait_for_timeout(self, ms):
        if not self.page:
            raise RuntimeError("Call fetch() first")
        self.page.wait_for_timeout(ms)

    def __getattr__(self, name):
        return getattr(self.session, name)


class WebScraper:
    """
    Static scraping utility.

    Usage — fast HTTP:
        html = WebScraper.fetch("https://example.com")

    Usage — browser session (lean):
        with WebScraper.browser() as session:
            page = session.fetch("https://example.com")

    Usage — interactive browser (for JS automation):
        with WebScraper.browser(interactive=True) as session:
            session.fetch("https://example.com")
            session.execute_script("window.scrollTo(0, document.body.scrollHeight)")
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
    def browser(headless: bool = True, solve_cloudflare: bool = False, interactive: bool = False):
        """Get a browser session as a context manager.

        If interactive=True: returns InteractiveSession supporting execute_script.
        Otherwise: returns lean Scrapling session.
        """
        if solve_cloudflare:
            session = StealthySession(
                headless=headless,
                solve_cloudflare=True,
                # Cloudflare/DataDome need JS/CSS to run the challenge
                disable_resources=False,
                network_idle=True
            )
        else:
            session = DynamicSession(
                headless=headless,
                disable_resources=(not interactive),
                network_idle=interactive
            )

        if interactive:
            return InteractiveSession(session)
        return session

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
                                # High stealth: allow resources and wait for network idle
                                page = await session.fetch(url, disable_resources=False, network_idle=True)
                                callback(url, page.html_content)
                            except Exception as e:
                                print(f"[scrape/stealth] Error on {url}: {e}")

                    await asyncio.gather(*[_fetch_one(u) for u in urls])

            asyncio.run(_run())
