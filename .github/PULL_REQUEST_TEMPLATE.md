## Description

<!-- What does this PR change and why? -->

## Testing checklist

<!-- All applicable boxes must be checked. CI enforces the required jobs. -->

- [ ] Python suites green locally: `cd bet_framework && python -m pytest` · `cd bet_dashboard/backend && python -m pytest tests/` · `cd bet_crawler && python -m pytest tests/`
- [ ] Frontend green locally: `cd bet_dashboard/frontend && npm run typecheck && npm run lint` (`npm test` if environment allows)
- [ ] New/changed code is covered by tests (or reason stated)
- [ ] `ruff check` clean on touched Python files
- [ ] No new `# type: ignore` without justification
- [ ] Secrets: none committed (`.env` only)

## Notes for reviewers

<!-- Anything special about this change? -->
