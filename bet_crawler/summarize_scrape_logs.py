"""Summarize structured crawler events and CI job logs from one scraping run."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_LEVEL_LINE = re.compile(
    r"^\S.*?\s-\s(?P<logger>[^\s].*?)\s-\s+(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+-\s(?P<message>.*)$",
    re.IGNORECASE,
)
_BARE_LEVEL_LINE = re.compile(
    r"^\s*(?:\[[^]]+\]\s*)?(?P<level>WARNING|ERROR|CRITICAL)\s*[:\-]\s*(?P<message>.*)$",
    re.IGNORECASE,
)
_ISSUE_LEVELS = {"WARNING", "ERROR", "CRITICAL"}
_OUTCOME_PRIORITY = {"success": 0, "skipped": 0, "partial": 1, "error": 2, "failure": 2}


def _read_events(logs_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Load valid JSONL events and collect malformed-line diagnostics."""
    events: list[dict[str, Any]] = []
    malformed: list[dict[str, str]] = []
    for path in sorted(logs_dir.rglob("*.jsonl")):
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    if not raw_line.strip():
                        continue
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        malformed.append(
                            {
                                "file": str(path.relative_to(logs_dir)),
                                "line": str(line_number),
                                "error": str(exc),
                            }
                        )
                        continue
                    if isinstance(record, dict):
                        record.setdefault("_artifact", str(path.relative_to(logs_dir)))
                        events.append(record)
                    else:
                        malformed.append(
                            {
                                "file": str(path.relative_to(logs_dir)),
                                "line": str(line_number),
                                "error": "JSON event is not an object",
                            }
                        )
        except OSError as exc:
            malformed.append({"file": str(path), "line": "0", "error": str(exc)})
    return events, malformed


def _is_near_miss_message(message: str) -> bool:
    """True when a log message belongs to the merge NEAR-MISS REPORT block (issue #113)."""
    return bool(_NEAR_MISS_START.match(message) or _NEAR_MISS_END.match(message) or _NEAR_MISS_LINE.match(message))


def _is_near_miss_issue(issue: dict[str, Any]) -> bool:
    """Near-miss lines from MatchesManager are reported separately, not as problems."""
    return str(issue.get("logger", "")) == "bet_framework.MatchesManager" and _is_near_miss_message(
        str(issue.get("message", ""))
    )


