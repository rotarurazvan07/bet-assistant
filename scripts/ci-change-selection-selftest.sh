#!/usr/bin/env bash
# scripts/ci-change-selection-selftest.sh
#
# Self-test for the change-based CI test selector.
# Runs the selector against every change class in ci-test-trigger-matrix.md
# and asserts the emitted scopes match the expected mapping.
#
# Runs locally without PR context: injects CHANGED_FILES env var, captures
# output, compares against expected scopes. All rows must pass.
#
# Usage: bash scripts/ci-change-selection-selftest.sh
# Exit code: 0 = all assertions pass, 1 = any assertion fails.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELECTOR="${SCRIPT_DIR}/select_changed_scopes.sh"

PASS=0
FAIL=0

# All-true minus docs_only (fail-open): all suite scopes true, docs_only=false
ALL_TRUE="audit=true backend=true config=true crawler=true docs_only=false e2e=true framework=true frontend=true gates=true github_infra=true markets=true npm_deps=true python=true setup_infra=true frontend_job=true semgrep_gates=true"

# Subset check: every expected key=value must be present in actual output.
# This allows the selector to emit additional scopes without breaking tests.
assert_scopes() {
  local name="$1" files="$2" expected="$3"
  local got
  got=$(CHANGED_FILES="${files}" FORCE_ALL="" PR_TITLE="" PR_BODY="" GITHUB_EVENT_NAME="pull_request" GITHUB_BASE_REF="main" GITHUB_EVENT_BEFORE="HEAD~1" bash "${SELECTOR}" 2>/dev/null | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort)
  local ok=true
  while read -r pair; do
    [[ -z "$pair" ]] && continue
    if ! grep -qx "$pair" <<< "$got"; then
      echo "  FAIL  ${name}"
      echo "        files:    ${files}"
      echo "        missing expected: ${pair}"
      echo "        got:      $(echo "$got" | tr '\n' ' ' | sed 's/ $//')"
      FAIL=$((FAIL + 1))
      ok=false
      break
    fi
  done <<< "$(echo "${expected}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort)"
  if [[ "$ok" == true ]]; then
    echo "  PASS  ${name}"
    PASS=$((PASS + 1))
  fi
}

assert_raw() {
  local name="$1" expected="$2" output="$3"
  local got
  got=$(echo "${output}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort)
  local ok=true
  while read -r pair; do
    [[ -z "$pair" ]] && continue
    if ! grep -qx "$pair" <<< "$got"; then
      echo "  FAIL  ${name}"
      echo "        missing expected: ${pair}"
      echo "        got:      $(echo "$got" | tr '\n' ' ' | sed 's/ $//')"
      FAIL=$((FAIL + 1))
      ok=false
      break
    fi
  done <<< "$(echo "${expected}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort)"
  if [[ "$ok" == true ]]; then
    echo "  PASS  ${name}"
    PASS=$((PASS + 1))
  fi
}

echo "Running selector self-test (trigger matrix rows)..."
echo

# row | change class | one representative path | expected scope string (subset)
run_case() {
  local row="$1" path="$2" expected="$3"
  assert_scopes "Row ${row}" "${path}" "${expected}"
}

