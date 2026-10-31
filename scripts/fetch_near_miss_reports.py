#!/usr/bin/env python3
"""
Fetch NEAR-MISS REPORT from GitHub Actions merge jobs for the current day.

This script:
1. Uses GITHUB_KEY from environment to authenticate with GitHub API
2. Fetches all workflow runs from today (based on system date)
3. For each run, finds the 'merge' job
4. Downloads the job logs and extracts the NEAR-MISS REPORT section
5. Outputs each run's report in full, exactly as it appears in the logs

Usage:
    export GITHUB_KEY=ghp_xxx
    python scripts/fetch_near_miss_reports.py

    # Or for a specific date:
    python scripts/fetch_near_miss_reports.py --date 2026-09-10

Requirements:
    - requests (pip install requests)
    - GITHUB_KEY environment variable with repo:read and actions:read scopes
"""

import argparse
import os
import re
import sys
from datetime import date, datetime, timezone

import requests

GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "rotarurazvan07"
REPO_NAME = "bet-assistant"
WORKFLOW_NAME = "Matches Scraper"


class GitHubActionsClient:
    """Client for GitHub Actions API."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_runs_for_date(self, target_date: date) -> list[dict]:
        """Fetch all workflow runs for a specific date."""
        runs = []
        page = 1
        per_page = 100

        while True:
            url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
            params = {
                "per_page": per_page,
                "page": page,
            }
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("workflow_runs"):
                break

            for run in data["workflow_runs"]:
                if run.get("name") != WORKFLOW_NAME:
                    continue
                created_at = datetime.fromisoformat(
                    run["created_at"].replace("Z", "+00:00")
                )
                if created_at.date() == target_date:
                    runs.append(run)

            # If we got fewer than per_page, we're done
            if len(data["workflow_runs"]) < per_page:
                break
            page += 1

        # Sort by created_at ascending (oldest first)
        runs.sort(key=lambda r: r["created_at"])
        return runs

    def get_jobs_for_run(self, run_id: int) -> list[dict]:
        """Fetch all jobs for a workflow run."""
        url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{run_id}/jobs"
        params = {"per_page": 100}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("jobs", [])

    def get_job_logs(self, job_id: int) -> str:
        """Download job logs as plain text."""
        url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/actions/jobs/{job_id}/logs"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text


def extract_near_miss_report(log_text: str) -> str | None:
    """
    Extract the NEAR-MISS REPORT section from log text.

    The report starts with "=== NEAR-MISS REPORT:" and ends with "=== END NEAR-MISS REPORT ===".
    Returns the full block including start/end markers, or None if not found.
    """
    # Pattern to match the NEAR-MISS REPORT block
    # The log lines have timestamps like: 2026-09-10T14:20:26.8319504Z 2026-09-10 14:20:26 - bet_framework.MatchesManager -  WARNING - === NEAR-MISS REPORT: 110 pairs (score 40-65) ===
    start_pattern = r"(.*? === NEAR-MISS REPORT:.*?===)"
    end_pattern = r"(.*? === END NEAR-MISS REPORT ===)"

    # Find start
    start_match = re.search(start_pattern, log_text)
    if not start_match:
        return None

    start_idx = start_match.start()

    # Find end
    end_match = re.search(end_pattern, log_text[start_idx:])
    if not end_match:
        return None

    end_idx = start_idx + end_match.end()

    # Extract the block
    report_block = log_text[start_idx:end_idx]

    # Clean up: each log line has a prefix like "2026-09-10T14:20:26.8319504Z 2026-09-10 14:20:26 - bet_framework.MatchesManager -  WARNING - "
    # We want to strip the GitHub Actions log prefix to get the actual log message
    lines = report_block.strip().split("\n")
    cleaned_lines = []
    for line in lines:
        # Match: timestampZ timestamp - logger - LEVEL - message
        # The actual message starts after " -  WARNING - " or " -  INFO - " etc.
        match = re.match(
            r"^.*?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - .*? - \s*\w+ - \s*(.*)$", line
        )
        if match:
            cleaned_lines.append(match.group(1))
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def find_merge_job(jobs: list[dict]) -> dict | None:
    """Find the merge job in a list of jobs."""
    for job in jobs:
        if job.get("name", "").lower() == "merge":
            return job
    return None


def format_run_header(run: dict, run_index: int, total_runs: int) -> str:
    """Format the run header."""
    created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    run_date = created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    conclusion = run.get("conclusion", "unknown")
    return f"=== RUN {run['id']} ({run_index}/{total_runs}) - {run_date} - {conclusion} ==="


def main():
    parser = argparse.ArgumentParser(
        description="Fetch NEAR-MISS REPORT from GitHub Actions merge jobs for a given date."
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date to fetch reports for (YYYY-MM-DD). Defaults to today (UTC).",
    )
    parser.add_argument(
        "--token",
        type=str,
        help="GitHub token (defaults to GITHUB_KEY environment variable).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output (job IDs, API calls).",
    )
    args = parser.parse_args()

    # Determine target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(
                f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        target_date = datetime.now(timezone.utc).date()

    # Get token
    token = args.token or os.environ.get("GITHUB_KEY")
    if not token:
        print(
            "Error: GitHub token required. Set GITHUB_KEY environment variable or use --token.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = GitHubActionsClient(token)

    if args.verbose:
        print(f"Fetching runs for {target_date}...", file=sys.stderr)

    # Fetch runs for the target date
    try:
        runs = client.get_runs_for_date(target_date)
    except requests.HTTPError as e:
        print(f"Error fetching runs: {e}", file=sys.stderr)
        sys.exit(1)

    if not runs:
        print(f"No '{WORKFLOW_NAME}' runs found for {target_date}.")
        return

    if args.verbose:
        print(f"Found {len(runs)} run(s).", file=sys.stderr)

    # Process each run
    for idx, run in enumerate(runs, 1):
        run_id = run["id"]
        if args.verbose:
            print(f"  Processing run {run_id} ({idx}/{len(runs)})...", file=sys.stderr)

        # Get jobs for this run
        try:
            jobs = client.get_jobs_for_run(run_id)
        except requests.HTTPError as e:
            print(f"  Error fetching jobs for run {run_id}: {e}", file=sys.stderr)
            continue

        # Find merge job
        merge_job = find_merge_job(jobs)
        if not merge_job:
            print(f"  No 'merge' job found for run {run_id}", file=sys.stderr)
            continue

        merge_job_id = merge_job["id"]
        if args.verbose:
            print(f"  Found merge job: {merge_job_id}", file=sys.stderr)

        # Download logs
        try:
            logs = client.get_job_logs(merge_job_id)
        except requests.HTTPError as e:
            print(f"  Error fetching logs for job {merge_job_id}: {e}", file=sys.stderr)
            continue

        # Extract NEAR-MISS REPORT
        report = extract_near_miss_report(logs)
        if not report:
            print(
                f"  No NEAR-MISS REPORT found in merge job {merge_job_id}",
                file=sys.stderr,
            )
            continue

        # Output
        print(format_run_header(run, idx, len(runs)))
        print(report)
        print()  # Blank line between runs


if __name__ == "__main__":
    main()
