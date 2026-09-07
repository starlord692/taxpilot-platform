# AFPE-FD-017 — No Configured Near-Zero Policy

**Status:** Founder Approved
**Authority:** AFPE-FD-016A–016G
**Scope:** v1.0 behavior when Accounting has no configured near-zero threshold for a currency
**Implementation authorization:** None

## Decisions

### AFPE-FD-017A — No configured currencies

Until Accounting publishes a complete threshold configuration and it receives Founder approval, no currency is supported for threshold-based Financial Performance relative-rate determination.

### AFPE-FD-017B — Deterministic fail-closed behavior

For an unsupported or unconfigured currency, Accounting publishes baseline eligibility as `UNDETERMINABLE` with an applicable limitation/reason. Momentum produces `NOT_DETERMINABLE` for rate and does not infer a threshold.

### AFPE-FD-017C — Direction remains independent

The absence of a configured near-zero threshold applies only to relative-rate determination. It does not by itself prevent valid Financial Performance movement/direction from being determined when the separately approved evidence, comparison, and Accounting materiality requirements are satisfied.

### AFPE-FD-017D — No consumer inference

Momentum and other consumers may not choose a threshold, assume a default currency, infer supported currencies, perform currency conversion, or infer a near-zero boundary.

### AFPE-FD-017E — Historical policy preservation

A historical result may contain a threshold-based baseline determination only when a valid Accounting threshold policy existed for its declared context. Later policy availability does not retroactively rewrite immutable historical reported evidence.

### AFPE-FD-017F — Future activation

A future Accounting configuration becomes authoritative only after it contains currency, exact decimal `N`, scale, rounding mode, effective date/time, and policy version and receives explicit Founder approval. The configuration then applies only within its declared effective context.

## Current v1.0 configuration

No supported currencies and no numeric threshold `N` are currently established. Consequently, threshold-based Financial Performance rate determination is fail-closed for all currencies in v1.0 until a complete configuration is approved.

## Non-authorization

These decisions do not authorize Momentum implementation or invent an Accounting threshold. They authorize only deterministic fail-closed behavior and future controlled activation.