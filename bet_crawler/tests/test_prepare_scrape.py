"""Stage 1: prepare_scrape tests (issue #68).

Pins: chunk file creation, per-runner finder lists, chunk math,
retry semantics, stdout tasks JSON, runner-set isolation.
"""

import json

import pytest

from bet_crawler.crawl_core.prepare_scrape import prepare_scrape

from .conftest import StubCrawler, StubFactory


def _run(tmp_cwd, crawlers, runner="actions", max_chunk_size=None, capsys=None):
    factory = StubFactory({runner: crawlers})
    if max_chunk_size is None:
        max_chunk_size = {runner: 100}
    prepare_scrape(runner, factory, max_chunk_size)
    out = capsys.readouterr().out if capsys else None
    return out


def _read_urls(path):
    return open(path).read().split(",")


class TestPrepareScrapeP0:
    def test_creates_chunk_files_with_runner_prefix_and_content(self, tmp_cwd, capsys):
        crawlers = [StubCrawler([f"https://a.com/{i}" for i in range(5)])]
        out = _run(tmp_cwd, crawlers, capsys=capsys)
        assert (tmp_cwd / "actions-1-urls.txt").is_file()
        assert (tmp_cwd / "actions-1.db").exists() is False  # db created later by scrape
        # random.shuffle runs before chunking — order NOT guaranteed, multiset is
        assert sorted(_read_urls(tmp_cwd / "actions-1-urls.txt")) == sorted(f"https://a.com/{i}" for i in range(5))
        tasks = json.loads(out.strip())
        assert tasks == [{"db_path": "actions-1.db", "urls_file": "actions-1-urls.txt"}]

    def test_per_runner_crawler_list(self, tmp_cwd, capsys):
        """Only crawlers registered for the requested runner are used."""
        factory = StubFactory(
            {
                "actions": [StubCrawler(["https://a.com/1"])],
                "local": [StubCrawler(["https://b.com/1"]), StubCrawler(["https://c.com/1"])],
            }
        )
        prepare_scrape("local", factory, {"local": 100})
        used = list(factory.created)
        assert len(used) == 2
        assert used[0].get_matches_urls_calls == 1
        assert used[1].get_matches_urls_calls == 1

    def test_chunk_math_splits_by_max_runners(self, tmp_cwd, capsys):
        urls = [f"https://a.com/{i}" for i in range(50)]
        out = _run(tmp_cwd, [StubCrawler(urls)], max_chunk_size={"actions": 2}, capsys=capsys)
        tasks = json.loads(out.strip())
        assert len(tasks) == 2
        sizes = [len(_read_urls(tmp_cwd / t["urls_file"])) for t in tasks]
        assert sum(sizes) == 50
        assert all(s == 25 for s in sizes)

    def test_chunk_size_floor_is_20(self, tmp_cwd, capsys):
        """chunk_size = max(20, ceil(n/max_runners)) — small collections stay in one chunk."""
        out = _run(tmp_cwd, [StubCrawler(["https://a.com/1"] * 5)], max_chunk_size={"actions": 10}, capsys=capsys)
        tasks = json.loads(out.strip())
        assert len(tasks) == 1

    def test_no_crawlers_exits_1(self, tmp_cwd):
        with pytest.raises(SystemExit) as exc:
            prepare_scrape("actions", StubFactory({"actions": []}), {"actions": 100})
        assert exc.value.code == 1

    def test_stdout_tasks_json_matches_files(self, tmp_cwd, capsys):
        crawlers = [StubCrawler([f"https://a.com/{i}" for i in range(60)])]
        out = _run(tmp_cwd, crawlers, max_chunk_size={"actions": 10}, capsys=capsys)
        tasks = json.loads(out.strip())
        assert len(tasks) == 3
        for i, t in enumerate(tasks, start=1):
            assert t["db_path"] == f"actions-{i}.db"
            assert t["urls_file"] == f"actions-{i}-urls.txt"
            assert (tmp_cwd / t["urls_file"]).is_file()


class FlakyCrawler:
    """Fails N times on get_matches_urls then returns payload."""

    def __init__(self, fail_times, payload):
        self.fail_times = fail_times
        self.payload = payload
        self.calls = 0

    def get_matches_urls(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return list(self.payload)


class EmptyCrawler:
    calls = 0

    def get_matches_urls(self):
        self.calls += 1
        return []


class TestPrepareScrapeRetryP1:
    def test_retry_then_success_after_two_failures(self, tmp_cwd, capsys, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        flaky = FlakyCrawler(2, ["https://a.com/1"])
        _run(tmp_cwd, [flaky], capsys=capsys)
        assert flaky.calls == 3
        assert sleeps == [2, 2]
        assert _read_urls(tmp_cwd / "actions-1-urls.txt") == ["https://a.com/1"]

    def test_crawler_erroring_all_three_attempts_is_skipped(self, tmp_cwd, capsys, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        ok = StubCrawler(["https://b.com/1"])
        dead = FlakyCrawler(99, ["https://a.com/1"])
        _run(tmp_cwd, [dead, ok], capsys=capsys)
        assert dead.calls == 3
        assert _read_urls(tmp_cwd / "actions-1-urls.txt") == ["https://b.com/1"]

    def test_empty_url_list_retries_all_three_attempts(self, tmp_cwd, capsys, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        empty = EmptyCrawler()
        _run(tmp_cwd, [empty], capsys=capsys)
        assert empty.calls == 3
        assert sleeps == [2, 2]

    def test_shuffle_preserves_url_multiset(self, tmp_cwd, capsys):
        urls = [f"https://a.com/{i}" for i in range(40)]
        _run(tmp_cwd, [StubCrawler(urls)], max_chunk_size={"actions": 4}, capsys=capsys)
        got = []
        for f in sorted(tmp_cwd.glob("actions-*-urls.txt")):
            got.extend(_read_urls(f))
        assert sorted(got) == sorted(urls)

    def test_retry_loop_breaks_on_success_no_extra_sleep(self, tmp_cwd, capsys, monkeypatch):
        sleeps = []
        monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
        flaky = FlakyCrawler(1, ["https://a.com/1", "https://a.com/2"])
        _run(tmp_cwd, [flaky], capsys=capsys)
        assert flaky.calls == 2
        assert sleeps == [2]


class TestPrepareScrapeP2:
    def test_domain_logging_counts_unique_domains(self, tmp_cwd, capsys, caplog):
        crawlers = [StubCrawler(["https://a.com/1", "https://b.org/2", "https://a.com/3"])]
        with caplog.at_level("INFO", logger="bet_crawler.crawl_core.prepare_scrape"):
            _run(tmp_cwd, crawlers, capsys=capsys)
        msg = [r.getMessage() for r in caplog.records if "Collected" in r.getMessage()]
        assert msg, "expected domain summary log"
        assert "3 URLs across 2 domains" in msg[0]
        assert "a.com" in msg[0] and "b.org" in msg[0]

    def test_unknown_runner_defaults_chunk_size_1(self, tmp_cwd, capsys):
        """max_chunk_size.get(runner, 1) → chunk_size = max(20, n)."""
        urls = [f"https://a.com/{i}" for i in range(45)]
        out = _run(tmp_cwd, [StubCrawler(urls)], runner="ghost", max_chunk_size={}, capsys=capsys)
        tasks = json.loads(out.strip())
        # chunk_size = max(20, ceil(45/1)=45) → single chunk of 45
        assert len(tasks) == 1
        assert len(_read_urls(tmp_cwd / "ghost-1-urls.txt")) == 45
