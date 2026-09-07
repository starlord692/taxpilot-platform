# AFPE-FD-014 — Accounting Financial Performance Evidence Contract Closure

**Status:** Founder Approved  
**Scope:** Accounting Financial Performance Evidence Contract  
**Implementation authorization:** None  
**Momentum implementation:** Remains blocked pending executable contract publication and subsequent governance gates.

## Authority

This decision record captures the Founder-approved closure of the Accounting-side semantic gaps identified after AFPE-CONTRACT-001 v1.1 and formalizes decisions AFPE-FD-014A through AFPE-FD-014E. It does not authorize Business Momentum implementation and does not authorize Momentum to invent or determine Accounting semantics.

## AFPE-FD-014A — Current and Comparison Values

**Approved position: Explicit paired results.**

The Accounting evidence response shall expose independent results for the requested current and comparison observation contexts. Each result shall independently contain the three Momentum-eligible Financial Performance fields:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

Each result shall retain its own observation context, evidence/result identity, evidence state, qualifiers, materiality result, provenance, policy context, historical/reconstruction context, lineage, and limitations as applicable.

A missing, invalid, or unavailable comparison result shall never be silently interpreted as the current result or as an aggregate result.

## AFPE-FD-014B — Field-Level Materiality Result

**Approved position: Accounting publishes field-level materiality results.**

For each eligible Financial Performance field, Accounting shall publish the applicable deterministic materiality outcome. The result shall carry the applicable materiality policy identity/version and sufficient basis/limitation context to explain the determination.

Momentum consumes the Accounting-owned materiality result. Momentum shall not calculate, infer, override, or reinterpret Accounting materiality.

The substantive Accounting materiality policy parameters remain governed by the previously approved Accounting materiality decisions. This decision does not introduce new numeric thresholds or formulas.

## AFPE-FD-014C — Observation-Context Resolution

**Approved position: Accounting-owned observation-context resolver.**

Accounting shall provide a technology-neutral mechanism for resolving valid Accounting observation contexts relevant to a requested current context and permitted comparison needs.

Accounting remains authoritative for the meaning, validity, boundaries, granularity, and availability of Accounting observation contexts. Momentum shall not derive Accounting periods from Accounting internals or manufacture period identities.

Momentum retains responsibility for applying `MOM-COMPARISON-POLICY-001 v1.0` to the permitted contexts returned by the Accounting contract. Accounting does not determine Momentum direction or rate.

## AFPE-FD-014D — Near-Zero Baseline

**Approved position: Accounting-owned deterministic baseline eligibility determination.**

Accounting shall define and publish the deterministic determination of whether a Financial Performance comparison baseline is suitable for percentage-based relative movement.

The determination shall distinguish at minimum the approved semantic cases required by the Momentum rate policy:

- zero baseline;
- near-zero baseline;
- baseline for which eligibility cannot be determined;
- baseline eligible for the approved relative-movement calculation.

The substantive near-zero threshold/value remains an Accounting-owned policy parameter and shall not be invented by Momentum. It must be explicitly governed and versioned before implementation depends on it.

## AFPE-FD-014E — Currency Compatibility

**Approved position: Explicit currency compatibility; no Momentum conversion.**

The Accounting evidence contract shall explicitly establish whether current and comparison monetary values are compatible for comparison.

For v1.0, current and comparison values must use the same currency for the mandated Financial Performance relative-movement calculation. Momentum shall not perform currency conversion or introduce an exchange-rate source.

Where current and comparison currencies differ, or compatibility cannot be established, the comparison is not valid for Momentum movement/rate determination. The resulting Momentum behavior remains:

- Direction: `INSUFFICIENT_INFORMATION`
- Rate: `NOT_DETERMINABLE`

## Non-Authorization

These decisions do not authorize:

- Business Momentum application implementation;
- database or API implementation;
- changes to Accounting internals;
- new Accounting materiality thresholds or formulas beyond separately approved policy;
- currency conversion;
- Momentum-derived Accounting periods;
- whole-business rate implementation;
- AI authority over any Accounting or Momentum determination.

## Required Contract Consequence

`AFPE-CONTRACT-001` must be revised so its executable representation faithfully exposes these approved semantics before Momentum implementation can resume.
