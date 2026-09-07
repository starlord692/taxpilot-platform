# MOM-FD-019 — Canonical Assessment Identity and History Record

**Status:** Founder-approved — restored/published governance record
**Capability:** Business Momentum v1.0
**Authority:** Founder governance
**Scope:** Canonical Momentum assessment identity and history

## Approved Decision

Business Momentum uses a layered, business-scoped assessment identity. Canonical assessments are immutable.

Every correction creates a new assessment identity. Each assessment preserves its explicit temporal context. Historical and reconstruction context remain preserved and distinct.

For deterministic history retrieval:

1. `assessment_created_at` is the primary history-ordering field.
2. `assessment_identity` is the deterministic tie-breaker.

Ordering and correction lineage are separate concepts. Lineage does not determine historical ordering, and historical ordering does not infer lineage.

History retrieval is deterministic and fails closed where the required governed context cannot support it. Historical assessments must not be destructively updated.

## Scope

This restored record preserves Founder-approved governance only. It does not itself authorize implementation, APIs, persistence, database design, or any other implementation-specific decision.
