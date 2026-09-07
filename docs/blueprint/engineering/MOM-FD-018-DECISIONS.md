# MOM-FD-018 — Financial Performance Relative Rate Policy

**Status:** Founder-approved — restored/published governance record
**Capability:** Business Momentum v1.0
**Authority:** Founder governance
**Scope:** Financial Performance relative rate

## Approved Decision

For Financial Performance, relative movement is:

```text
abs(current - comparison) / abs(comparison)
```

A valid non-zero comparison baseline is required.

- Zero baseline results in `NOT_DETERMINABLE`.
- Near-zero baseline results in `NOT_DETERMINABLE` unless separately approved.
- Sign transition results in `NOT_DETERMINABLE`.
- Non-comparable periods result in `NOT_DETERMINABLE`.
- Relative movement below 10% is `GRADUAL`.
- Relative movement from 10% to below 25% is `MODERATE`.
- Relative movement of 25% or greater is `RAPID`.
- Stable movement results in `NOT_DETERMINABLE`.
- Invalid, unavailable, insufficient, stale, or contradictory evidence results in `NOT_DETERMINABLE`.

Whole-business rate remains `NOT_DETERMINABLE` in v1.0.

AI has no authority to determine, override, or alter the rate result.

## Scope

This restored record preserves Founder-approved governance only. It does not itself authorize implementation, APIs, persistence, database design, or any other implementation-specific decision.
