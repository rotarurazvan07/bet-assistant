"""
Advanced Web Scraping Framework for Linux
Modular architecture with Stealth and Retry engines

REQUIREMENTS:
1. Python packages:
   pip install playwright fake-useragent curl_cffi

2. System dependencies:
   playwright install chromium
   playwright install-deps
"""

import gc
import threading
import time
import random
from typing import Dict, Optional, Any, List
import json

from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("Warning: curl_cffi not available. Install with: pip install curl_cffi")


class StealthEngine:
    """
    Handles all stealth and anti-detection mechanisms.
    Provides browser fingerprints, headers, and evasion scripts.
    """

    BROWSER_PROFILES = [
        {
            'platform': 'Win32',
            'vendor': 'Google Inc.',
            'screen': {'width': 1920, 'height': 1080, 'depth': 24},
            'timezone': 'America/New_York',
            'locale': 'en-US'
        },
        {
            'platform': 'MacIntel',
            'vendor': 'Apple Computer, Inc.',
            'screen': {'width': 1440, 'height': 900, 'depth': 24},
            'timezone': 'America/Los_Angeles',
            'locale': 'en-US'
        },
        {
            'platform': 'Win32',
            'vendor': 'Google Inc.',
            'screen': {'width': 2560, 'height': 1440, 'depth': 24},
            'timezone': 'America/Chicago',
            'locale': 'en-US'
        },
        {
            'platform': 'X11',
            'vendor': 'Google Inc.',
            'screen': {'width': 1920, 'height': 1080, 'depth': 24},
            'timezone': 'Europe/London',
            'locale': 'en-GB'
        },
        {
            'platform': 'Win32',
            'vendor': 'Google Inc.',
            'screen': {'width': 1366, 'height': 768, 'depth': 24},
            'timezone': 'America/Denver',
            'locale': 'en-US'
        },
        {
            'platform': 'MacIntel',
            'vendor': 'Apple Computer, Inc.',
            'screen': {'width': 1680, 'height': 1050, 'depth': 24},
            'timezone': 'America/Phoenix',
            'locale': 'en-US'
        },
    ]

    def __init__(self, custom_headers: Optional[Dict[str, str]] = None):
        """
        Initialize stealth engine.

        Args:
            custom_headers: Additional headers to merge with stealth headers
        """
        self.ua = UserAgent()
        self.custom_headers = custom_headers or {}
        self._profile_counter = 0
        self._lock = threading.Lock()

    def get_profile(self, profile_id: int) -> Dict:
        """Get a browser profile by ID."""
        return self.BROWSER_PROFILES[profile_id % len(self.BROWSER_PROFILES)]

    def get_next_profile(self) -> tuple:
        """Get next profile with thread-safe counter."""
        with self._lock:
            profile_id = self._profile_counter
            self._profile_counter += 1
        return profile_id, self.get_profile(profile_id)

    def get_user_agent(self) -> str:
        """Generate random user agent."""
        desktop_user_agents = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            # Opera
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/95.0.0.0",
            # Safari (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15"
        ]
        return random.choice(desktop_user_agents)
    def get_headers(self, user_agent: Optional[str] = None) -> Dict[str, str]:
        """Generate stealth HTTP headers."""
        headers = {
            'User-Agent': user_agent or self.get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice([
                'en-US,en;q=0.9',
                'en-US,en;q=0.9,es;q=0.8',
                'en-GB,en;q=0.9',
                'en-US,en;q=0.8'
            ]),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Cache-Control': 'max-age=0',
        }
        headers.update(self.custom_headers)
        return headers

    def get_browser_args(self, profile: Dict) -> List[str]:
        """Generate browser launch arguments."""
        return [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-gpu',
            f'--window-size={profile["screen"]["width"]},{profile["screen"]["height"]}',
        ]

    def get_evasion_script(self, profile: Dict) -> str:
        """Generate JavaScript evasion script with unique fingerprint."""
        canvas_seed = random.randint(1000, 9999)

        return f"""
        Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
        Object.defineProperty(navigator, 'platform', {{ get: () => '{profile['platform']}' }});
        Object.defineProperty(navigator, 'vendor', {{ get: () => '{profile['vendor']}' }});
        Object.defineProperty(navigator, 'plugins', {{ get: () => new Array({random.randint(3, 6)}).fill(null) }});
        Object.defineProperty(navigator, 'languages', {{ get: () => ['{profile['locale']}', '{profile['locale'].split('-')[0]}'] }});
        window.chrome = {{ runtime: {{}}, loadTimes: function() {{}}, csi: function() {{}} }};

        const canvasSeed = {canvas_seed};
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function() {{
            const imageData = originalGetImageData.apply(this, arguments);
            if (canvasSeed > 0) {{
                for (let i = 0; i < imageData.data.length; i += 4) {{
                    imageData.data[i] = imageData.data[i] ^ (canvasSeed % 256);
                }}
            }}
            return imageData;
        }};

        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) return '{random.choice(['Intel Inc.', 'Google Inc. (NVIDIA)', 'Google Inc. (AMD)'])}';
            if (parameter === 37446) return '{random.choice(['Intel Iris OpenGL Engine', 'ANGLE (NVIDIA GeForce GTX 1050 Ti)', 'ANGLE (AMD Radeon)'])}';
            return getParameter.call(this, parameter);
        }};

        Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {random.choice([4, 6, 8, 12, 16])} }});
        Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {random.choice([4, 8, 16])} }});
        Object.defineProperty(screen, 'width', {{ get: () => {profile['screen']['width']} }});
        Object.defineProperty(screen, 'height', {{ get: () => {profile['screen']['height']} }});
        """