def _read_legacy_issues(
    logs_dir: Path,
    structured_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[tuple[int, str]]]]:
    """Read actionable text log records not already represented by JSONL.

    Returns a tuple of (issues, legacy_lines_by_artifact) where the second value maps
    artifact name -> list of (line_number, raw_line), used for near-miss extraction.
    """
    structured_messages = {
        (
            str(event.get("logger", "")),
            str(event.get("severity", "")).upper(),
            str(event.get("message", "")),
        )
        for event in structured_events
    }
    issues: list[dict[str, Any]] = []
    legacy_lines_by_artifact: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for path in sorted(logs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".log"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        artifact = str(path.relative_to(logs_dir))
        has_sidecar = any(path.parent.glob("*.jsonl"))
        for line_number, raw_line in enumerate(lines, start=1):
            legacy_lines_by_artifact[artifact].append((line_number, raw_line))
            issue = _parse_legacy_line(
                raw_line,
                artifact=artifact,
                line_number=line_number,
                structured_events=has_sidecar,
                structured_messages=structured_messages,
            )
            if issue:
                issues.append(issue)
    return issues, legacy_lines_by_artifact


_NEAR_MISS_START = re.compile(r"^\s*=== NEAR-MISS REPORT:\s*(\d+)\s+pairs \(score 40-65\) ===")
_NEAR_MISS_END = re.compile(r"^\s*=== END NEAR-MISS REPORT ===\s*$")
_NEAR_MISS_LINE = re.compile(r"^\s*\[(\d+)\]\s+(.+?)\s+vs\s+(.+?)\s+<->\s+(.+?)\s+vs\s+(.+?)\s*$")


def _extract_message_from_legacy_line(line: str) -> str | None:
    """Extract the log message part from a legacy log line.

    Expected format: TIMESTAMP - LOGGER - LEVEL - MESSAGE
    Returns the MESSAGE part, or None if format doesn't match.
    """
    # Match: YYYY-MM-DD HH:MM:SS - logger.name - LEVEL - message
    match = re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - .+? - (?:DEBUG|INFO|WARNING|ERROR|CRITICAL) - (.+)$", line)
    if match:
        return match.group(1)
    # Fallback: try the _LEVEL_LINE pattern
    match = _LEVEL_LINE.match(line)
    if match:
        return match.group("message")
    return None


def _extract_near_misses(
    events: list[dict[str, Any]],
    legacy_lines_by_artifact: dict[str, list[tuple[int, str]]],
) -> list[dict[str, Any]]:
    """Extract near-miss pairs from legacy log lines and JSONL events.

    Scans both:
    - Legacy text lines (primary source, since bet_framework logger lacks JSONL handler)
    - JSONL events (fallback if bet_framework.MatchesManager ever gets handler)
    """
    near_misses: list[dict[str, Any]] = []

    # 1. Legacy text lines: look for the NEAR-MISS REPORT block in each artifact
    for lines in legacy_lines_by_artifact.values():
        in_block = False
        for _line_number, raw_line in lines:
            line = _ANSI_ESCAPE.sub("", raw_line).strip()
            if not line:
                continue
            # Extract message part from log line
            message = _extract_message_from_legacy_line(line)
            if message is None:
                message = line

            start_match = _NEAR_MISS_START.match(message)
            if start_match:
                in_block = True
                continue
            if in_block and _NEAR_MISS_END.match(message):
                in_block = False
                continue
            if in_block:
                mm_match = _NEAR_MISS_LINE.match(message)
                if mm_match:
                    score = float(mm_match.group(1))
                    home_a = mm_match.group(2).strip()
                    away_a = mm_match.group(3).strip()
                    home_b = mm_match.group(4).strip()
                    away_b = mm_match.group(5).strip()
                    near_misses.append(
                        {
                            "score": score,
                            "home_a": home_a,
                            "away_a": away_a,
                            "home_b": home_b,
                            "away_b": away_b,
                        }
                    )

    # 2. JSONL events fallback: bet_framework.MatchesManager WARNING events with near-miss messages
    for event in events:
        if not (
            str(event.get("severity", "")).upper() == "WARNING"
            and str(event.get("logger", "")) == "bet_framework.MatchesManager"
        ):
            continue
        message = str(event.get("message", ""))
        # Check for header line
        if _NEAR_MISS_START.match(message):
            continue
        # Check for individual pair lines that might be logged separately
        mm_match = _NEAR_MISS_LINE.match(message)
        if mm_match:
            score = float(mm_match.group(1))
            home_a = mm_match.group(2).strip()
            away_a = mm_match.group(3).strip()
            home_b = mm_match.group(4).strip()
            away_b = mm_match.group(5).strip()
            # Deduplicate against legacy-extracted
            key = (score, home_a, away_a, home_b, away_b)
            if key not in {(nm["score"], nm["home_a"], nm["away_a"], nm["home_b"], nm["away_b"]) for nm in near_misses}:
                near_misses.append(
                    {
                        "score": score,
                        "home_a": home_a,
                        "away_a": away_a,
                        "home_b": home_b,
                        "away_b": away_b,
                    }
                )

    return near_misses


def _parse_legacy_line(
    raw_line: str,
    *,
    artifact: str,
    line_number: int,
    structured_events: bool,
    structured_messages: set[tuple[str, str, str]],
) -> dict[str, Any] | None:
    """Parse one legacy warning/error line, avoiding mirrored app logs."""
    line = _ANSI_ESCAPE.sub("", raw_line).strip()
    if not line:
        return None
    match = _LEVEL_LINE.match(line)
    if match:
        logger_name = match.group("logger").strip()
        level = match.group("level").upper()
        message = match.group("message").strip()
        if level not in _ISSUE_LEVELS:
            return None
        if logger_name.startswith("bet_crawler") and (
            structured_events or (logger_name, level, message) in structured_messages
        ):
            return None
    else:
        bare_match = _BARE_LEVEL_LINE.match(line)
        if not bare_match:
            return None
        logger_name = "unstructured"
        level = bare_match.group("level").upper()
        message = bare_match.group("message").strip()
    return {
        "severity": level,
        "event": "legacy.log_issue",
        "reason_code": "legacy_warning" if level == "WARNING" else "legacy_error",
        "logger": logger_name,
        "message": message,
        "_artifact": artifact,
        "_line": line_number,
    }


def summarize(logs_dir: Path, job_outcomes: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a deterministic summary from downloaded artifacts and job results."""
    logs_dir = logs_dir.resolve()
    events, malformed = _read_events(logs_dir) if logs_dir.exists() else ([], [])
    issues = [
        event
        for event in events
        if event.get("event") != "stage.completed"
        and (
            str(event.get("severity", "")).upper() in _ISSUE_LEVELS
            or str(event.get("outcome", "")).lower() in {"error", "partial"}
        )
    ]
    legacy_issues, legacy_lines_by_artifact = _read_legacy_issues(logs_dir, events)
    issues.extend(legacy_issues)
    issues.extend(
        {
            "severity": "WARNING",
            "event": "logging.jsonl_malformed",
            "reason_code": "malformed_jsonl_event",
            "logger": "summary-script",
            "message": f"{item['file']}:{item['line']}: {item['error']}",
            "_artifact": item["file"],
        }
        for item in malformed
    )

    # AC-4 (issue #113): near-miss reports are their own section and must not
    # inflate the problems table or the issue/severity counters.
    issues = [issue for issue in issues if not _is_near_miss_issue(issue)]
    near_misses = _extract_near_misses(events, legacy_lines_by_artifact)

    outcomes = {name: str(result).lower() for name, result in sorted((job_outcomes or {}).items())}
    failed_jobs = {name: result for name, result in outcomes.items() if result not in {"success", "skipped"}}
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        source = str(issue.get("source_key") or issue.get("finder") or issue.get("logger") or "unknown")
        event_name = str(issue.get("event") or "unspecified")
        reason = str(issue.get("reason_code") or "unspecified")
        groups[(source, event_name, reason)].append(issue)

    return {
        "schema_version": 2,
        "jobs": outcomes,
        "failed_jobs": failed_jobs,
        "event_files": len(list(logs_dir.rglob("*.jsonl"))) if logs_dir.exists() else 0,
        "structured_events": len(events),
        "malformed_event_lines": malformed,
        "issue_count": len(issues),
        "severity_counts": dict(Counter(str(issue.get("severity", "UNKNOWN")).upper() for issue in issues)),
        "groups": [
            {
                "source": source,
                "event": event_name,
                "reason_code": reason,
                "count": len(records),
                "severity_counts": dict(Counter(str(item.get("severity", "UNKNOWN")).upper() for item in records)),
                "samples": [
                    {
                        "severity": item.get("severity"),
                        "message": item.get("message"),
                        "url": item.get("url"),
                        "match_id": item.get("match_id"),
                        "error_type": item.get("error_type"),
                        "artifact": item.get("_artifact"),
                        "line": item.get("_line"),
                    }
                    for item in records[:3]
                ],
            }
            for (source, event_name, reason), records in sorted(groups.items())
        ],
        "stage_events": [event for event in events if str(event.get("event", "")) in {"stage.completed", "stage.failed"}],
        "near_misses": near_misses,
    }


def _stage_job(event: dict[str, Any]) -> str:
    """Return the CI job that produced a stage event when it can be identified."""
    stage = str(event.get("stage") or event.get("event") or "unknown")
    runner = event.get("runner")
    if runner:
        return f"{stage.removesuffix('-scrape')}-{runner}"

    artifact = str(event.get("_artifact") or "").replace("\\", "/")
    match = re.search(r"(?:^|/)logs-(prepare|scrape)-(actions|local)(?:-|/|$)", artifact)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return stage


def _pipeline_health(stage_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate real stage completions into the small, decision-oriented health view."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in stage_events:
        grouped[_stage_job(event)].append(event)

    health = []
    for job, events in sorted(grouped.items()):
        counts: Counter[str] = Counter()
        outcomes = []
        reasons: Counter[str] = Counter()
        for event in events:
            counts.update({key: value for key, value in (event.get("counts") or {}).items() if isinstance(value, int)})
            outcomes.append(str(event.get("outcome") or "unknown").lower())
            if event.get("outcome") in {"partial", "error", "failure"} and event.get("reason_code"):
                reasons[str(event["reason_code"])] += 1

        outcome = max(
            outcomes,
            key=lambda value: _OUTCOME_PRIORITY.get(value, 1),
            default="unknown",
        )
        health.append(
            {
                "job": job,
                "stage": str(events[0].get("stage") or events[0].get("event") or "unknown"),
                "outcome": outcome,
                "runs": len(events),
                "counts": dict(counts),
                "reasons": dict(reasons),
            }
        )
    return health


def _health_work_and_output(item: dict[str, Any]) -> tuple[str, str]:
    """Format stage-specific throughput without exposing every internal counter."""
    counts = item["counts"]
    stage = item["stage"]
    if stage == "prepare-scrape":
        return f"{counts.get('urls', 0)} URLs", "—"
    if stage == "scrape":
        return (
            f"{counts.get('groups_completed', 0)}/{counts.get('groups_total', 0)} groups",
            (f"{counts.get('matches_added', 0)} added, {counts.get('matches_skipped', 0)} skipped"),
        )
    if stage == "merge":
        return (
            f"{counts.get('chunks', 0)} chunks",
            f"{counts.get('matches', 0)} matches",
        )
    return "—", "—"


def _health_attention(item: dict[str, Any]) -> str:
    """Summarize only signals that warrant a reader's attention."""
    counts = item["counts"]
    signals = []
    if item["outcome"] != "success":
        signals.append(f"{item['runs']} {item['outcome']} run(s)")
    for key in (
        "errors",
        "warnings",
        "sources_failed",
        "sources_with_warnings",
        "crawlers_missing",
        "runner_sets_missing",
    ):
        if counts.get(key, 0):
            signals.append(f"{counts[key]} {key.replace('_', ' ')}")
    return ", ".join(signals) or "—"


def render_markdown(summary: dict[str, Any]) -> str:
    """Render an actionable GitHub Actions step summary."""
    lines = ["# Scrape run problem summary", ""]
    if summary["jobs"]:
        lines.extend(["## CI jobs", "", "| Job | Result |", "|---|---|"])
        lines.extend(f"| `{name}` | **{result}** |" for name, result in summary["jobs"].items())
        lines.append("")

    severity_counts = summary["severity_counts"]
    lines.append(
        f"**Issues:** {summary['issue_count']} total — "
        f"{severity_counts.get('ERROR', 0)} errors, "
        f"{severity_counts.get('CRITICAL', 0)} critical, "
        f"{severity_counts.get('WARNING', 0)} warnings."
    )
    lines.append(
        f"Parsed {summary['structured_events']} structured events from "
        f"{summary['event_files']} JSONL files; "
        f"{len(summary['malformed_event_lines'])} malformed event lines."
    )
    lines.append("")

    if summary["failed_jobs"]:
        lines.extend(["## Failed or incomplete CI jobs", ""])
        lines.extend(f"- **{name}:** `{result}`" for name, result in summary["failed_jobs"].items())
        lines.append("")

    if summary["groups"]:
        lines.extend(
            [
                "## Problems by source and reason",
                "",
                "| Severity | Source/logger | Event | Reason | Count | Example |",
                "|---|---|---|---|---:|---|",
            ]
        )
        for group in summary["groups"]:
            levels = ", ".join(f"{level}: {count}" for level, count in sorted(group["severity_counts"].items()))
            sample = group["samples"][0] if group["samples"] else {}
            message = str(sample.get("message") or "").replace("|", "\\|").replace("\n", " ")
            if len(message) > 220:
                message = message[:217] + "..."
            url = sample.get("url")
            if url:
                message = f"{message} ([URL]({url}))"
            source = str(group["source"]).replace("|", "\\|")
            lines.append(
                f"| {levels} | `{source}` | `{group['event']}` | "
                f"`{group['reason_code']}` | {group['count']} | {message or '—'} |"
            )
        lines.append("")
    else:
        lines.extend(["## Problems", "", "No warning/error log events were found.", ""])

    # AC-1/AC-5 (issue #113): dedicated near-miss section, omitted when empty.
    near_misses = summary.get("near_misses") or []
    if near_misses:
        lines.extend(
            [
                "## Near-miss reports",
                "",
                "Fuzzy-dedup pairs below the match threshold — synonym-discovery candidates.",
                "",
                "| Score | Match A | Match B |",
                "|------:|---|---|",
            ]
        )
        for nm in near_misses:
            match_a = f"{nm.get('home_a', '')} vs {nm.get('away_a', '')}".replace("|", r"\|")
            match_b = f"{nm.get('home_b', '')} vs {nm.get('away_b', '')}".replace("|", r"\|")
            lines.append(f"| {nm.get('score', 0):.0f} | {match_a} | {match_b} |")
        lines.append("")

    health = _pipeline_health(summary["stage_events"])
    if health:
        lines.extend(
            [
                "## Pipeline health",
                "",
                "| Job | Outcome | Work | Output | Attention |",
                "|---|---|---|---|---|",
            ]
        )
        for item in health:
            work, output = _health_work_and_output(item)
            lines.append(f"| `{item['job']}` | **{item['outcome']}** | {work} | {output} | {_health_attention(item)} |")
        lines.append("")

    degraded = [item for item in health if item["outcome"] not in {"success", "skipped"}]
    if degraded:
        lines.extend(["## Incomplete or degraded work", ""])
        for item in degraded:
            reasons = (
                ", ".join(f"`{reason}` ({count})" for reason, count in sorted(item["reasons"].items()))
                or "See problems by source and reason."
            )
            lines.append(f"- `{item['job']}`: {reasons}")
        lines.append("")

    lines.extend(
        [
            (
                "> This report is diagnostic and does not change the workflow conclusion. "
                "Raw logs and machine-readable details are retained in the `unified-logs` artifact."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _parse_job_outcomes(values: list[str]) -> dict[str, str]:
    outcomes = {}
    for value in values:
        name, separator, result = value.partition("=")
        if not separator or not name:
            raise ValueError(f"Invalid job outcome {value!r}; expected NAME=RESULT")
        outcomes[name] = result
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--step-summary", type=Path)
    parser.add_argument("--job-outcome", action="append", default=[])
    args = parser.parse_args()

    try:
        outcomes = _parse_job_outcomes(args.job_outcome)
    except ValueError as exc:
        parser.error(str(exc))
    summary = summarize(args.logs_dir, outcomes)
    markdown = render_markdown(summary)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_markdown.write_text(markdown, encoding="utf-8")
    if args.step_summary:
        args.step_summary.parent.mkdir(parents=True, exist_ok=True)
        with args.step_summary.open("a", encoding="utf-8") as stream:
            stream.write(markdown)
    print(f"Scrape summary: {summary['issue_count']} warning/error issue(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
