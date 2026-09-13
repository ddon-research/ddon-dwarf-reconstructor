# Lessons learned

This research record serves future maintainers. Refactoring lessons and performance conclusions
remain pending until corresponding tasks and acceptance evidence finish.

## Observed workflow lesson

Read-only lint probes must explicitly pass `--no-fix`: the current Ruff configuration enables
fixing by default. The planning probe's unintended test edits were restored to their original
index contents; this is a workflow observation, not a reason to broaden lint rules blindly.

## Pending acceptance-dependent lessons

Record each completed finding, useful abstraction, rejected extraction, measured performance
tradeoff, test that prevented recurrence, and resulting instruction change here. Do not present
the proposed architecture or higher memory tolerance as a proven improvement before measurement.
