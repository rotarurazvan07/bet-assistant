#!/usr/bin/env bash
# scripts/select_changed_scopes.sh
#
# Change-based CI test selection: emit one KEY=true|false line per suite scope,
# derived from the PR (or push) diff, ready to append to $GITHUB_OUTPUT.
#
# This implementation directly encodes the 26-row trigger matrix from
# ci-test-trigger-matrix.md — each file maps to its row, scopes are OR-ed.
# Derived implications (never-narrow classes) are applied as additive rules.
#
# Design contract (see docs/development.md "Change-based test selection"):
#   * native git only — no third-party action runs in CI.
#   * FAIL-OPEN: an empty/unresolvable diff, an unknown path, or the
#     [force-all] marker sets EVERY suite scope to true (run everything).
#   * docs_only is the ONLY scope whose true value skips work — it stays
#     false on every fail-open path.
#
# Environment inputs (all optional, sensible defaults):
#   GITHUB_EVENT_NAME     pull_request | push | other (affects base choice)
#   GITHUB_BASE_REF       PR base branch name (pull_request only)
#   GITHUB_EVENT_BEFORE   previous head sha (push only)
#   FORCE_ALL=1           emergency bypass — emit all-true
#   PR_TITLE, PR_BODY     PR text; a [force-all] marker forces all-true
#
# Output: one line per scope on stdout, e.g. "framework=true".

set -euo pipefail

# ── scope registry ────────────────────────────────────────────────────────
SCOPES=(framework crawler backend frontend markets e2e docs_only github_infra setup_infra config gates npm_deps audit)

declare -A SCOPE
for s in "${SCOPES[@]}"; do SCOPE[$s]=false; done

# ── helpers ──────────────────────────────────────────────────────────────
emit_all_true() {
  local s
  for s in "${SCOPES[@]}"; do
    if [[ "$s" == "docs_only" ]]; then echo "docs_only=false"; else echo "${s}=true"; fi
  done
}

any_match() { grep -Eq -- "$1" <<< "$CHANGED_FILES"; }

note() { echo "::notice::$*" >&2; }

# ── fail-open gate ───────────────────────────────────────────────────────
if [[ "${FORCE_ALL:-}" == "1" ]] || grep -qi '\[force-all\]' <<< "${PR_TITLE:-}${PR_BODY:-}"; then
  note "force-all marker or FORCE_ALL=1 — emitting all scopes true"
  emit_all_true
  exit 0
fi

# CHANGED_FILES may be injected (dry-run/self-test) or resolved from git.
if [[ -n "${CHANGED_FILES:-}" ]]; then
  BASE="(injected)"
