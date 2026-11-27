# Story 3.3: CI Change-Based Test Selection

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **repository maintainer**,
I want **the CI pipeline to skip test suites and gates dynamically based on which files changed in the PR**,
so that **wall-clock time is reduced on focused changes without compromising enforcement coverage or deadlocking branch protection**.

## Acceptance Criteria

1. **AC-1** — A `changes` selector job exists in `.github/workflows/cicd.yml` that emits scope outputs derived from `git diff --name-only origin/${{ github.base_ref }}...HEAD` (native git, no untrusted third-party action) — on every PR event and on push-to-main.

2. **AC-2** — Selector failure mode is FAIL-OPEN: empty/error diff, unknown paths, fork PRs with unreachable base_ref → ALL scopes = true (run everything). Empty diff must NOT skip anything. Verified by a shell test / dry-run in the story's Dev Notes.

3. **AC-3** — Each previously-always-running suite job (`test`, `frontend-tests`, `audit`, `e2e-tests`) gains a job-level `if:` reading the selector output. NO workflow-level `on.*.paths:` or `paths-ignore:` filter is introduced anywhere — asserted by grep in verification.

4. **AC-4** — The never-narrow constraints from the TR `Riskiest skip decisions` section are enforced in the selector mapping and asserted by tests / a dry-run matrix check:
   - `bet_framework/markets/**` implies framework+backend+frontend(codegen/tsc/vitest/build)+E2E
   - `config/**` implies crawler+framework+backend+E2E
   - `setup/seed_e2e.py` and `bet_dashboard/frontend/e2e/**` imply E2E
   - any `requirements*.txt` or `package.json` / `package-lock.json` bump implies ALL suites on that runtime side
   - `docs/**`-only NEVER skips `audit` (the internal-reference hygiene gate scans `docs`)
   - `AGENTS.md` / `README.md` / `.github/**` / `setup/**` / `scripts/**` / `config/**` / `.semgrep/**` also imply `audit`

5. **AC-5** — `ci-gate` aggregator accepts `skipped` as a passing outcome ONLY for jobs the selector legitimately skipped in the SAME commit/workflow-run — in its Python `needs:` evaluation. Its current strictness (success-only) must be confirmed and the failure class (a job failing when it should have run) must still block the gate.

6. **AC-6** — A dry-run / self-test of the selector exists and is runnable without PR context: the story must include a table of the form `changed path → scopes emitted` covering EVERY row of `ci-test-trigger-matrix.md` (26 rows), and the repo must carry an executable check demonstrating those mappings — either bash assertions in a script under `scripts/` or Python tests. Whichever, it runs locally via `.venv/bin/python` (venv-rule) and is wired into an existing CI job (or a step inside the existing `audit` job — no new job, no new required status name).

7. **AC-7** — `docs/development.md` gains a short, published-standard-prose section that explains the change-detection mechanism, the never-narrow classes, and how to bypass it in an emergency (`[force-all]` marker in the PR title/body OR the escape routed through an existing selector scope — pick one and document it). Update `docs/frontend.md` ONLY if the E2E gating rules it documents change.

8. **AC-8** — lint/check gates green locally per the venv-rule: ruff check + ruff format on any changed Python; shellcheck on any new/changed `.sh` (if not installed in the container, state that explicitly); `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/cicd.yml'))"` (or equivalent) proves the edited workflow YAML still parses; `actionlint` if available (it is NOT installed in the container as of prior sessions — if so, state explicitly and treat as CI-verified class); and the repo's existing test suites that could touch selector code run green: framework `.venv/bin/python -m pytest tests/`, crawler `cd bet_crawler && ../.venv/bin/python -m pytest tests/`, backend `cd bet_dashboard/backend && ../../.venv/bin/python -m pytest tests/`.

9. **AC-9** — No internal-reference-hygiene violations introduced in any new/changed published file (no issue/PR/ticket numbers, no AC/AC-n/TC-2 labels, no cycle/wave/story/epic/sprint trackers, no review notes, no CI run identifiers or context-anchored commit hashes, no "M1/M编辑器" review labels). Run the `.semgrep/no-internal-references.yml` rule (or inspect manually) on every touched file. "Wave W0" wording in the story file is fine (planning artifact under .a0proj); the same wording in `cicd.yml` comments / `docs/development.md` / commit messages is NOT.

