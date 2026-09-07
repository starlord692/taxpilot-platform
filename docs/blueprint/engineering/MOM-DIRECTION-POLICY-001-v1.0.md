# MOM-DIRECTION-POLICY-001 v1.0

## Business Momentum Whole-Business Direction Policy

**Status:** Founder-approved / authoritative for Business Momentum v1.0  
**Authority:** Business Momentum governance  
**Scope:** Whole-business direction only  
**Version:** 1.0

## 1. Purpose

This policy defines the deterministic, transparent combination of valid Business Momentum dimension movements into a whole-business direction.

It does not define source-domain evidence, source-domain materiality, comparison-window selection, relative-rate classification, Health, Confidence, Season, Goals, Forecast, Brief, valuation, prediction, recommendation, or AI authority.

## 2. Controlled Direction Vocabulary

Whole-business direction is limited to:

- `IMPROVING`
- `DETERIORATING`
- `BROADLY_UNCHANGED`
- `INSUFFICIENT_INFORMATION`

No additional direction values may be introduced by implementation without Founder-approved policy change.

## 3. Authoritative Inputs

Only valid dimension movement classifications produced from registered authoritative Momentum evidence may participate in whole-business direction.

The six core Momentum dimensions are treated equally:

1. Financial Performance
2. Cash & Receivables
3. Expenses
4. Operations
5. Customers
6. Suppliers

Growth/Expansion may provide contextual evidence where separately authorized, but it is not a standalone core dimension for this policy. Compliance is not a standalone Momentum dimension.

Source-domain owners remain authoritative for their evidence and materiality rules. Momentum does not reinterpret source-domain evidence or invent materiality.

## 4. Valid Dimension Movement

A core dimension is valid for whole-business direction only when its movement classification is supported by authoritative registered evidence and satisfies the approved evidence-failure rules.

Valid movement classifications are:

- `IMPROVING`
- `DETERIORATING`
- `STABLE`

`INSUFFICIENT_INFORMATION` is not treated as a valid directional vote.

Unavailable, insufficient, stale, or materially contradictory evidence fails closed and does not become `STABLE`.

## 5. Minimum Evidence Requirement

At least **3 valid core dimensions** are required to determine a whole-business direction.

If fewer than 3 core dimensions are valid:

`INSUFFICIENT_INFORMATION`

No inference, fallback, averaging, or AI interpretation may replace the missing evidence.

## 6. Direction Combination Rule

Among valid core dimensions:

- A **strict majority** of valid dimensions classified as `IMPROVING` produces whole-business `IMPROVING`.
- A **strict majority** of valid dimensions classified as `DETERIORATING` produces whole-business `DETERIORATING`.
- If neither direction has a strict majority, and the minimum evidence requirement is satisfied, the result is `BROADLY_UNCHANGED`.

Counts are decision mechanics only. They are **not a score, ranking, weighting system, or confidence measure**.

### Example

With 5 valid dimensions:

- 3 improving, 1 stable, 1 deteriorating → `IMPROVING`
- 3 deteriorating, 1 stable, 1 improving → `DETERIORATING`
- 2 improving, 2 deteriorating, 1 stable → `BROADLY_UNCHANGED`

The examples illustrate the policy mechanics and do not create additional business rules.

## 7. No Single-Dimension Override

No individual dimension may override the whole-business result solely because it is considered more important.

There are:

- no hidden weights;
- no numerical score;
- no weighted average;
- no priority dimension;
- no Health-based override;
- no Confidence-based override;
- no Season-based override;
- no Goals-based override;
- no Forecast-based override.

Any future exception would require an explicit Founder-approved policy change.

## 8. BROADLY_UNCHANGED Semantics

`BROADLY_UNCHANGED` means that sufficient valid evidence exists, but the approved combination rule does not produce a strict whole-business improving or deteriorating majority.

It must **not** be used as a synonym for:

- missing evidence;
- unavailable evidence;
- stale evidence;
- contradictory evidence;
- insufficient history;
- inability to compare periods.

Those conditions fail closed to `INSUFFICIENT_INFORMATION` where the policy requires insufficient information.

## 9. Evidence and Context Preservation

A canonical Momentum assessment must preserve the dimension-level evidence and policy context supporting the whole-business direction, including applicable:

- evidence references;
- current and comparison contexts;
- evidence-state information;
- source-domain policy versions;
- comparison-policy version;
- direction-policy version;
- limitations and provenance.

The whole-business direction is therefore explainable from the recorded deterministic inputs and policy version.

## 10. AI Boundary

AI may explain, summarize, or present the deterministic result.

AI may not:

- determine whole-business direction;
- override the deterministic result;
- invent missing dimensions;
- reinterpret invalid evidence as valid;
- apply hidden weighting;
- score or rank dimensions;
- convert uncertainty into direction;
- substitute prediction or recommendation for direction.

Human and governance authority remain above AI interpretation.

## 11. Determinism and Versioning

For the same authoritative evidence, declared comparison context, and policy versions, the whole-business direction must be deterministic and reproducible.

The policy version must be retained with the canonical Momentum assessment. A future policy change creates a new policy version and must not silently rewrite historical assessments.

## 12. Fail-Closed Requirements

The implementation must fail closed when the required evidence or policy context is not available.

In particular:

- fewer than 3 valid core dimensions → `INSUFFICIENT_INFORMATION`;
- invalid evidence → never converted to `STABLE`;
- contradictory evidence → not silently resolved;
- unavailable evidence → not inferred;
- insufficient historical/comparison context → not fabricated;
- AI output → never treated as authoritative direction.

## 13. Authority and Consumer Boundary

This policy is authoritative only for the whole-business direction combination step of Business Momentum v1.0.

It does not authorize changes to Accounting, Sales, Purchases, Expenses, Inventory, Customers, Suppliers, Payments, Health, Confidence, Season, Goals, Forecast, Brief, DNA, or other bounded contexts.

Consumers may read and explain the resulting direction, but may not recalculate or override it outside the approved Momentum policy.

## 14. Founder Approval Record

This document records the Founder-approved `MOM-FD-013` decisions and the exact coherence/conflict policy adopted as `MOM-DIRECTION-POLICY-001 v1.0`.

The policy was approved with the following governing positions:

- controlled direction vocabulary;
- registered evidence only;
- no single-dimension override;
- no hidden weighting/scoring;
- minimum three valid core dimensions;
- strict majority for improving/deteriorating;
- broadly unchanged only when evidence is sufficient but no strict majority exists;
- insufficient information when fewer than three valid dimensions exist;
- deterministic, transparent, versioned policy;
- preservation of supporting evidence and policy context;
- no AI authority.

**Implementation authorization:** This artifact defines an already-approved policy. It does not, by itself, authorize unrelated implementation or policy changes.
