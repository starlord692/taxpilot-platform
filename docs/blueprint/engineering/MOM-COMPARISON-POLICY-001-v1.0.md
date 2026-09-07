# MOM-COMPARISON-POLICY-001 v1.0

## Business Momentum Comparison Window Selection Policy

**Status:** Founder-approved / authoritative for Business Momentum v1.0  
**Authority:** Business Momentum governance  
**Scope:** Comparison-window selection for movement and relative-rate assessment  
**Version:** 1.0

## 1. Purpose

This policy defines the controlled comparison contexts that Business Momentum may use when assessing observed movement and relative rate.

The policy exists to ensure that current and comparison evidence are semantically and temporally comparable and that comparison selection is deterministic, explicit, and reproducible.

It does not redefine source-domain accounting periods, source-domain materiality, Season, Health, Confidence, Goals, Forecast, Brief, valuation, prediction, recommendation, or AI authority.

## 2. Controlled Comparison Vocabulary

The permitted comparison contexts are:

- `PREVIOUS_COMPARABLE_PERIOD`
- `PRIOR_EQUIVALENT_PERIOD`
- `APPROVED_ROLLING_WINDOW`
- `NO_VALID_COMPARISON`

No additional comparison context may be introduced without a Founder-approved policy change.

## 3. Current and Comparison Context Are Mandatory

Every Momentum movement and rate determination must identify:

- the current observation context; and
- the comparison context used, when one exists.

The context must preserve the applicable period identity, temporal boundaries, granularity, and relevant source-domain semantics.

A comparison must never be inferred solely from a convenient date range without satisfying the approved temporal and semantic rules.

## 4. Default Granularity

The comparison context should use the same observation granularity as the current context by default.

A different granularity may only be used where explicitly permitted by an approved comparison or source-domain policy and where the resulting comparison remains semantically valid.

Implementation must not silently aggregate, disaggregate, or mix granularities to manufacture a comparison.

## 5. Comparability Requirements

A candidate comparison must be both semantically and temporally comparable.

The comparison must be evaluated against the applicable evidence and observation-period semantics, including where relevant:

- period identity;
- period boundaries;
- granularity;
- inclusion basis;
- temporal ordering;
- source-domain meaning;
- historical/reconstruction context; and
- evidence availability and validity.

If these conditions cannot support a valid comparison, the candidate must not be used.

## 6. Deterministic Selection Priority

Where multiple approved comparison contexts are available, selection follows this deterministic priority:

1. `PREVIOUS_COMPARABLE_PERIOD`
2. `PRIOR_EQUIVALENT_PERIOD`
3. `APPROVED_ROLLING_WINDOW` — only where separately authorized for the applicable context
4. `NO_VALID_COMPARISON`

This is a selection policy, not a scoring or preference-learning mechanism.

The implementation must not invent additional fallback rules.

## 7. PREVIOUS_COMPARABLE_PERIOD

`PREVIOUS_COMPARABLE_PERIOD` is the primary comparison context.

It may be selected when the immediately preceding period is available and satisfies the approved semantic and temporal comparability requirements.

If the preceding period is not comparable, it must not be silently substituted with an arbitrary nearby period.

## 8. PRIOR_EQUIVALENT_PERIOD

`PRIOR_EQUIVALENT_PERIOD` is an explicit fallback when an equivalent prior period is authorized and semantically comparable.

The equivalent period must be determined from approved period semantics rather than arbitrary calendar manipulation.

This context must preserve the identity and boundaries of both the current and equivalent prior period.

## 9. APPROVED_ROLLING_WINDOW

`APPROVED_ROLLING_WINDOW` may be used only where a rolling comparison has been explicitly authorized for the applicable dimension/evidence context.

The rolling-window definition must be deterministic and versioned.

A rolling window must not be introduced merely because a fixed comparable period is unavailable.

## 10. NO_VALID_COMPARISON

When no approved comparison context satisfies the required conditions, the selected context is:

`NO_VALID_COMPARISON`

No arbitrary date range, nearest available period, incomplete history, or AI-generated substitute may be used in its place.

