"""Canonical market-key burn-down gate (AC-09).

Usage: python3 .semgrep/check_burn_down.py [report.json]

With no argument, runs semgrep with the repo rule against the source dirs and
evaluates the report; otherwise evaluates the given semgrep JSON report.

Rules:

- Findings beyond the committed ``.semgrep/baseline.json`` FAIL the gate (exit 1).
- The baseline is required to never GROW (ratchet): ``max_baseline_size`` is
  asserted against the committed finding count.
- Identity is stable across line shifts: rule id + path + stripped matched
  line content (line numbers are compared only within a file's content key).
- Any error (missing report, unparseable JSON, missing baseline) FAILS CLOSED.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".semgrep" / "baseline.json"
RULE = ROOT / ".semgrep" / "no-raw-market-literals.yml"
SCAN_DIRS = ["bet_framework", "bet_dashboard/backend", "bet_crawler", "tests"]


def _findings_identity(finding: dict) -> tuple[str, str, str]:
    """Stable identity: (check_id, path, stripped matched line content)."""
    extra = finding.get("extra", {}) or {}
    return (
        finding.get("check_id", ""),
        finding.get("path", ""),
        (extra.get("lines", "") or "").strip(),
    )


def _baseline_identity(entry: dict) -> tuple[str, str, str]:
    """Baseline entries store the same triple (match text kept as 'match')."""
    return (
        entry.get("rule_id", ""),
        entry.get("path", ""),
        (entry.get("match", "") or "").strip(),
    )


def main() -> int:
    if len(sys.argv) > 1:
        report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        completed = subprocess.run(
            [
                "semgrep",
                "--config",
                str(RULE),
                "--json",
                "--metrics=off",
                *SCAN_DIRS,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode not in (0, 1):
            sys.stderr.write(completed.stderr or "semgrep failed")
            return 1  # fail closed
        report = json.loads(completed.stdout)

    if not isinstance(report, dict):
        sys.stderr.write("unexpected semgrep report shape")
        return 1
    findings = report.get("results", [])

    if not BASELINE.exists():
        sys.stderr.write(f"missing baseline: {BASELINE}")
        return 1
    baseline_doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline = baseline_doc.get("findings", [])

    baselined = {_baseline_identity(f) for f in baseline}
    current = {_findings_identity(f) for f in findings}
    new = sorted(current - baselined)

    frozen_max = baseline_doc.get("max_baseline_size")
    if frozen_max is None:
        frozen_max = len(baseline)

    print(f"findings={len(findings)} baseline={len(baseline)} new={len(new)}")
    for check_id, path, snippet in new:
        print(f"NEW {check_id} {path}: {snippet[:100]}")

    if new:
        sys.stderr.write(
            "BLOCKING: new raw market-key literals beyond baseline - import from bet_framework/markets/ instead.\n"
        )
        return 1
    if len(baseline) > int(frozen_max):
        sys.stderr.write("BLOCKING: baseline grew - the ratchet may only shrink.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