else
  if [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
    BASE_REF="${GITHUB_BASE_REF:-main}"
    BASE="origin/${BASE_REF}"
    git fetch --no-tags --depth=1 origin "refs/heads/${BASE_REF}:${BASE}" >/dev/null 2>&1 ||
      git fetch --no-tags origin "${BASE_REF}" >/dev/null 2>&1 || true
  else
    BASE="${GITHUB_EVENT_BEFORE:-HEAD~1}"
  fi
  CHANGED_FILES="$(git diff --name-only "${BASE}"...HEAD 2>/dev/null || true)"
fi

# ── fail-open: empty diff ────────────────────────────────────────────────
if [[ -z "${CHANGED_FILES//[[:space:]]/}" ]]; then
  note "empty or unresolvable diff (base=${BASE}) — emitting all scopes true"
  emit_all_true
  exit 0
fi

# ── per-file classification (matrix rows in priority order) ──────────────
# Each block sets SCOPE[...]=true for that row's scopes.
# Rows checked in priority order (most specific first).

# Row 2: bet_framework/markets/**
if any_match '^bet_framework/markets/'; then
  SCOPE[framework]=true; SCOPE[backend]=true; SCOPE[frontend]=true
  SCOPE[markets]=true; SCOPE[e2e]=true
fi

# Row 18: bet_dashboard/backend/openapi.generated.json
if any_match '^bet_dashboard/backend/openapi\.generated\.json$'; then
  SCOPE[backend]=true; SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# Row 25: bet_framework/core/Slip.py
if any_match '^bet_framework/core/Slip\.py$'; then
  SCOPE[framework]=true; SCOPE[crawler]=true; SCOPE[backend]=true; SCOPE[e2e]=true
fi

# Row 1: bet_framework/** (non-markets, non-tests)
if any_match '^bet_framework/' && ! any_match '^bet_framework/markets/|^bet_framework/tests/'; then
  SCOPE[framework]=true; SCOPE[backend]=true
fi

# Row 19: bet_framework/tests/**
if any_match '^bet_framework/tests/'; then
  SCOPE[framework]=true
fi

# Row 3: bet_crawler/** (non-finders-specific, non-tests)
if any_match '^bet_crawler/' && ! any_match '^bet_crawler/tests/|^bet_crawler/finders/[^/]+\.py$'; then
  SCOPE[crawler]=true
fi

# Row 20: bet_crawler/tests/**
if any_match '^bet_crawler/tests/'; then
  SCOPE[crawler]=true
fi

# Row 24: single finder file (bet_crawler/finders/XFinder.py)
if any_match '^bet_crawler/finders/[^/]+\.py$'; then
  SCOPE[crawler]=true
fi

# Row 4: bet_dashboard/backend/** (non-tests, non-openapi, non-requirements)
if any_match '^bet_dashboard/backend/' && ! any_match '^bet_dashboard/backend/(tests/|openapi\.generated\.json$|requirements\.txt$)'; then
  SCOPE[backend]=true; SCOPE[frontend]=true
fi

# Row 21: bet_dashboard/backend/tests/**
if any_match '^bet_dashboard/backend/tests/'; then
  SCOPE[backend]=true
fi

# Row 5: bet_dashboard/frontend/src/** (non-test, non-types)
if any_match '^bet_dashboard/frontend/src/' && ! any_match '^bet_dashboard/frontend/src/(test|types)/'; then
  SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# Row 22: bet_dashboard/frontend/src/test/**
if any_match '^bet_dashboard/frontend/src/test/'; then
  SCOPE[frontend]=true
fi

# Row 23: bet_dashboard/frontend/src/types/**
if any_match '^bet_dashboard/frontend/src/types/'; then
  SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# Row 6: bet_dashboard/frontend/e2e/**
if any_match '^bet_dashboard/frontend/e2e/'; then
  SCOPE[e2e]=true
fi

# Row 7: setup/seed_e2e.py
if any_match '^setup/seed_e2e\.py$'; then
  SCOPE[e2e]=true; SCOPE[setup_infra]=true
fi

# Row 9: setup/** (Dockerfile/compose/nginx/runner) - except seed_e2e.py handled above
if any_match '^setup/' && ! any_match '^setup/seed_e2e\.py$|^setup/compose\.e2e\.yaml$'; then
  SCOPE[setup_infra]=true; SCOPE[e2e]=true
fi

# Row 8: config/**
if any_match '^config/'; then
  SCOPE[config]=true; SCOPE[framework]=true; SCOPE[crawler]=true
  SCOPE[backend]=true; SCOPE[e2e]=true
fi

# Row 10: bet_dashboard/backend/requirements.txt
if any_match '^bet_dashboard/backend/requirements\.txt$'; then
  SCOPE[framework]=true; SCOPE[crawler]=true
  SCOPE[backend]=true; SCOPE[e2e]=true; SCOPE[gates]=true
fi

# Row 11: setup/requirements-scrape.txt
if any_match '^setup/requirements-scrape\.txt$'; then
  SCOPE[framework]=true; SCOPE[crawler]=true
  SCOPE[backend]=true; SCOPE[e2e]=true; SCOPE[gates]=true; SCOPE[setup_infra]=true
fi

# Row 12/13: bet_dashboard/frontend/package.json / package-lock.json
if any_match '^bet_dashboard/frontend/package(-lock)?\.json$'; then
  SCOPE[npm_deps]=true; SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# Row 14: .semgrep/**
if any_match '^\.semgrep/'; then
  SCOPE[gates]=true; SCOPE[framework]=true; SCOPE[crawler]=true
  SCOPE[backend]=true; SCOPE[frontend]=true
fi

# Row 15: AGENTS.md, README.md
if any_match '^AGENTS\.md$|^README\.md$'; then
  SCOPE[gates]=true
fi

# Row 17: .github/workflows/**
if any_match '^\.github/'; then
  SCOPE[github_infra]=true; SCOPE[config]=true; SCOPE[gates]=true
  SCOPE[framework]=true; SCOPE[crawler]=true; SCOPE[backend]=true
  SCOPE[frontend]=true; SCOPE[markets]=true; SCOPE[e2e]=true
fi

# ── docs_only detection (Row 16): only docs/ and root .md (except AGENTS.md/README.md) ────────────────
if ! grep -Ev '^docs/|^[^/]*\.md$' <<< "$CHANGED_FILES" | grep -q .; then
  # All files are docs/ or root .md — now check if any are the special gates files
  if ! any_match '^AGENTS\.md$|^README\.md$'; then
    SCOPE[docs_only]=true
  fi
fi

# ── derived implications (never-narrow classes) ──────────────────────────
# These ADD scopes on top of row classifications (OR semantics).

# markets scope → framework, backend, frontend, e2e
if [[ "${SCOPE[markets]}" == true ]]; then
  SCOPE[framework]=true; SCOPE[backend]=true; SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# config scope → crawler, framework, backend, e2e
if [[ "${SCOPE[config]}" == true ]]; then
  SCOPE[crawler]=true; SCOPE[framework]=true; SCOPE[backend]=true; SCOPE[e2e]=true
fi

# github_infra scope → everything (framework, crawler, backend, frontend, markets, e2e)
if [[ "${SCOPE[github_infra]}" == true ]]; then
  SCOPE[framework]=true; SCOPE[crawler]=true; SCOPE[backend]=true
  SCOPE[frontend]=true; SCOPE[markets]=true; SCOPE[e2e]=true
fi

# setup_infra scope → e2e only (plus audit which is always on)
# (setup_infra does NOT cascade to code suites - setup/ changes only need E2E)

# gates scope (.semgrep/) → framework, crawler, backend, frontend
if [[ "${SCOPE[gates]}" == true ]] && any_match '^\.semgrep/'; then
  SCOPE[framework]=true; SCOPE[crawler]=true; SCOPE[backend]=true; SCOPE[frontend]=true
fi

# npm_deps scope → frontend, e2e
if [[ "${SCOPE[npm_deps]}" == true ]]; then
  SCOPE[frontend]=true; SCOPE[e2e]=true
fi

# requirements scope → framework, crawler, backend, e2e, gates (already set by row 10/11)
if any_match '(^|/)requirements[^/]*\.txt$|^setup/requirements-scrape\.txt$|^bet_dashboard/backend/requirements\.txt$'; then
  SCOPE[framework]=true; SCOPE[crawler]=true; SCOPE[backend]=true; SCOPE[e2e]=true; SCOPE[gates]=true
fi

# Unknown/unclassified paths: if docs_only=false and no recognised scope matched,
# emit all true (fail-open).
if [[ "${SCOPE[docs_only]}" == false ]]; then
  if [[ "${SCOPE[framework]}" == false && "${SCOPE[crawler]}" == false && \
        "${SCOPE[backend]}"   == false && "${SCOPE[frontend]}" == false && \
        "${SCOPE[markets]}"   == false && "${SCOPE[e2e]}" == false && \
        "${SCOPE[github_infra]}"     == false && "${SCOPE[setup_infra]}" == false && \
        "${SCOPE[config]}"     == false && "${SCOPE[gates]}"     == false && \
        "${SCOPE[npm_deps]}" == false ]]; then
    note "no recognised scope matched — unclassified change, emitting all scopes true"
    emit_all_true
    exit 0
  fi
fi

# audit runs on every change class (docs_only included)
SCOPE[audit]=true

# ── observability ────────────────────────────────────────────────────────
{
  echo "### Change selection"
  echo
  echo "base: \`${BASE}\`"
  echo
  echo '```'
  echo "$CHANGED_FILES"
  echo '```'
  echo
  echo "| Scope | Value |"
  echo "|---|---|"
  for s in "${SCOPES[@]}"; do echo "| ${s} | ${SCOPE[$s]} |"; done
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}" || true

# ── emit ─────────────────────────────────────────────────────────────────
for s in "${SCOPES[@]}"; do echo "${s}=${SCOPE[$s]}"; done