The resulting Momentum semantics are:

- direction → `INSUFFICIENT_INFORMATION`;
- rate → `NOT_DETERMINABLE`.

## 11. Evidence Validity

Invalid comparison evidence must not be silently used.

Evidence that is unavailable, insufficient, stale under the applicable policy, materially contradictory, non-reproducible where reproducibility is required, or otherwise incapable of supporting the comparison must fail closed.

Failure must not be converted into a neutral comparison or treated as evidence of stability.

## 12. Historical and Reconstruction Context

Comparison selection must preserve whether the evidence represents:

- an immutable historical reported state; or
- a later current reconstruction.

A later reconstruction must not be represented as though it were the historical reported comparison solely because it covers the same dates.

The comparison context must retain applicable evidence, contract, policy, and lineage information required for reproducibility and explanation.

## 13. Season Does Not Override Comparison Policy

Season is a separate business context.

Season may provide contextual interpretation where separately authorized, but it cannot override this comparison policy, manufacture a comparison window, or replace unavailable evidence.

## 14. No Blending

Momentum v1.0 must not blend multiple comparison windows into a synthetic comparison unless an explicit Founder-approved policy authorizes such behavior.

In particular, the implementation must not:

- average different comparison windows;
- combine prior-period and equivalent-period values;
- mix rolling and fixed windows;
- select a window based on which produces a preferred result; or
- use an AI-selected comparison.

## 15. Determinism

Given identical authoritative evidence, observation-period semantics, applicable policies, and policy versions, comparison selection must be deterministic.

The selected comparison context and policy version must be retained with the canonical Momentum assessment.

## 16. Direction and Rate Effects

Comparison-window selection has explicit downstream consequences:

- valid comparison + sufficient evidence → movement/rate may proceed under their respective policies;
- no valid comparison → direction is `INSUFFICIENT_INFORMATION`;
- no valid comparison → rate is `NOT_DETERMINABLE`.

A comparison-policy failure must not be converted into `BROADLY_UNCHANGED`.

## 17. AI Boundary

AI may explain why an approved comparison context was selected or why no valid comparison exists.

AI may not:

- select an unapproved comparison window;
- override deterministic selection;
- invent missing periods;
- alter period boundaries;
- blend comparison windows;
- reinterpret source-domain period semantics;
- convert an invalid comparison into a valid one; or
- use prediction or recommendation as a substitute for comparison evidence.

## 18. Versioning and Historical Preservation

The comparison-policy version must be preserved with each canonical Momentum assessment.

A future policy change creates a new version and must not silently rewrite historical comparison contexts or previously published Momentum assessments.

Historical retrieval must preserve the comparison context originally used.

## 19. Consumer Boundary

This policy is authoritative only for Business Momentum comparison-window selection.

It does not authorize consumers to recalculate or replace comparison contexts outside the approved Momentum pipeline.

Consumers may read and explain the recorded comparison context but may not reinterpret it as an alternative Momentum comparison policy.

## 20. Founder Approval Record

This document records the Founder-approved `MOM-FD-015` decisions and the adopted comparison selection policy as `MOM-COMPARISON-POLICY-001 v1.0`.

The approved positions are:

- every movement/rate identifies current and comparison contexts;
- controlled comparison vocabulary;
- same granularity as the default;
- explicit semantic and temporal comparability;
- deterministic selection;
- primary `PREVIOUS_COMPARABLE_PERIOD`;
- explicit `PRIOR_EQUIVALENT_PERIOD` fallback;
- `APPROVED_ROLLING_WINDOW` only where authorized;
- `NO_VALID_COMPARISON` when no approved comparison exists;
- no arbitrary fallback;
- no blending;
- Season cannot override;
- invalid comparison evidence fails closed;
- no valid comparison produces insufficient direction and non-determinable rate;
- historical/reconstruction context is preserved;
- policy is versioned;
- AI has no authority over comparison selection.

**Implementation authorization:** This artifact records an approved policy. It does not authorize unrelated policy changes or implementation outside the approved ES-004 scope.