class RetryEngine:
    """
    Handles retry logic, timing, and page validation.
    Implements smart backoff strategies and detects blocking.
    """

    def __init__(
        self,
        max_retries: int = 3,
        detection_keywords: Optional[List[str]] = None
    ):
        """
        Initialize retry engine.

        Args:
            max_retries: Maximum number of retry attempts
            detection_keywords: Keywords that indicate blocking or loading
        """
        self.max_retries = max_retries
        self.detection_keywords = detection_keywords or []

    def is_blocked(self, html: str, min_length: int = 100) -> tuple:
        """
        Check if page is blocked or incomplete.

        Returns:
            (is_blocked: bool, reason: str)
        """
        if not html or len(html) < min_length:
            return True, "Empty or too short HTML"

        for keyword in self.detection_keywords:
            if keyword in html:
                return True, f"Detection keyword found: '{keyword}'"

        return False, ""

    def calculate_wait_time(
        self,
        attempt: int,
        min_wait: float,
        is_rate_limited: bool = False
    ) -> float:
        """
        Calculate smart wait time with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            min_wait: Minimum wait time in seconds
            is_rate_limited: If True, wait 3x longer

        Returns:
            Wait time in seconds
        """
        if attempt == 0:
            # First attempt: just add small random jitter
            return min_wait + random.uniform(0, 0.5)

        # Exponential backoff: min_wait * (1.5 ^ attempt) + jitter
        backoff = min_wait * (1.5 ** attempt)
        jitter = random.uniform(0, 2)
        wait_time = backoff + jitter

        # If rate limited, wait 3x longer
        if is_rate_limited:
            wait_time *= 3

        return wait_time

    def wait_for_content(
        self,
        get_content_fn,
        max_wait: int = 30,
        check_interval: float = 2.0
    ) -> bool:
        """
        Wait for blocking screens to disappear.

        Args:
            get_content_fn: Function that returns current page HTML
            max_wait: Maximum seconds to wait
            check_interval: Seconds between checks

        Returns:
            True if content loaded, False if still blocked
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                html = get_content_fn()
                is_blocked, reason = self.is_blocked(html)

                if not is_blocked:
                    return True

                time.sleep(check_interval)

            except Exception as e:
                print(f"Error while waiting for content: {str(e)}")
                time.sleep(check_interval)

        return False


class WebScraper:
    """
    Thread-safe web scraper with modular stealth and retry engines.
    Supports both browser automation and fast HTTP requests.
    """

    TIMEOUT = 60000  # Fixed 60 second timeout

    def __init__(
        self,
        custom_cookies: Optional[List[Dict[str, Any]]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        headless: bool = True,
        stealth_mode: bool = True,
        max_retries: int = 3,
        min_request_delay: float = 0.0,
        detection_keywords: Optional[List[str]] = None
    ):
        """
        Initialize web scraper.

        Args:
            custom_cookies: List of cookie dicts with 'name', 'value', 'domain', 'path', 'url'
            custom_headers: Custom headers to merge with stealth headers
            headless: Run browser in headless mode
            stealth_mode: Enable stealth engine
            max_retries: Maximum retry attempts
            min_request_delay: Minimum seconds between ANY requests (rate limiting)
            detection_keywords: Keywords indicating blocking/loading (merged list)
        """
        self.custom_cookies = custom_cookies or []
        self.headless = headless
        self.min_request_delay = min_request_delay

        # Initialize engines
        self.stealth_engine = StealthEngine(custom_headers) if stealth_mode else None
        self.retry_engine = RetryEngine(max_retries, detection_keywords)

        # Thread-local storage
        self._thread_local = threading.local()

        # Global rate limiting
        self._last_request_time = 0
        self._request_lock = threading.Lock()
        self._page_load_counter = 0
        self._counter_lock = threading.Lock()

    def _get_thread_browser(self):
        """Get or create browser instance for current thread."""
        if not hasattr(self._thread_local, 'page'):
            # Get unique profile from stealth engine
            if self.stealth_engine:
                thread_id, profile = self.stealth_engine.get_next_profile()
                user_agent = self.stealth_engine.get_user_agent()
                headers = self.stealth_engine.get_headers(user_agent)
                browser_args = self.stealth_engine.get_browser_args(profile)
                print(f"Thread {thread_id}: Starting with {profile['platform']} profile")
            else:
                thread_id = 0
                profile = {'screen': {'width': 1920, 'height': 1080}, 'locale': 'en-US', 'timezone': 'UTC'}
                user_agent = 'Mozilla/5.0'
                headers = {}
                browser_args = ['--no-sandbox', '--disable-gpu' if self.headless else '']

            # Start playwright
            self._thread_local.playwright = sync_playwright().start()
            self._thread_local.browser = self._thread_local.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args
            )

            # Create context
            self._thread_local.context = self._thread_local.browser.new_context(
                viewport={'width': profile['screen']['width'], 'height': profile['screen']['height']},
                user_agent=user_agent,
                extra_http_headers=headers,
                ignore_https_errors=True,
                java_script_enabled=True,
                locale=profile.get('locale', 'en-US'),
                timezone_id=profile.get('timezone', 'UTC'),
                screen={'width': profile['screen']['width'], 'height': profile['screen']['height']},
                device_scale_factor=1.0 + random.uniform(-0.1, 0.1),
                has_touch=random.choice([False, False, False, True]),
            )

            # Add cookies
            if self.custom_cookies:
                self._thread_local.context.add_cookies(self.custom_cookies)

            # Apply stealth script
            if self.stealth_engine:
                evasion_script = self.stealth_engine.get_evasion_script(profile)
                self._thread_local.context.add_init_script(evasion_script)

            # Create page
            self._thread_local.page = self._thread_local.context.new_page()
            self._thread_local.page.set_default_timeout(self.TIMEOUT)
            self._thread_local.thread_id = thread_id

        return self._thread_local.page

    def _enforce_rate_limit(self):
        """Enforce minimum delay between requests globally."""
        if self.min_request_delay <= 0:
            return

        with self._request_lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self.min_request_delay:
                sleep_time = self.min_request_delay - elapsed
                time.sleep(sleep_time)

            self._last_request_time = time.time()

    def _restart_browser_if_needed(self, threshold: int = 30) -> bool:
        """
        Check if page load count exceeds threshold and restart browser if needed.

        Args:
            threshold: Restart after this many page loads per thread

        Returns:
            True if browser was restarted, False otherwise
        """
        if not hasattr(self._thread_local, 'page_load_count'):
            self._thread_local.page_load_count = 0

        self._thread_local.page_load_count += 1

        if self._thread_local.page_load_count >= threshold:
            thread_id = getattr(self._thread_local, 'thread_id', 0)
            print(f"Thread {thread_id}: Browser restart at {self._thread_local.page_load_count} page loads (threshold: {threshold})")

            # Close and destroy current browser
            try:
                if hasattr(self._thread_local, 'page'):
                    self._thread_local.page.close()
                if hasattr(self._thread_local, 'context'):
                    self._thread_local.context.close()
                if hasattr(self._thread_local, 'browser'):
                    self._thread_local.browser.close()
                if hasattr(self._thread_local, 'playwright'):
                    self._thread_local.playwright.stop()
            except Exception as e:
                print(f"Thread {thread_id}: Error during browser cleanup: {str(e)}")

            # Clear thread-local storage to force recreation
            for attr in ['page', 'context', 'browser', 'playwright', 'page_load_count']:
                if hasattr(self._thread_local, attr):
                    delattr(self._thread_local, attr)

            # Reset counter
            self._thread_local.page_load_count = 0
            gc.collect()
            return True

        return False

    def load_page(
        self,
        url: str,
        wait_for: str = 'domcontentloaded',
        additional_wait: float = 0,
        wait_for_selector: Optional[str] = None,
        required_content: Optional[List[str]] = None,
        min_content_length: int = 1000
    ) -> str:
        """
        Load page using browser automation.

        Args:
            url: URL to load
            wait_for: 'load', 'domcontentloaded', or 'networkidle'
            additional_wait: Extra seconds to wait after page loads
            wait_for_selector: CSS selector to wait for
            required_content: Strings that must be in the page
            min_content_length: Minimum HTML length

        Returns:
            HTML content as string
        """
        print(url)
        self._restart_browser_if_needed(threshold=5)
        page = self._get_thread_browser()
        thread_id = getattr(self._thread_local, 'thread_id', 0)

        for attempt in range(self.retry_engine.max_retries):
            try:
                # Calculate and apply wait time for retries
                if attempt > 0:
                    wait_time = self.retry_engine.calculate_wait_time(attempt, self.min_request_delay, is_rate_limited=False)
                    print(f"Thread {thread_id}: Waiting {wait_time:.1f}s before retry {attempt + 1}/{self.retry_engine.max_retries}")
                    time.sleep(wait_time)

                # Enforce global rate limit before request
                self._enforce_rate_limit()

                # Navigate
                response = page.goto(url, wait_until=wait_for, timeout=self.TIMEOUT)
                time.sleep(random.uniform(1.5, 2.5))

                # Check response status
                if response:
                    if response.status == 429:
                        print(f"Thread {thread_id}: Rate limited (429)")
                        if attempt < self.retry_engine.max_retries - 1:
                            # Use longer wait for rate limits
                            wait_time = self.retry_engine.calculate_wait_time(attempt + 1, self.min_request_delay, is_rate_limited=True)
                            time.sleep(wait_time)
                            continue
                    elif response.status >= 400:
                        print(f"Thread {thread_id}: HTTP {response.status}")
                        if attempt < self.retry_engine.max_retries - 1:
                            continue

                # Wait for blocking to clear
                if not self.retry_engine.wait_for_content(lambda: page.content(), max_wait=20):
                    print(f"Thread {thread_id}: Page still blocked")
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                # Wait for selector
                if wait_for_selector:
                    try:
                        page.wait_for_selector(wait_for_selector, timeout=10000)
                    except:
                        if attempt < self.retry_engine.max_retries - 1:
                            continue

                # Additional wait
                if additional_wait > 0:
                    time.sleep(additional_wait)

                # Get content
                html = page.content()

                # Validate
                if len(html) < min_content_length:
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                if required_content and any(c not in html for c in required_content):
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                is_blocked, reason = self.retry_engine.is_blocked(html, min_content_length)
                if is_blocked:
                    print(f"Thread {thread_id}: {reason}")
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                return html

            except Exception as e:
                print(f"Thread {thread_id}: Error - {str(e)}")
                if attempt < self.retry_engine.max_retries - 1:
                    wait_time = self.retry_engine.calculate_wait_time(attempt, self.min_request_delay)
                    time.sleep(wait_time)

        return ""

    def fast_http_request(
        self,
        url: str,
        method: str = 'GET',
        data: Optional[Dict] = None,
        required_content: Optional[List[str]] = None,
        min_content_length: int = 1000,
        impersonate: str = 'chrome120'
    ) -> str:
        """
        Ultra-fast HTTP request with stealth.

        Args:
            url: URL to fetch
            method: HTTP method
            data: POST data if method is POST
            required_content: Strings that must be in response
            min_content_length: Minimum HTML length
            impersonate: Browser to impersonate

        Returns:
            HTML content as string
        """
        print(url)
        if not CURL_CFFI_AVAILABLE:
            print("curl_cffi not available, using browser mode")
            return self.load_page(url, required_content=required_content, min_content_length=min_content_length)

        for attempt in range(self.retry_engine.max_retries):
            try:
                # Calculate and apply wait time for retries
                if attempt > 0:
                    wait_time = self.retry_engine.calculate_wait_time(attempt, self.min_request_delay, is_rate_limited=False)
                    print(f"Fast HTTP: Waiting {wait_time:.1f}s before retry {attempt + 1}/{self.retry_engine.max_retries}")
                    time.sleep(wait_time)

                # Enforce global rate limit before request
                self._enforce_rate_limit()

                # Get stealth headers
                if self.stealth_engine:
                    headers = self.stealth_engine.get_headers()
                else:
                    headers = {'User-Agent': 'Mozilla/5.0'}

                # Add referer
                from urllib.parse import urlparse
                parsed = urlparse(url)
                headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"

                # Convert cookies
                cookies_dict = {}
                for cookie in self.custom_cookies:
                    cookies_dict[cookie.get('name', '')] = cookie.get('value', '')

                # Make request
                if method.upper() == 'GET':
                    response = curl_requests.get(
                        url, headers=headers, cookies=cookies_dict,
                        impersonate=impersonate, timeout=30, allow_redirects=True
                    )
                else:
                    response = curl_requests.post(
                        url, headers=headers, cookies=cookies_dict, data=data,
                        impersonate=impersonate, timeout=30, allow_redirects=True
                    )

                # Check status
                if response.status_code == 429:
                    print(f"Fast HTTP: Rate limited (429)")
                    if attempt < self.retry_engine.max_retries - 1:
                        # Use longer wait for rate limits
                        wait_time = self.retry_engine.calculate_wait_time(attempt + 1, self.min_request_delay, is_rate_limited=True)
                        time.sleep(wait_time)
                        continue
                elif response.status_code >= 400:
                    print(f"Fast HTTP: HTTP {response.status_code}")
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                html = response.text

                # Validate
                if len(html) < min_content_length:
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                if required_content and any(c not in html for c in required_content):
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                is_blocked, reason = self.retry_engine.is_blocked(html, min_content_length)
                if is_blocked:
                    print(f"Fast HTTP: {reason}")
                    if attempt < self.retry_engine.max_retries - 1:
                        continue

                return html

            except Exception as e:
                print(f"Fast HTTP: Error - {str(e)}")
                if attempt < self.retry_engine.max_retries - 1:
                    wait_time = self.retry_engine.calculate_wait_time(attempt, self.min_request_delay)
                    time.sleep(wait_time)

        return ""

    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in browser."""
        page = self._get_thread_browser()
        try:
            return page.evaluate(script, *args)
        except Exception as e:
            print(f"Error executing script: {str(e)}")
            return None

    def get_current_page(self) -> str:
        """Get current page HTML."""
        page = self._get_thread_browser()
        return page.content()

    def get_cookies(self) -> List[Dict]:
        """Get cookies from browser."""
        if hasattr(self._thread_local, 'context'):
            return self._thread_local.context.cookies()
        return []

    def set_cookies(self, cookies: List[Dict]):
        """Set cookies in browser."""
        if hasattr(self._thread_local, 'context'):
            self._thread_local.context.add_cookies(cookies)

    def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> bytes:
        """Take screenshot."""
        page = self._get_thread_browser()
        return page.screenshot(path=path, full_page=full_page)

    def destroy_current_thread(self):
        """Clean up browser for current thread."""
        if hasattr(self._thread_local, 'page'):
            try:
                self._thread_local.page.close()
                del self._thread_local.page
            except:
                pass

        if hasattr(self._thread_local, 'context'):
            try:
                self._thread_local.context.close()
                del self._thread_local.context
            except:
                pass

        if hasattr(self._thread_local, 'browser'):
            try:
                self._thread_local.browser.close()
                del self._thread_local.browser
            except:
                pass

        if hasattr(self._thread_local, 'playwright'):
            try:
                self._thread_local.playwright.stop()
                del self._thread_local.playwright
            except:
                pass

    def save_cookies_to_file(self, filepath: str):
        """Save cookies to JSON file."""
        cookies = self.get_cookies()
        with open(filepath, 'w') as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved {len(cookies)} cookies to {filepath}")

    @staticmethod
    def load_cookies_from_file(filepath: str) -> List[Dict]:
        """Load cookies from JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy_current_thread()