10. **AC-10** — The current CI is unchanged for non-PR/scheduled workflow triggers (`scrape.yml`, `update-runner.yml`, `security-watchdog.yml`) — verify by reading and confirming no edits, or by `git diff --stat`.

## Tasks / Subtasks

- [ ] Task 1: Create selector script `scripts/select_changed_scopes.sh` (AC: 1, 2, 4)
  - [ ] Subtask 1.1: Implement native `git diff` logic with fork-safe base resolution
  - [ ] Subtask 1.2: Emit all selector scopes as `KEY=true|false` to `$GITHUB_OUTPUT`
  - [ ] Subtask 1.3: Add step-summary printing of resolved base and changed-file list
  - [ ] Subtask 1.4: Implement FAIL-OPEN on empty/error diff (all scopes = true)
  - [ ] Subtask 1.5: Map all 26 change classes from trigger matrix to selector scopes

- [ ] Task 2: Add `changes` selector job to `.github/workflows/cicd.yml` (AC: 1, 3)
  - [ ] Subtask 2.1: Add job with `needs: []`, `runs-on: ubuntu-latest`, outputs for all scopes
  - [ ] Subtask 2.2: Use `actions/checkout@v7` with `fetch-depth: 0`
  - [ ] Subtask 2.3: Run selector script, capture outputs
  - [ ] Subtask 2.4: No `if:` on this job — it must always run

- [ ] Task 3: Wire job-level `if:` conditions on `test`, `frontend-tests`, `audit`, `e2e-tests` (AC: 3, 4)
  - [ ] Subtask 3.1: Add `needs: [changes]` to each gated job
  - [ ] Subtask 3.2: `test` job: `if: ${{ always() && needs.changes.outputs.docs_only != 'true' }}`
  - [ ] Subtask 3.3: `frontend-tests` job: `if: ${{ needs.changes.outputs.frontend == 'true' || needs.changes.outputs.markets == 'true' || needs.changes.outputs.backend == 'true' || needs.changes.outputs.npm_deps == 'true' }}`
  - [ ] Subtask 3.4: `e2e-tests` job: replace `needs.*.result` conditions with selector-driven `if:` using `e2e`, `frontend`, `setup` scopes
  - [ ] Subtask 3.5: `audit` job: `if: ${{ always() && needs.changes.outputs.docs_only != 'true' }}` (but keep blocking gates always-running — see Task 5)

- [ ] Task 4: Update `ci-gate` Python check to tolerate `skipped` for selector-gated jobs (AC: 5)
  - [ ] Subtask 4.1: Modify `required` dict to accept `('success', 'skipped')` for `test`, `frontend-tests`, `e2e-tests`
  - [ ] Subtask 4.2: Keep `audit` as `('success',)` only (blocking gates never skip)
  - [ ] Subtask 4.3: Add inline comment mapping each allowance to its selector output

- [ ] Task 5: Split `audit` job — fast published-files gates never skip (AC: 4, 5)
  - [ ] Subtask 5.1: Keep semgrep market-key burn-down, internal-refs, bandit, interrogate in `audit` (never skips)
  - [ ] Subtask 5.2: Allow mypy/radon/vulture/pip-audit to skip on `docs_only` via step-level `if:`
  - [ ] Subtask 5.3: Ensure `audit` job itself never reports `skipped`

- [ ] Task 6: Create dry-run self-test with 26-row assertion matrix (AC: 6)
  - [ ] Subtask 6.1: Create `scripts/ci-change-selection-selftest.sh` (bash) or Python test
  - [ ] Subtask 6.2: Encode all 26 rows from `ci-test-trigger-matrix.md` as assertions
  - [ ] Subtask 6.3: Wire into existing `audit` job as a step (no new required check)
  - [ ] Subtask 6.4: Runs locally via `.venv/bin/python` or `bash`

