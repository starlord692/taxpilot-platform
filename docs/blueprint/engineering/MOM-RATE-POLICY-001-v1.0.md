# MOM-RATE-POLICY-001 v1.0

## Business Momentum Relative Rate Policy

**Status:** Founder-approved / authoritative for Business Momentum v1.0  
**Authority:** Business Momentum governance  
**Scope:** Relative rate classification  
**Version:** 1.0

## 1. Purpose

This policy defines the deterministic categorical vocabulary and classification framework for the relative rate of observed business movement.

Rate is separate from movement direction. It does not predict future movement, measure confidence, assign urgency, create a score, rank dimensions, or authorize recommendations.

## 2. Controlled Rate Vocabulary

Rate is limited to:

- `GRADUAL`
- `MODERATE`
- `RAPID`
- `NOT_DETERMINABLE`

No numerical rate score or additional rate category may be introduced without a Founder-approved policy change.

## 3. Authoritative Inputs

Rate may consume only:

1. registered authoritative Momentum evidence;
2. comparison contexts permitted by `MOM-COMPARISON-POLICY-001 v1.0`;
3. movement results produced under the approved Momentum movement policy;
4. the applicable versioned rate policy.

A rate classification must retain its current and comparison context.

## 4. Relative, Not Universal, Rate Semantics

Rate expresses the relative magnitude of observed movement against an explicitly declared reference basis.

It must not be implemented as an arbitrary universal percentage rule across all dimensions.

The policy adopts a **hybrid model**:

- common rate semantics provide the shared vocabulary and classification structure;
- dimension-specific deterministic rules may define the appropriate reference basis where justified by the nature of the dimension.

Any dimension-specific rule must be explicit, transparent, deterministic, versioned, and Founder-approved.

## 5. Reference Basis

Every rate determination must identify the reference basis used for its comparison.

The reference basis must be compatible with the approved comparison context and the source evidence semantics.

The implementation must not silently substitute an alternative baseline when the declared reference basis is invalid.

## 6. Normalized Movement Magnitude

Rate classification is based on normalized movement magnitude rather than raw absolute change alone.

The normalization method must be deterministic and appropriate to the declared dimension and reference basis.

The policy does not authorize implementation to invent a numeric normalization formula where the governing dimension policy has not supplied one.

## 7. Zero and Near-Zero Baselines

A zero baseline must not produce an undefined or misleading rate through ordinary division.

For a zero baseline, the applicable approved policy must provide an alternative reference basis; otherwise the rate is:

`NOT_DETERMINABLE`

Near-zero baselines require explicit safeguards so that insignificant denominator changes do not create artificial `RAPID` or `MODERATE` classifications.

Those safeguards must be deterministic and policy-versioned. No implementation default may be treated as an approved business threshold.

## 8. Sign-Transition Safeguards

Movement across zero requires explicit treatment because a sign transition can make a simple relative-rate calculation misleading.

A sign-transition case must use the applicable approved reference basis and deterministic rule.

If the approved semantics cannot determine a meaningful rate, the result is:

`NOT_DETERMINABLE`

The implementation must not manufacture a rate from an unstable or semantically invalid denominator.

## 9. Period Comparability

Current and comparison periods must be semantically and temporally comparable under `MOM-COMPARISON-POLICY-001 v1.0`.

A rate must not be calculated from incompatible granularities, invalid windows, or evidence that cannot support the declared comparison.

No valid comparison context results in:

`NOT_DETERMINABLE`

## 10. Ordered Rate Bands

Where a valid normalized movement magnitude is available, the approved rate vocabulary is ordered from lower to higher observed relative movement:

`GRADUAL → MODERATE → RAPID`

The boundaries between these categories must have explicit inclusivity semantics.

The threshold values are **policy parameters**, not implementation defaults. They require explicit Founder approval before being instantiated as numeric business rules.

This artifact therefore does not invent or imply numeric percentage bands.

## 11. Direction Independence

