"""Stage 2: scrape tests (issue #68).

Pins: URL input (file vs string), per-domain grouping, matches written to
class chunk .db via MatchesManager, per-group exception isolation, reset semantics.
All finders are stubs — zero network.
"""

from bet_crawler.crawl_core.scrape import scrape
from bet_framework.MatchesManager import MatchesManager

from .conftest import StubCrawler, StubFactory, make_match


def _fetch(db_path):
    mm = MatchesManager(db_path, similarity_config=None)
    try:
        return mm.fetch_matches()
    finally:
        mm.close()


class TestScrapeP0:
    def test_reads_urls_from_file_and_writes_matches_db(self, tmp_path):
        urls_file = tmp_path / "chunk-1-urls.txt"
        urls_file.write_text("https://a.com/1,https://a.com/2")
        match = make_match(url="https://a.com/1")
        crawler = StubCrawler([], matches=[match])
        factory = StubFactory({}, url_to_crawler={"a": crawler})
        db = tmp_path / "chunk-1.db"
        scrape(str(db), str(urls_file), factory)
        df = _fetch(str(db))
        assert len(df) == 1
        assert df.iloc[0]["home_name"] == "Team A"
        assert df.iloc[0]["result_url"] == "https://a.com/1"

    def test_reads_urls_from_comma_string(self, tmp_path):
        match = make_match(home="X FC", url="https://a.com/1")
        crawler = StubCrawler([], matches=[match])
        factory = StubFactory({}, url_to_crawler={"a": crawler})
        db = tmp_path / "chunk-1.db"
        scrape(str(db), "https://a.com/1, https://a.com/2", factory)
        df = _fetch(str(db))
        assert len(df) == 1
        assert df.iloc[0]["home_name"] == "X FC"

    def test_groups_urls_by_domain_core(self, tmp_path):
        """One crawler instance per domain group; each receives its group's URLs."""
        crawler_a = StubCrawler([], matches=[])
        crawler_b = StubCrawler([], matches=[])
        factory = StubFactory(
            {},
            url_to_crawler={"a": crawler_a, "b": crawler_b},
        )
        seen = {}
        orig_a = crawler_a.get_matches

        def spy_a(urls):
            seen["a"] = list(urls)
            return orig_a(urls)

        crawler_a.get_matches = spy_a

        def spy_b(urls):
            seen["b"] = list(urls)

        crawler_b.get_matches = spy_b
        db = tmp_path / "chunk.db"
        scrape(str(db), "https://www.a.com/1,https://www.a.com/9,https://b.org/2", factory)
        assert seen["a"] == ["https://www.a.com/1", "https://www.a.com/9"]
        assert seen["b"] == ["https://b.org/2"]
        # create_for_url receives the FIRST url of each group
        assert set(factory.created) == {crawler_a, crawler_b}

    def test_exception_in_one_group_continues_others(self, tmp_path):
        bad = StubCrawler([], raise_on_get=True)
        good = StubCrawler([], matches=[make_match(home="Good FC", url="https://b.org/1")])
        factory = StubFactory(
            {},
            url_to_crawler={"a": bad, "b": good},
        )
        db = tmp_path / "chunk.db"
        scrape(str(db), "https://a.com/1,https://b.org/1", factory)  # must not raise
        df = _fetch(str(db))
        assert len(df) == 1
        assert df.iloc[0]["home_name"] == "Good FC"

    def test_factory_exception_continues_others(self, tmp_path):
        """Unknown URL for a domain → create_for_url raises → other groups proceed."""
        good = StubCrawler([], matches=[make_match(home="Good FC", url="https://b.org/1")])
        factory = StubFactory({}, url_to_crawler={"b": good})
        db = tmp_path / "chunk.db"
        scrape(str(db), "https://unknown.xyz/1,https://b.org/1", factory)
        df = _fetch(str(db))
        assert len(df) == 1


class TestScrapeP1:
    def test_empty_url_list_resets_db_and_writes_nothing(self, tmp_path):
        """Pre-existing db rows are wiped by reset_matches_db even with zero URLs."""

        db = tmp_path / "chunk.db"
        mm = MatchesManager(str(db), similarity_config=None)
        mm.add_match(make_match(home="Stale FC"))
        mm.flush()
        mm.close()
        factory = StubFactory({}, url_to_crawler={})
        scrape(str(db), "", factory)
        assert len(_fetch(str(db))) == 0

    def test_duplicate_matches_dedupe_into_single_row(self, tmp_path):
        """Same home/away/datetime twice from one group lands once; predictions merge."""
        from bet_framework.core.Match import Score

        m1 = make_match(home="Dedup FC", away="Rival", preds=None, url="https://a.com/1")
        m1.predictions = [Score(source="s1", home=2, away=0)]
        m2 = make_match(home="Dedup FC", away="Rival", preds=None, url="https://a.com/2")
        m2.predictions = [Score(source="s2", home=3, away=0)]
        crawler = StubCrawler([], matches=[m1, m2])
        factory = StubFactory({}, url_to_crawler={"a": crawler})
        db = tmp_path / "chunk.db"
        scrape(str(db), "https://a.com/1,https://a.com/2", factory)
        df = _fetch(str(db))
        assert len(df) == 1
        assert len(df.iloc[0]["scores"]) == 2


class TestScrapeP2:
    def test_no_dot_domain_keyed_by_full_host(self, tmp_path):
        """Domain without dots → core_name = whole domain; grouping still works."""
        crawler = StubCrawler([], matches=[])
        seen = []

        def spy(urls):
            seen.extend(urls)

        crawler.get_matches = spy
        factory = StubFactory({}, url_to_crawler={"localhost": crawler})
        db = tmp_path / "chunk.db"
        scrape(str(db), "http://localhost/1", factory)
        assert seen == ["http://localhost/1"]

    def test_subdomains_share_core_group(self, tmp_path):
        """www.a.com and a.com share core name 'a' → single group."""
        crawler = StubCrawler([], matches=[])
        seen = []

        def spy(urls):
            seen.extend(urls)

        crawler.get_matches = spy
        factory = StubFactory({}, url_to_crawler={"a": crawler})
        db = tmp_path / "chunk.db"
        scrape(str(db), "https://www.a.com/1,https://a.com/2", factory)
        assert seen == ["https://www.a.com/1", "https://a.com/2"]
        assert len(factory.created) == 1
