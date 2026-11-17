# Phase 1 risk analysis

Ranked by impact times likelihood.

| # | Risk | Impact | Likelihood | Detection |
|---|---|---|---|---|
| 1 | Job state changes under concurrency: cancel, timeout, or completion collide, or a job runs twice | High | High | Component tests with a controllable fake adapter; assert final state and adapter call count |
| 2 | Wrong but plausible measurement results (gate maths, bit order, aggregation) | Critical, silent | Medium | Circuits with known outcomes, fixed-seed assertions, statistical tolerances, counts sum to shots |
| 3 | SDK retry policy and error mapping: wrong retries, wrong backoff, wrong exception | Medium to high | High | Unit tests with mocked transport and injected sleep; assert outcome and attempts |
| 4 | SDK and API contract drift; validation limits are duplicated in both packages | Medium to high | High over time | Contract tests against the real API, same boundaries on both sides, OpenAPI diff in CI |
| 5 | Authorization: a valid key reaches another owner's experiment | High | Medium | Schema-driven test calling every ID endpoint with a second owner's key |

## Left out: load

Slowness is visible and recoverable; risks 1 and 2 are silent. The baseline is one process with an in-memory queue, so load results would not predict the Phase 5 system. Revisit in Phase 7.

## Test level for risk 1: component

- Real: execution service, state machine, queue, SQLite repository (in memory).
- Faked: hardware adapter (test-controlled) and clock.
- Why: the race protection is the repository's atomic "change state only if still X" update, so mocking the repository removes what is under test; going through HTTP removes control over timing.
- Remaining: multiple worker processes and a real queue (Phase 5).