- [ ] Task 7: Update `docs/development.md` with change-detection documentation (AC: 7)
  - [ ] Subtask 7.1: Add section explaining selector mechanism, never-narrow classes, force-all escape
  - [ ] Subtask 7.2: Document `[force-all]` in PR title/body as escape hatch
  - [ ] Subtask 7.3: Check `docs/frontend.md` — update only if E2E gating rules change

- [ ] Task 8: Local verification gates (AC: 8, 9, 10)
  - [ ] Subtask 8.1: ruff check/format on any changed Python files
  - [ ] Subtask 8.2: shellcheck on selector script (or state missing)
  - [ ] Subtask 8.3: YAML validation of `cicd.yml`
  - [ ] Subtask 8.4: Run framework, crawler, backend pytest suites
  - [ ] Subtask 8.5: Run selector dry-run self-test (26/26 assertions pass)
  - [ ] Subtask 8.6: semgrep no-internal-references on all changed published files
  - [ ] Subtask 8.7: Verify `scrape.yml`, `update-runner.yml`, `security-watchdog.yml` unchanged

## Dev Notes

### Project Structure Notes

- **CI workflow**: `.github/workflows/cicd.yml` (1028 lines, 6 jobs: auto-fix, test, audit, frontend-tests, e2e-tests, ci-gate)
- **Selector script location**: `scripts/select_changed_scopes.sh` (new, tracked)
- **Self-test location**: `scripts/ci-change-selection-selftest.sh` (new, tracked)
- **Documentation**: `docs/development.md` (CI Pipeline section), `docs/frontend.md` (Testing section)
- **Trigger matrix reference**: `.a0proj/_bmad-output/planning-artifacts/research/ci-test-trigger-matrix.md` (26 rows)
- **Technical research**: `.a0proj/_bmad-output/planning-artifacts/research/technical-ci-change-based-test-selection-research-2026-11-27.md` (719 lines)

### Current CI Job Dependency Graph

```
auto-fix (PR-only, same-repo) → test → e2e-tests
                        → audit (parallel to test)
frontend-tests (no needs) → e2e-tests
ci-gate needs: [auto-fix, test, audit, frontend-tests, e2e-tests]
```

### Selector Scope Design (from TR Section 4.1)

**Coarse scopes emitted by selector:**
- `framework` — `bet_framework/**` changes
- `crawler` — `bet_crawler/**` changes
- `backend` — `bet_dashboard/backend/**` changes
- `frontend` — `bet_dashboard/frontend/src/**` changes
- `markets` — `bet_framework/markets/**` changes (cross-cutting)
- `e2e` — `bet_dashboard/frontend/e2e/**`, `setup/seed_e2e.py`, `setup/compose.e2e.yaml`
- `docs_only` — ONLY `docs/**` and `*.md` files changed (nothing else)
- `infra` — `.github/**`, `setup/**` (Dockerfile, compose, nginx, runner)
- `config` — `config/**`, `requirements*.txt`, `*.lock`, `Dockerfile`, `.env`
- `gates` — `.semgrep/**`, `AGENTS.md`, `README.md`
- `npm_deps` — `bet_dashboard/frontend/package.json`, `package-lock.json`

**Derived logic (critical for AC-4 never-narrow constraints):**
- `markets=true` → implies `framework=true`, `backend=true`, `frontend=true`, `e2e=true`
- `config=true` → implies `crawler=true`, `framework=true`, `backend=true`, `e2e=true`
- `e2e=true` → always runs E2E (two-track demo-data contract)
- `npm_deps=true` → implies all frontend gates
- `docs_only=true` → ONLY `test` and `frontend-tests` may skip; `audit` NEVER skips
- `gates=true` / `infra=true` → `audit` never skips
- Empty diff / selector failure → ALL scopes = true (FAIL-OPEN)

### `ci-gate` Current Python Logic (lines 1009-1027 of cicd.yml)

