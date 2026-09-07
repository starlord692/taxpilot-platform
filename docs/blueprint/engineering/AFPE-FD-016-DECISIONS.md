# AFPE-FD-016 — Financial Performance Near-Zero Baseline Policy

**Status:** Founder Approved
**Authority:** AFPE-FD-001 through AFPE-FD-015
**Scope:** Accounting Financial Performance evidence baseline eligibility for relative-rate determination
**Implementation authorization:** None

## Purpose

Define the structural Accounting-owned policy for determining whether a Financial Performance comparison baseline is zero, near-zero, eligible, or undeterminable for percentage-based relative movement.

## Decisions

### AFPE-FD-016A — Exact zero

A baseline is `ZERO` when its governed monetary amount is exactly zero after Accounting's applicable monetary normalization. `ZERO` makes Financial Performance relative rate `NOT_DETERMINABLE`.

### AFPE-FD-016B — Near-zero basis

Near-zero is determined by an Accounting-owned absolute monetary threshold `N` applied to the absolute baseline magnitude. The threshold is not a percentage, score, ranking, prediction, or Momentum policy.

### AFPE-FD-016C — Currency scope

The threshold is interpreted in the baseline's own currency. Threshold configuration is currency-specific. Momentum performs no currency conversion and may not infer an unsupported currency or substitute a threshold.

### AFPE-FD-016D — Precision and rounding

Accounting applies its governed monetary precision, scale, and rounding mode before making the baseline determination. Momentum does not independently round or normalize the monetary value.

### AFPE-FD-016E — Boundary semantics

For a supported currency with configured threshold `N`:

- `baseline = 0` → `ZERO`
- `0 < abs(baseline) < N` → `NEAR_ZERO`
- `abs(baseline) >= N` → `ELIGIBLE`

`ZERO` and `NEAR_ZERO` make relative rate `NOT_DETERMINABLE`. `ELIGIBLE` permits the approved Financial Performance rate formula only when all other approved requirements are satisfied.

### AFPE-FD-016F — Undeterminable baseline

If Accounting cannot determine the baseline category because required currency, threshold configuration, precision/rounding context, or other governed context is unavailable or contradictory, the result is `UNDETERMINABLE`. Momentum must fail closed and produce `NOT_DETERMINABLE` for rate.

### AFPE-FD-016G — Versioned policy context

The baseline determination preserves threshold-policy identity/version, currency, threshold, scale, rounding mode, effective policy context, evidence/result identity, and limitations. Later policy changes create later governed results or reconstructions and do not rewrite immutable historical reported evidence.

## Concrete threshold configuration

No Accounting-owned numeric threshold or supported-currency configuration is currently established. Therefore no currency is currently supported for threshold-based Financial Performance relative-rate determination.

A future configuration must contain, for every supported currency:

- currency code;
- exact decimal threshold `N`;
- monetary scale;
- rounding mode;
- effective date/time;
- policy version.

No default value may be inferred.

## Non-authorization

These decisions do not authorize Momentum implementation, currency conversion, new Accounting policy beyond the stated boundary, or changes to application code. They authorize only the governed contract semantics necessary for later contract publication.