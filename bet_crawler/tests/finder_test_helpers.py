"""Shared helpers for finder tests (issue #69, cycle 8)."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "html"

DEFAULT_SKIP_PATTERNS = (
    (r"\bU\d{2}s?\b", "Youth team"),
    (r"\bW\b", "Women's team"),
    (r"\bII\b", "Reserve team II"),
    (r"\b2\b", "Reserve team 2"),
    (r"\bIII\b", "Reserve team III"),
    (r"\bB\b", "B team"),
    (r"\bC\b", "C team"),
    (r"\b(Am)\b", "Amateur"),
    (r"\bRes\b", "Reserve team"),
)


def load_fixture(key, name):
    """Read a committed HTML fixture from tests/fixtures/html/<key>/<name>."""
    return (FIXTURE_DIR / key / name).read_text(encoding="utf-8")


class MatchCollector:
    """Records matches passed to add_match_callback."""

    def __init__(self) -> None:
        self.matches = []

    def __call__(self, match) -> None:
        self.matches.append(match)

    def __len__(self):
        return len(self.matches)

    @property
    def first(self):
        return self.matches[0] if self.matches else None


def make_finder(
    finder_cls,
    collector=None,
    contributes_odds: bool = False,
    top_leagues_only: bool = True,
    num_days_ahead=1,
    local_timezone="Europe/Bucharest",
    skip_patterns=None,
):
    """Build a finder with the CrawlerFactory constructor contract (cycle 7)."""
    if collector is None:
        collector = MatchCollector()
    finder = finder_cls(
        collector,
        contributes_odds=contributes_odds,
        top_leagues_only=top_leagues_only,
        num_days_ahead=num_days_ahead,
        local_timezone=local_timezone,
        skip_patterns=skip_patterns
        if skip_patterns is not None
        else DEFAULT_SKIP_PATTERNS,
    )
    return finder, collector


def relax_date_window(finder):
    """Fixture dates are far-future (2035): bypass the date gate for parse tests.

    Date policy itself is pinned with dynamic dates in test_base_finder.py (D2).
    """

    def always_valid(dt) -> bool:
        return True

    finder.validate_match_date = always_valid
    return finder


def patch_fetch(monkeypatch, finder_module, responses) -> None:
    """Patch module-level fetch(url, **kw). responses: {url: html} or callable."""
    if callable(responses):
        monkeypatch.setattr(finder_module, "fetch", responses)
        return

    def fake_fetch(url, **kwargs):
        if url in responses:
            return responses[url]
        raise KeyError(f"unexpected fetch: {url}")

    monkeypatch.setattr(finder_module, "fetch", fake_fetch)


def patch_scrape(monkeypatch, finder_module, pages) -> None:
    """Patch module-level scrape(urls, callback, **kw) feeding HTML per url."""

    def fake_scrape(urls, callback, **kwargs) -> None:
        for url in urls:
            if url in pages:
                callback(url, pages[url])

    monkeypatch.setattr(finder_module, "scrape", fake_scrape)


class FakeBrowserSession:
    """Patch target for scrape_kit browser() sessions.

    Supports the three usage patterns in the codebase:
    - session.fetch(url) -> str HTML             (WhoScored discovery; scrape-kit@v0.2.2)
    - session.execute_script(...)                (xGScore discovery)
    - session.page.content() + session.click(sel, label) (OddsPortal/BetExplorer)

    content_map: {url: html | callable(clicks_list) -> html}. When a callable is
    supplied it receives the ordered list of clicked labels so far — tab-based
    odds finders swap page content per click this way.
    """

    def __init__(self, content_map, fetch_error_urls=()) -> None:
        self.content_map = content_map
        self.fetch_error_urls = set(fetch_error_urls)
        self.fetched = []
        self.clicks = []
        # (selector, label) pairs — pins click targets (2026-10-12 OP button fix)
        self.click_calls = []
        self._current_url = None
        self.page = self

    def fetch(self, url, **kwargs):
        self.fetched.append(url)
        if url in self.fetch_error_urls:
            raise RuntimeError("fetch failed")
        self._current_url = url
        return self.html_content

    def click(self, selector, label=None) -> bool:
        self.clicks.append(label if label is not None else selector)
        self.click_calls.append((selector, label))
        return True

    def execute_script(self, script) -> bool:
        return True

    @property
    def html_content(self):
        content = self.content_map.get(self._current_url, "")
        return content(self.clicks) if callable(content) else content

    def content(self):
        content = self.content_map.get(self._current_url, "")
        return content(self.clicks) if callable(content) else content

    def wait_for_selector(self, selector, state=None, timeout=None):
        return None


def fake_browser(monkeypatch, finder_module, content_map, fetch_error_urls=()):
    """Patch browser(...) context manager in the finder's module namespace.

    Returns the shared FakeBrowserSession so tests can assert fetches/clicks.
    """
    session = FakeBrowserSession(content_map, fetch_error_urls)

    @contextmanager
    def fake_browser_ctx(**kwargs):
        yield session

    monkeypatch.setattr(finder_module, "browser", fake_browser_ctx)
    return session


class FakeAnchor:
    """Minimal odds-cell anchor; hover() mounts this cell's tooltip (B2 tests)."""

    def __init__(self, text, page, index) -> None:
        self.text = text
        self.page = page
        self.index = index

    def text_content(self, timeout=None) -> str:
        return self.text

    def hover(self, timeout=None) -> None:
        self.page.mount(self.index)


class FakeLocator:
    """Playwright-ish locator over a fixed item list (count/nth/first/filter)."""

    def __init__(self, items) -> None:
        self._items = list(items)

    def count(self) -> int:
        return len(self._items)

    def nth(self, i):
        return self._items[i]

    @property
    def first(self):
        return self._items[0]

    def filter(self, has_text=None):
        return self

    def locator(self, selector):
        """Delegate a nested locator to the single held item (tbody.locator('tr'))."""
        return self._items[0].locator(selector)


class FakeRow:
    """Minimal table row: inner_text() is its line label, locator('a') its cells."""

    def __init__(self, line, anchors) -> None:
        self.line = line
        self.anchors = anchors

    def inner_text(self, timeout=None) -> str:
        return self.line

    def locator(self, selector):
        return FakeLocator(self.anchors if selector == "a" else [])


class FakeTooltipPage:
    """Headless odds-table page for movement tests (issue #105 / CR #106).

    content() returns the current HTML; hovering an anchor mounts that cell's
    ODDS MOVEMENT tooltip div, so pre-hover popups stay mounted (B2 race).
    """

    def __init__(self, base_html, tooltips) -> None:
        self.html = base_html
        self.tooltips = tooltips
        self.content_calls = 0
        self.mounted = set()
        self.tbody = FakeTbody(self)

    def content(self) -> str:
        self.content_calls += 1
        return self.html

    def mount(self, index) -> None:
        if index not in self.mounted and index < len(self.tooltips):
            self.mounted.add(index)
            self.html += self.tooltips[index]

    def locator(self, selector):
        return FakeLocator(
            [self.tbody] if selector == "table.w-full.table-fixed tbody" else []
        )


class FakeTbody:
    """Hands out the rows a caller pre-registered on the page."""

    def __init__(self, page) -> None:
        self.page = page
        self.rows = []

    def locator(self, selector):
        return FakeLocator(self.rows if selector == "tr" else [])


def make_tooltip_session(page, rows):
    """Wire a session over an existing FakeTooltipPage with the given rows."""
    page.locator("table.w-full.table-fixed tbody").first.rows = rows
    return SimpleNamespace(page=page)
