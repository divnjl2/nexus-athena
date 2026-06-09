# Run Report — TEMPLATE (Phase 7)

> This is the TEMPLATE for the end-to-end dogfooding run (§9 Phase 7). It is NOT a real
> run — a real run requires `bd` installed, an executor (OpenHands V1 / Claurst), and
> `ralph/loop.sh` actually executing against a populated graph. Fill it from a real run.

- **Date:** <YYYY-MM-DD>
- **Feature:** <small real feature used for dogfooding>
- **Plan:** `thoughts/qrspi/<id>/plan.md`

## Metrics

| Metric | Value |
|---|---|
| Iterations (loop passes) | <n> |
| Issues closed | `bd stats --json \| jq '.closed'` |
| Gate failures | <n> |
| discovered-from issues created | <n> |
| Backtracks (replan) | <n> |
| OpenHands vs Claurst routing | <a> / <b> |
| Wall-clock | <hh:mm> |

## Acceptance (§10)

- [ ] `pytest tests/` green (golden + idempotency + bd-contract)
- [ ] Hermes one-prompt -> populated bd graph (epics/issues/deps, success_check on each)
- [ ] `loop.sh` closes the queue autonomously, routes by label, exits on empty `bd ready`
- [ ] Beads state synced to Dolt, survives session kills between iterations
- [ ] Executor swap touches only `ralph/`

## Notes

<diff review: quality, drift, correct replan on discovered-from>