```python
required = {
    'auto-fix':       ('${{ needs.auto-fix.result }}', ('success', 'skipped')),
    'test':           ('${{ needs.test.result }}', ('success',)),
    'frontend-tests': ('${{ needs.frontend-tests.result }}', ('success',)),
    'e2e-tests':      ('${{ needs.e2e-tests.result }}', ('success',)),
    'audit':          ('${{ needs.audit.result }}', ('success',)),
}
```

**Required change:** Add `'skipped'` to `test`, `frontend-tests`, `e2e-tests` allowed outcomes. Keep `audit` strict.

### E2E Current Condition (lines 843-855)

```yaml
needs: [test, frontend-tests]
if: ${{ always() && needs.test.result == 'success' && needs.frontend-tests.result == 'success' }}
```

**Required change:** Replace with selector-driven condition:
```yaml
needs: [test, frontend-tests, changes]
if: ${{ always() && needs.changes.result == 'success' && (needs.changes.outputs.e2e == 'true' || needs.changes.outputs.frontend == 'true' || needs.changes.outputs.setup == 'true') }}
```

### Self-Test Matrix (26 rows from trigger matrix)

The self-test must assert each row's expected scope outputs. Example format:
```bash
# Row 1: bet_framework/** → framework=true, backend=true, markets=false, crawler=false, frontend=false, e2e=false, docs_only=false, infra=false, config=false, gates=false, npm_deps=false
# Row 2: bet_framework/markets/** → framework=true, backend=true, markets=true, frontend=true, e2e=true, ...
# ... all 26 rows
```

### References

- [Source: .github/workflows/cicd.yml] — full workflow, all 6 jobs, gate Python
- [Source: .a0proj/_bmad-output/planning-artifacts/research/ci-test-trigger-matrix.md] — 26-row trigger matrix with Why notes
- [Source: .a0proj/_bmad-output/planning-artifacts/research/technical-ci-change-based-test-selection-research-2026-11-27.md] — full TR, sections 1-10
- [Source: docs/development.md#CI Pipeline] — current CI documentation
- [Source: .github/PULL_REQUEST_TEMPLATE.md] — PR template
- [Source: .semgrep/no-internal-references.yml] — internal reference hygiene rule
- [Source: .github/workflows/scrape.yml] — must remain unchanged (AC-10)
- [Source: .github/workflows/update-runner.yml] — must remain unchanged (AC-10)
- [Source: .github/workflows/security-watchdog.yml] — must remain unchanged (AC-10)
- [Source: .a0proj/_bmad-output/implementation-artifacts/sprint-status.yaml] — epic-ci-maintenance tracking

## Dev Agent Record

### Agent Model Used

Litellm/frontier (Amelia, bmad-dev)

### Debug Log References

- TR artifacts read in full (2026-11-27)
- cicd.yml read in full (1028 lines)
- sprint-status.yaml confirms epic-ci-maintenance backlog, next story 003

### Completion Notes List

- Story created from Phase 1 Technical Research deliverables
- All 10 ACs derived from TR Riskiest skip decisions and implementation sketch
- Selector design: native git diff (Option C), dorny/paths-filter as documented fallback
- tj-actions/changed-files rejected (supply-chain history)
- Workflow-level paths filters rejected (deadlock)
- FAIL-OPEN on selector failure is mandatory
- ci-gate must be updated in same commit as any new skippable job
- Wave 0 (selector only, no skipping) → Wave 1 (docs_only) → Wave 2 (E2E) → Wave 3 (audit split) → Wave 4 (per-package) → Wave 5 (hardening/docs)

### File List

- `.github/workflows/cicd.yml` (modified)
- `scripts/select_changed_scopes.sh` (new)
- `scripts/ci-change-selection-selftest.sh` (new)
- `docs/development.md` (modified)
- `docs/frontend.md` (potentially modified)
- `.a0proj/_bmad-output/implementation-artifacts/stories/ci-maintenance-003-change-based-test-selection.md` (this file)
- `.a0proj/_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — status to ready-for-dev)

---

## Story Completion Status

- Story file created: yes
- Sprint status updated: pending (step 6 of create-story workflow)
- Ready for dev-story: yes