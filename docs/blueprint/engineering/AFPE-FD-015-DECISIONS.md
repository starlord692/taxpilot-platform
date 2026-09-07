# AFPE-FD-015 — Executable Accounting Evidence Contract Semantics

**Status:** Founder Approved  
**Scope:** Executable semantics for AFPE-CONTRACT-001 following AFPE-FD-014  
**Implementation authorization:** None  
**Momentum implementation:** Remains blocked pending contract revision, audit, and remaining Momentum governance.

## Authority

This decision record captures the Founder-approved AFPE-FD-015A through AFPE-FD-015H decisions. It converts the approved AFPE-FD-014 semantics into contract-level requirements without introducing new Accounting policy or Momentum authority.

## AFPE-FD-015A — Paired Financial Performance Results

**Approved position: Explicit independent current and comparison result objects.**

The AFPE response shall expose independent `current_result` and `comparison_result` objects.

Each result shall independently expose exactly the three registered Momentum-eligible Financial Performance fields:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

Each result shall carry its own applicable observation context, evidence/result identity, evidence state, qualifiers, materiality result, provenance, policy context, historical/reconstruction context, lineage, and limitations.

The contract shall not permit a missing, invalid, or unavailable comparison result to be interpreted as the current result or as an aggregate result.

## AFPE-FD-015B — Field-Level Materiality

**Approved position: Accounting publishes field-level materiality outcomes.**

For each eligible Financial Performance field, the response shall expose the Accounting-owned materiality outcome applicable to that field and observation result.

The materiality result shall preserve the applicable materiality policy identity/version and sufficient basis and limitation context to make the determination explainable and auditable.

Momentum consumes this result and shall not calculate, infer, override, or reinterpret Accounting materiality.

No new numeric threshold or formula is created by this decision. Previously approved Accounting materiality policy parameters remain authoritative.

## AFPE-FD-015C — Observation-Context Resolution

**Approved position: Separate Accounting-owned technology-neutral resolver.**

Accounting shall provide a technology-neutral operation for resolving valid Accounting observation contexts relevant to a requested business and current observation context.

The resolver shall return only contexts permitted by Accounting's governed observation-period semantics. Accounting remains authoritative for period identity, boundaries, granularity, validity, and availability.

Momentum applies `MOM-COMPARISON-POLICY-001 v1.0` to the permitted contexts. Accounting shall not determine Momentum direction or rate, and Momentum shall not manufacture Accounting observation contexts.

The exact operation/request/response representation must remain faithful to this decision and may not introduce unapproved Accounting or Momentum semantics.

## AFPE-FD-015D — Baseline Eligibility / Near-Zero

**Approved position: Explicit Accounting baseline-eligibility determination.**

Accounting shall expose a deterministic baseline eligibility determination for percentage-based Financial Performance movement. The representation shall distinguish at least:

- `ELIGIBLE`
- `ZERO`
- `NEAR_ZERO`
- `UNDETERMINABLE`

The actual near-zero threshold/value remains an Accounting-owned policy parameter and must be explicitly governed and versioned before implementation depends on it. Momentum shall not select or infer that threshold.

Momentum behavior remains:

- `ZERO` → rate `NOT_DETERMINABLE`
- `NEAR_ZERO` → rate `NOT_DETERMINABLE`
- `UNDETERMINABLE` → rate `NOT_DETERMINABLE`
- `ELIGIBLE` → the approved relative-movement calculation may proceed, subject to all other approved validity conditions.

## AFPE-FD-015E — Currency Compatibility

**Approved position: Explicit compatibility result; no consumer conversion.**

Accounting shall explicitly establish whether the current and comparison monetary values are compatible for the mandated comparison.

For v1.0, same-currency values are required for the Financial Performance relative-movement calculation. Momentum shall not perform currency conversion or select an exchange-rate source.

The governed compatibility semantics are:

- `SAME_CURRENCY` → comparison-compatible;
- `DIFFERENT_CURRENCY` → not comparison-compatible;
- `UNDETERMINABLE` → not comparison-compatible.

When comparison is not compatible because of currency, Momentum shall produce:

- Direction: `INSUFFICIENT_INFORMATION`
- Rate: `NOT_DETERMINABLE`

## AFPE-FD-015F — Evidence-State Handling

The existing primary Accounting evidence states remain:

- `AVAILABLE`
- `UNAVAILABLE`
- `INSUFFICIENT`

Independent qualifiers remain applicable for reproducibility, freshness, material contradiction, and limitations.

Contract delivery or transport errors shall remain distinct from governed Accounting evidence states and shall not be silently converted into them.

## AFPE-FD-015G — Determinism and Provenance

Every current/comparison result shall preserve sufficient declared context to explain the exact governed result, including as applicable:

- business identity;
- observation context;
- evidence/result identity;
- contract identity/version;
- Accounting policy versions;
- materiality policy/version;
- historical/reconstruction context;
- lineage;
- provenance;
- reproducibility/freshness/contradiction qualifiers;
- limitations.

The contract shall preserve deterministic behavior under the same declared context and authoritative Accounting state. It shall not infer historical truth from timestamps alone.

## AFPE-FD-015H — Momentum Consumer Boundary

Momentum may read the registered Accounting evidence contract, including current/comparison results, materiality outcomes, baseline eligibility, currency compatibility, observation contexts, provenance, policy metadata, lineage, and limitations.

Momentum shall not:

- access Accounting repositories, database tables, models, or internal services as evidence;
- calculate Accounting materiality;
- create or derive Accounting periods;
- perform currency conversion;
- reinterpret Accounting policy;
- repair Accounting evidence;
- override Accounting evidence states.

## Non-Authorization

AFPE-FD-015 does not authorize Business Momentum implementation, database changes, API implementation, migration, or changes to Accounting internals.

It also does not approve a whole-business Momentum rate policy, canonical Momentum identity serialization, or deterministic Momentum history implementation. Those remain separate governance matters.

## Required Contract Consequence

`AFPE-CONTRACT-001` must be revised to expose these approved executable semantics before ES-004 implementation may resume.
