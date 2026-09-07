# MOM-FD-014N — Relative Rate Policy Record

**Status:** Founder-approved — restored/published governance record
**Capability:** Business Momentum v1.0
**Authority:** Founder governance
**Governing policy:** `MOM-RATE-POLICY-001 v1.0`

## Approved Decision

Business Momentum relative rate uses normalized movement magnitude under a hybrid common and dimension-specific policy structure. Every determination uses an explicit reference basis.

- A zero baseline results in `NOT_DETERMINABLE`.
- Near-zero baselines require an approved deterministic safeguard.
- Sign transitions require an approved deterministic safeguard.
- Periods must be comparable.
- Valid determinations use ordered `GRADUAL`, `MODERATE`, and `RAPID` bands with explicit inclusivity semantics.
- Thresholds are policy parameters; implementation must not invent them.
- Rate scoring and averaging are prohibited.
- Whole-business rate requires a separate approved policy.
- The rate determination fails closed where the approved evidence, comparison, baseline, or policy conditions do not support a result.

AI has no authority to determine, override, score, average, or otherwise alter rate.

## Scope

This restored record preserves Founder-approved governance only. It does not itself authorize implementation, APIs, persistence, database design, or any other implementation-specific decision.