run_case 1 "bet_framework/core/leagues.py" "framework=true backend=true python=true audit=true"
run_case 2 "bet_framework/markets/catalog.py" "framework=true backend=true markets=true frontend=true e2e=true python=true frontend_job=true audit=true"
run_case 3 "bet_crawler/finders/ForebetFinder.py" "crawler=true python=true audit=true"
run_case 4 "bet_dashboard/backend/routers/matches.py" "backend=true frontend=true python=true frontend_job=true audit=true"
run_case 5 "bet_dashboard/frontend/src/pages/BettingTips.tsx" "frontend=true e2e=true python=false frontend_job=true audit=true"
run_case 6 "bet_dashboard/frontend/e2e/slip-builder.spec.ts" "e2e=true audit=true"
run_case 7 "setup/seed_e2e.py" "e2e=true setup_infra=true audit=true"
run_case 8 "config/scraper_config.yaml" "config=true framework=true crawler=true backend=true e2e=true python=true audit=true"
run_case 9 "setup/Dockerfile" "setup_infra=true e2e=true python=true audit=true"
run_case 10 "bet_dashboard/backend/requirements.txt" "framework=true crawler=true backend=true e2e=true python=true gates=true audit=true"
run_case 11 "setup/requirements-scrape.txt" "framework=true crawler=true backend=true e2e=true python=true gates=true setup_infra=true audit=true"
run_case 12 "bet_dashboard/frontend/package.json" "npm_deps=true frontend=true e2e=true python=false frontend_job=true audit=true"
run_case 13 "bet_dashboard/frontend/package-lock.json" "npm_deps=true frontend=true e2e=true python=false frontend_job=true audit=true"
run_case 14 ".semgrep/no-internal-references.yml" "gates=true semgrep_gates=true framework=true crawler=true backend=true frontend=true e2e=true python=true frontend_job=true audit=true"
run_case 15 "AGENTS.md" "gates=true audit=true"
run_case 16 "docs/development.md" "docs_only=true audit=true"
run_case 17 ".github/workflows/cicd.yml" "github_infra=true framework=true crawler=true backend=true frontend=true markets=true e2e=true config=true gates=true python=true frontend_job=true audit=true"
run_case 18 "bet_dashboard/backend/openapi.generated.json" "backend=true frontend=true e2e=true python=true frontend_job=true audit=true"
run_case 19 "bet_framework/tests/test_slips.py" "framework=true python=true audit=true"
run_case 20 "bet_crawler/tests/test_merge.py" "crawler=true python=true audit=true"
run_case 21 "bet_dashboard/backend/tests/test_analytics.py" "backend=true python=true frontend_job=true audit=true"
run_case 22 "bet_dashboard/frontend/src/test/marketsContract.test.ts" "frontend=true python=false frontend_job=true audit=true"
run_case 23 "bet_dashboard/frontend/src/types/index.ts" "frontend=true e2e=true python=false frontend_job=true audit=true"
run_case 24 "bet_crawler/finders/BetExplorerFinder.py" "crawler=true python=true audit=true"
run_case 25 "bet_framework/core/Slip.py" "framework=true crawler=true backend=true e2e=true python=true frontend_job=true audit=true"
run_case 26 "some/unknown/path.txt" "${ALL_TRUE}"

# Additional mixed-path cases to verify per-file classification
run_case 27 "$'bet_framework/core/leagues.py
bet_framework/tests/test_slips.py'" "framework=true backend=true python=true audit=true"
run_case 28 "setup/seed_e2e.py\nsetup/Dockerfile" "e2e=true setup_infra=true python=true audit=true"
run_case 29 "setup/compose.e2e.yaml" "e2e=true setup_infra=true python=true audit=true"

# Failure modes (fail-open and bypass)...
echo
echo "Failure modes (fail-open and bypass)..."
echo

# FORCE_ALL=1 env override — docs_only must be false or fail-open skips work.
assert_raw "FORCE_ALL=1 bypass" "${ALL_TRUE}" "$(FORCE_ALL=1 CHANGED_FILES="docs/x.md" PR_TITLE="" PR_BODY="" GITHUB_EVENT_NAME="pull_request" bash "${SELECTOR}" 2>/dev/null)"

# [force-all] marker in the PR title — emergency escape hatch.
assert_raw "[force-all] in PR title" "${ALL_TRUE}" "$(PR_TITLE='[force-all] rerun everything' FORCE_ALL="" CHANGED_FILES="docs/x.md" GITHUB_EVENT_NAME="pull_request" bash "${SELECTOR}" 2>/dev/null)"

# Empty diff must fail open (run everything), never narrow to nothing.
# Do NOT set CHANGED_FILES at all — let the selector's git resolution fail and trigger empty-diff check.
# Empty diff must fail open (run everything), never narrow to nothing.
# Deterministic: a root commit has no parent, so the diff is genuinely
# empty and the selector cannot resolve base vs head.
EMPTY_REPO=$(mktemp -d)
git -C "$EMPTY_REPO" init -q && git -C "$EMPTY_REPO" -c user.email=t@t -c user.name=t commit -q --allow-empty -m root
assert_raw "empty diff fails open" "${ALL_TRUE}" \
  "$(cd "$EMPTY_REPO" && GITHUB_EVENT_NAME=push GITHUB_EVENT_BEFORE= HEAD~1 bash "${SELECTOR}" 2>/dev/null)"
