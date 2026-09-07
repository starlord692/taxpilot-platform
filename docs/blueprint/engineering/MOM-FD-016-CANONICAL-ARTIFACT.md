# MOM-FD-016 — Canonical Momentum Artifact Identity, Serialization, Lifecycle & Correction

**Status:** Founder-approved decision record  
**Capability:** Business Momentum v1.0  
**Decision family:** MOM-FD-016  
**Authority:** Founder governance

## 1. Purpose

This record captures the approved MOM-FD-016 governance decisions for the canonical Business Momentum assessment artifact.

It is a governance record, not an implementation design that introduces unapproved business semantics.

## 2. Approved Canonical Artifact Principles

The canonical Momentum assessment is an **immutable canonical assessment**.

A canonical assessment preserves the deterministic result and the context required to understand and reproduce that result, including where applicable:

- business scope;
- whole-business direction;
- relative rate;
- current observation context;
- comparison context;
- applicable policy versions;
- authoritative evidence references;
- provenance;
- limitations; and
- correction lineage.

## 3. Direction and Rate

The canonical artifact records direction and rate as distinct attributes.

Direction is governed by `MOM-DIRECTION-POLICY-001 v1.0`.

Rate is governed by `MOM-RATE-POLICY-001 v1.0`.

Neither attribute may be replaced by a score, ranking, confidence value, forecast, prediction, or recommendation.

## 4. Temporal and Comparison Context

The artifact preserves the temporal context used for the assessment, including the current observation context and the approved comparison context.

Comparison selection is governed by `MOM-COMPARISON-POLICY-001 v1.0`.

The canonical artifact must not lose the context needed to distinguish the observed period from the comparison period.

## 5. Evidence and Provenance

Authoritative evidence references must be preserved with the canonical assessment.

The artifact must retain the provenance and policy context necessary to explain how the deterministic result was produced.

The artifact must not imply that an internal database row, transient calculation, or AI output is itself the authoritative Momentum assessment unless it is part of the approved canonical artifact semantics.

## 6. Immutability

A published canonical assessment is immutable.

A later change in source evidence, policy, correction, reconstruction, or other governed context must not destructively rewrite the historical canonical assessment.

Historical retrieval must return the canonical assessment in its original governed context.

## 7. Corrections and Lineage

A correction does not mutate the prior canonical assessment into a new meaning.

A later corrected assessment creates a **new canonical assessment** while preserving explicit predecessor lineage to the earlier assessment.

The lineage relationship is part of the historical context and must remain distinguishable from the content of the later assessment.

The implementation must not infer correction lineage merely from timestamps, numerical differences, or ordering.

## 8. Historical Preservation

Historical canonical assessments must preserve the assessment that was valid under their original declared context.

Later reconstructions or corrected results are represented separately and must retain their own applicable context while linking to their predecessor where the governance semantics establish such a relationship.

This preserves both historical truth and later authoritative results without destructive replacement.

## 9. Serialization

The canonical artifact must serialize deterministically from its governed business meaning and declared context.

Serialization must preserve the semantic distinctions established by the approved governance decisions, including direction, rate, temporal/comparison context, evidence references, provenance, limitations, policy versions, and correction lineage.

Serialization must not introduce hidden scores, rankings, inferred confidence, prediction, recommendation, or AI-derived authority.

No technology-specific serialization format is prescribed by this governance record unless separately authorized.

## 9A. Identity and Deterministic History

The canonical assessment uses layered, business-scoped assessment identity and preserves explicit temporal context. Every correction creates a new assessment identity.

For deterministic historical retrieval, `assessment_created_at` is the primary ordering field and `assessment_identity` is the deterministic tie-breaker. Ordering and correction lineage are separate concepts: neither may be inferred from the other.

## 10. Lifecycle Boundary

The canonical artifact is the authoritative historical assessment object once created under the approved Momentum semantics.

This record does not introduce an unapproved DRAFT-to-PUBLISHED lifecycle assumption.

A later correction is represented as a new assessment with predecessor lineage rather than by rewriting the prior assessment.

## 11. Consumer Boundary

Consumers may read, present, and explain the canonical assessment.

Consumers may not:

- mutate the canonical assessment;
- recalculate an alternative Momentum result and present it as canonical;
- override direction or rate;
- remove historical lineage;
- replace authoritative evidence references with unapproved evidence;
- reinterpret policy versions; or
- convert the artifact into a forecast, score, ranking, or recommendation while representing that result as canonical Momentum.

AI may explain the artifact but has no authority to alter it or its deterministic result.

## 12. Policy Version Preservation

The canonical assessment preserves the policy versions applicable to its result.

At minimum, where applicable, this includes the direction, rate, and comparison policy versions, together with the source evidence and policy context required by the registered evidence contract.

Future policy versions must not silently rewrite historical assessments.

## 13. Non-Authorization

This decision record does not authorize:

- arbitrary schema fields beyond the approved canonical semantics;
- a particular database technology;
- mutable historical records;
- implicit lifecycle states;
- hidden scoring or weighting;
- prediction;
- recommendation;
- AI authority; or
- unrelated repository changes.

## 14. Approval Record

This document records the approved MOM-FD-016 decisions as carried forward into ES-004 Business Momentum v1.0 implementation governance.

The approved summary is:

- immutable canonical assessment;
- explicit direction and rate;
- current and comparison context;
- policy versions;
- authoritative evidence references;
- provenance and limitations;
- explicit correction lineage;
- historical retrieval preservation;
- corrections create a new assessment while preserving predecessor lineage.
- layered business-scoped assessment identity and explicit temporal context;
- deterministic history ordering by `assessment_created_at`, then `assessment_identity`;
- ordering separate from lineage.

**Implementation boundary:** The artifact semantics are authoritative for ES-004. Technology-specific implementation details remain subordinate to the approved engineering specification and must not add business-policy behavior.