Rate and direction are independent attributes.

Examples of permitted combinations include:

- `IMPROVING` + `GRADUAL`
- `IMPROVING` + `RAPID`
- `DETERIORATING` + `MODERATE`
- `DETERIORATING` + `RAPID`
- `BROADLY_UNCHANGED` with `NOT_DETERMINABLE` where no meaningful rate can be established.

A direction value must never be inferred from rate, and a rate value must never be inferred from direction.

## 12. Stable Movement

`STABLE` movement does not automatically imply a rate category.

Under v1.0, stable movement produces:

`NOT_DETERMINABLE`

unless a future Founder-approved policy explicitly defines a different treatment.

## 13. Evidence Failure and Fail-Closed Behavior

The rate classifier must fail closed.

If required evidence is:

- unavailable;
- insufficient;
- stale under the applicable policy;
- materially contradictory;
- non-comparable;
- non-reproducible where reproducibility is required;
- missing a valid comparison context; or
- otherwise incapable of supporting the declared rate semantics;

then the rate must be:

`NOT_DETERMINABLE`

No failure state may be silently converted into `GRADUAL`, `MODERATE`, or `RAPID`.

## 14. Whole-Business Rate

Whole-business rate is a separate deterministic combination problem from dimension-level rate classification.

This policy does **not** authorize numerical averaging, weighted averaging, scoring, or ranking of dimension rates.

A whole-business rate may only be produced under a separate explicit, deterministic, transparent, versioned, Founder-approved categorical combination policy.

Until such a policy exists, implementation must not invent one.

## 15. Historical Preservation

A historical rate classification must preserve:

- the current observation context;
- the comparison context;
- the reference basis;
- applicable evidence references;
- rate-policy version;
- comparison-policy version;
- source-domain policy context;
- provenance;
- limitations; and
- any applicable historical/reconstruction context.

A later policy or evidence change must not silently rewrite a previously published canonical Momentum assessment.

## 16. AI Boundary

AI may explain or summarize a deterministic rate result.

AI may not:

- determine rate;
- override rate;
- invent a baseline;
- choose an unapproved comparison window;
- apply hidden thresholds;
- convert qualitative evidence into an unauthorized numerical rate;
- average or score rates;
- rank dimensions by rate;
- predict future movement from rate; or
- turn rate into a recommendation or urgency signal.

## 17. Determinism and Versioning

For identical authoritative evidence, comparison context, reference basis, and policy versions, the rate result must be deterministic.

The rate-policy version must be preserved with the resulting canonical Momentum assessment.

Any future change to rate semantics or thresholds requires a new approved policy version and must preserve historical results under their original policy context.

## 18. Explicit Non-Authorization

This policy does not authorize:

- universal numeric thresholds;
- percentage bands not separately approved;
- dimension-specific thresholds not Founder-approved;
- rate scoring;
- numerical averaging;
- whole-business rate combination without a separate approved policy;
- prediction;
- recommendation;
- AI authority; or
- changes to source-domain accounting or evidence semantics.

## 19. Founder Approval Record

This document records the Founder-approved `MOM-FD-014` decisions and the adopted hybrid rate-policy architecture as `MOM-RATE-POLICY-001 v1.0`.

The approved policy positions are:

- controlled rate vocabulary;
- rate independent from direction;
- only approved comparison contexts may be used;
- normalized movement magnitude;
- hybrid common and dimension-specific semantics;
- explicit reference basis;
- zero-baseline and near-zero safeguards;
- sign-transition safeguards;
- period comparability;
- ordered `GRADUAL → MODERATE → RAPID` bands;
- explicit threshold inclusivity;
- thresholds treated as policy parameters requiring Founder approval;
- no rate score or averaging;
- separate policy required for whole-business rate combination;
- fail-closed behavior;
- historical preservation and policy versioning;
- no AI authority.

**Implementation authorization:** This artifact records an approved policy. It does not authorize unrelated policy changes or implementation outside the approved ES-004 scope.