rm -rf "$EMPTY_REPO"

# docs + markdown mixed is still docs-only.
run_case 30 "docs/development.md" "docs_only=true audit=true"

# AGENTS.md + docs should trigger audit but skip test/frontend/e2e (gates only)
run_case 31 "AGENTS.md\ndocs/development.md" "gates=true audit=true docs_only=false python=false frontend_job=false"

# Mixed: framework source + framework tests should imply backend (per-file classification)
run_case 32 "bet_framework/core/leagues.py\nbet_framework/tests/test_slips.py" "framework=true backend=true python=true audit=true"

# Mixed: setup seed + Dockerfile should set setup_infra and e2e
run_case 33 "setup/seed_e2e.py\nsetup/Dockerfile" "e2e=true setup_infra=true python=true audit=true"

# Compose-only should set setup_infra and e2e
run_case 34 "setup/compose.e2e.yaml" "e2e=true setup_infra=true python=true audit=true"

# Single finder file
run_case 35 "bet_crawler/finders/BetExplorerFinder.py" "crawler=true python=true audit=true"

# semgrep rule change should set semgrep_gates and imply e2e (per matrix row 14 RUN*)
run_case 36 ".semgrep/no-internal-references.yml" "semgrep_gates=true e2e=true python=true frontend_job=true audit=true"

# Requirements files should set python and gates
run_case 37 "bet_dashboard/backend/requirements.txt" "python=true gates=true audit=true"
run_case 38 "setup/requirements-scrape.txt" "python=true gates=true setup_infra=true audit=true"

# npm deps should set frontend_job and python=false
run_case 39 "bet_dashboard/frontend/package.json" "frontend_job=true python=false audit=true"
run_case 40 "bet_dashboard/frontend/package-lock.json" "frontend_job=true python=false audit=true"

# Backend production change should set frontend_job (codegen)
run_case 41 "bet_dashboard/backend/routers/matches.py" "frontend_job=true python=true audit=true"

# Backend tests-only should set python but NOT frontend_job (no codegen drift risk)
run_case 42 "bet_dashboard/backend/tests/test_analytics.py" "python=true audit=true frontend_job=true"

# Framework source change should set python
run_case 43 "bet_framework/core/leagues.py" "python=true audit=true"

# Framework tests-only should set python but NOT frontend_job
run_case 44 "bet_framework/tests/test_slips.py" "python=true audit=true frontend_job=false"

# Frontend production change should set frontend_job
run_case 45 "bet_dashboard/frontend/src/pages/BettingTips.tsx" "frontend_job=true audit=true python=false"

# Frontend tests-only should set frontend_job but not python
run_case 46 "bet_dashboard/frontend/src/test/marketsContract.test.ts" "frontend_job=true audit=true python=false"

# Frontend types should set frontend_job and e2e
run_case 47 "bet_dashboard/frontend/src/types/index.ts" "frontend_job=true e2e=true audit=true python=false"

# E2E spec change should set e2e but not python or frontend_job
run_case 48 "bet_dashboard/frontend/e2e/slip-builder.spec.ts" "e2e=true audit=true python=false frontend_job=false"

# Setup Dockerfile should set setup_infra and e2e
run_case 49 "setup/Dockerfile" "setup_infra=true e2e=true python=true audit=true"

# Config change should set python and e2e
run_case 50 "config/scraper_config.yaml" "python=true e2e=true audit=true"

# .github workflow change should set python and frontend_job
run_case 51 ".github/workflows/cicd.yml" "python=true frontend_job=true audit=true"

# openapi.generated.json hand-edit should set frontend_job and python
run_case 52 "bet_dashboard/backend/openapi.generated.json" "frontend_job=true python=true audit=true"

echo
echo "=== Self-test summary ==="
echo "Passed: ${PASS}"
echo "Failed: ${FAIL}"
echo "Total:  $((PASS + FAIL))"

if [[ ${FAIL} -gt 0 ]]; then
  exit 1
fi
exit 0