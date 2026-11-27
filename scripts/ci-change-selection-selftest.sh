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
ALL_TRUE="audit=true backend=true config=true crawler=true docs_only=false e2e=true framework=true frontend=true gates=true github_infra=true markets=true npm_deps=true setup_infra=true"

assert_scopes() {
  local name="$1" files="$2" expected="$3"
  local got exp
  got=$(CHANGED_FILES="${files}" FORCE_ALL="" PR_TITLE="" PR_BODY="" GITHUB_EVENT_NAME="pull_request" GITHUB_BASE_REF="main" GITHUB_EVENT_BEFORE="HEAD~1" bash "${SELECTOR}" 2>/dev/null | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort | tr '\n' ' ' | sed 's/ $//')
  exp=$(echo "${expected}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort | tr '\n' ' ' | sed 's/ $//')
  if [[ "${got}" == "${exp}" ]]; then
    echo "  PASS  ${name}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  ${name}"
    echo "        files:    ${files}"
    echo "        expected: ${exp}"
    echo "        got:      ${got}"
    FAIL=$((FAIL + 1))
  fi
}

assert_raw() {
  local name="$1" expected="$2" output="$3"
  local got exp
  got=$(echo "${output}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort | tr '\n' ' ' | sed 's/ $//')
  exp=$(echo "${expected}" | tr ' ' '\n' | grep -E '^[a-z_]+=(true|false)$' | sort | tr '\n' ' ' | sed 's/ $//')
  if [[ "${got}" == "${exp}" ]]; then
    echo "  PASS  ${name}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  ${name}"
    echo "        expected: ${exp}"
    echo "        got:      ${got}"
    FAIL=$((FAIL + 1))
  fi
}

echo "Running selector self-test (trigger matrix rows)..."
echo

# row | change class | one representative path | expected scope string
run_case() {
  local row="$1" path="$2" expected="$3"
  assert_scopes "Row ${row}" "${path}" "${expected}"
}

run_case 1 "bet_framework/core/leagues.py" "framework=true backend=true audit=true markets=false crawler=false frontend=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 2 "bet_framework/markets/catalog.py" "framework=true backend=true markets=true frontend=true e2e=true audit=true crawler=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 3 "bet_crawler/finders/ForebetFinder.py" "crawler=true audit=true framework=false backend=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 4 "bet_dashboard/backend/routers/matches.py" "backend=true frontend=true audit=true framework=false crawler=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 5 "bet_dashboard/frontend/src/pages/BettingTips.tsx" "frontend=true e2e=true audit=true framework=false crawler=false backend=false markets=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 6 "bet_dashboard/frontend/e2e/slip-builder.spec.ts" "e2e=true audit=true framework=false crawler=false backend=false frontend=false markets=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 7 "setup/seed_e2e.py" "e2e=true setup_infra=true audit=true framework=false crawler=false backend=false frontend=false markets=false docs_only=false github_infra=false config=false gates=false npm_deps=false"
run_case 8 "config/scraper_config.yaml" "config=true framework=true crawler=true backend=true e2e=true audit=true markets=false frontend=false docs_only=false github_infra=false setup_infra=false gates=false npm_deps=false"
run_case 9 "setup/Dockerfile" "setup_infra=true e2e=true audit=true framework=false crawler=false backend=false frontend=false markets=false docs_only=false github_infra=false config=false gates=false npm_deps=false"
run_case 10 "bet_dashboard/backend/requirements.txt" "framework=true crawler=true backend=true e2e=true gates=true audit=true config=false markets=false frontend=false docs_only=false github_infra=false setup_infra=false npm_deps=false"
run_case 11 "setup/requirements-scrape.txt" "framework=true crawler=true backend=true e2e=true gates=true setup_infra=true audit=true config=false markets=false frontend=false docs_only=false github_infra=false npm_deps=false"
run_case 12 "bet_dashboard/frontend/package.json" "npm_deps=true frontend=true e2e=true audit=true config=false framework=false crawler=false backend=false markets=false docs_only=false github_infra=false setup_infra=false gates=false"
run_case 13 "bet_dashboard/frontend/package-lock.json" "npm_deps=true frontend=true e2e=true audit=true config=false framework=false crawler=false backend=false markets=false docs_only=false github_infra=false setup_infra=false gates=false"
run_case 14 ".semgrep/no-internal-references.yml" "gates=true framework=true crawler=true backend=true frontend=true audit=true markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false npm_deps=false"
run_case 15 "AGENTS.md" "gates=true audit=true framework=false crawler=false backend=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false npm_deps=false"
run_case 16 "docs/development.md" "docs_only=true audit=true framework=false crawler=false backend=false frontend=false markets=false e2e=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 17 ".github/workflows/cicd.yml" "github_infra=true framework=true crawler=true backend=true frontend=true markets=true e2e=true config=true gates=true audit=true docs_only=false setup_infra=false npm_deps=false"
run_case 18 "bet_dashboard/backend/openapi.generated.json" "backend=true frontend=true e2e=true audit=true framework=false crawler=false markets=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 19 "bet_framework/tests/test_slips.py" "framework=true audit=true backend=false crawler=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 20 "bet_crawler/tests/test_merge.py" "crawler=true audit=true framework=false backend=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 21 "bet_dashboard/backend/tests/test_analytics.py" "backend=true audit=true framework=false crawler=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 22 "bet_dashboard/frontend/src/test/marketsContract.test.ts" "frontend=true audit=true framework=false crawler=false backend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 23 "bet_dashboard/frontend/src/types/index.ts" "frontend=true e2e=true audit=true framework=false crawler=false backend=false markets=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 24 "bet_crawler/finders/BetExplorerFinder.py" "crawler=true audit=true framework=false backend=false frontend=false markets=false e2e=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 25 "bet_framework/core/Slip.py" "framework=true crawler=true backend=true e2e=true audit=true markets=false frontend=false docs_only=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"
run_case 26 "some/unknown/path.txt" "${ALL_TRUE}"

echo
echo "Failure modes (fail-open and bypass)..."
echo

# FORCE_ALL=1 env override — docs_only must be false or fail-open skips work.
assert_raw "FORCE_ALL=1 bypass" "${ALL_TRUE}" "$(FORCE_ALL=1 CHANGED_FILES="docs/x.md" PR_TITLE="" PR_BODY="" GITHUB_EVENT_NAME="pull_request" bash "${SELECTOR}" 2>/dev/null)"

# [force-all] marker in the PR title — emergency escape hatch.
assert_raw "[force-all] in PR title" "${ALL_TRUE}" "$(PR_TITLE='[force-all] rerun everything' FORCE_ALL="" CHANGED_FILES="docs/x.md" GITHUB_EVENT_NAME="pull_request" bash "${SELECTOR}" 2>/dev/null)"

# Empty diff must fail open (run everything), never narrow to nothing.
assert_raw "empty diff fails open" "${ALL_TRUE}" "$(CHANGED_FILES="" GITHUB_EVENT_NAME="pull_request" bash "${SELECTOR}" 2>/dev/null)"

# docs + markdown mixed is still docs-only.
assert_scopes "docs + root markdown" "docs/development.md" "docs_only=true audit=true framework=false crawler=false backend=false frontend=false markets=false e2e=false github_infra=false setup_infra=false config=false gates=false npm_deps=false"

echo
echo "=== Self-test summary ==="
echo "Passed: ${PASS}"
echo "Failed: ${FAIL}"
echo "Total:  $((PASS + FAIL))"

if [[ ${FAIL} -gt 0 ]]; then
  exit 1
fi
exit 0