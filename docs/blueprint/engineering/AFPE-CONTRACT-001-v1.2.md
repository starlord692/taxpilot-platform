# AFPE-CONTRACT-001 — Accounting Financial Performance Evidence Contract

**Version:** 1.2
**Status:** Owner Published / Founder Registered for Momentum use
**Owner:** Accounting
**Scope:** One authorized business (`business_id`)
**Consumer:** Business Momentum and other explicitly authorized consumers
**Supersedes:** v1.1 executable representation
**Governing decisions:** AFPE-FD-012A–012M; AFPE-FD-013A–013E; AFPE-FD-014A–014E; AFPE-FD-015A–015H; AFPE-FD-016A–016G; AFPE-FD-017A–017F; AFPE-FD-018A–018H

## 1. Purpose and Authority

AFPE-CONTRACT-001 v1.2 is the Accounting-owned, technology-neutral, read-only evidence contract for Financial Performance.

Accounting remains authoritative for posted financial effects; observation-period identity, membership, and boundaries; materiality; monetary precision and rounding; correction, reversal, restatement, reconstruction, and lineage semantics.

This contract publishes evidence only. It does not determine Business Momentum direction, rate, aggregation, scoring, ranking, prediction, recommendation, confidence, or AI authority.

Momentum must not access Accounting repositories, persistence, ORM models, database structures, internal services, or unregistered outputs as evidence.

## 2. Registered Momentum-Eligible Fields

Exactly these fields are registered for Momentum v1.0:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

No other Accounting output is Momentum-eligible through this contract.

## 3. Logical Operations

```text
resolve_financial_performance_observation_contexts(
    request: ObservationContextResolutionRequest
) -> ObservationContextResolutionResponse | FinancialPerformanceEvidenceError

retrieve_financial_performance_evidence(
    request: FinancialPerformanceEvidenceRequest
) -> FinancialPerformanceEvidenceResponse | FinancialPerformanceEvidenceError
```

Both operations are read-only, deterministic, Accounting-owned, business-scoped, and subject to existing platform authorization. They do not prescribe transport, API paths, database queries, serializers, or internal service topology.

## 4. Authorization and Business Isolation

Every request contains:

- `business_id: UUID`
- `authorization_context: AuthorizationContext`

`AuthorizationContext` is an opaque representation of the existing platform authentication and business-scoped authorization context. A requested `business_id` never grants access by itself.

Accounting must validate authorization before returning evidence or observation contexts. This contract creates no new permission vocabulary, authorization model, retention policy, or bypass.

## 5. Observation-Context Resolution

### Request

`ObservationContextResolutionRequest` contains:

| Field | Type | Requirement |
|---|---|---|
| `business_id` | UUID | required |
| `current_observation_context` | `ObservationContextRequest` | required |
| `evidence_perspective` | `EvidencePerspective` | required |
| `authorization_context` | `AuthorizationContext` | required |

### Response

`ObservationContextResolutionResponse` contains:

| Field | Type | Requirement |
|---|---|---|
| `business_id` | UUID | required |
| `resolved_current_context` | `ObservationContext` | required |
| `permitted_comparison_contexts` | tuple of `PermittedComparisonContext` | required; may be empty |
| `contract_id` | literal `AFPE-CONTRACT-001` | required |
| `contract_version` | literal `1.2` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |

`PermittedComparisonContext` contains:

- `comparison_kind`, exactly one of:
  - `PREVIOUS_COMPARABLE_PERIOD`
  - `PRIOR_EQUIVALENT_PERIOD`
  - `APPROVED_ROLLING_WINDOW`
- `observation_context: ObservationContext`
- `availability_state: AVAILABLE | UNAVAILABLE | INSUFFICIENT`
- `limitations`
- `provenance`
- `policy_context`

Accounting determines only the governed validity, identity, boundaries, granularity, and availability of observation contexts. Momentum applies its separately approved comparison-selection policy to the permitted contexts; Accounting does not determine Momentum direction or rate.

## 6. Evidence Retrieval Request

`FinancialPerformanceEvidenceRequest` contains:

| Field | Type | Requirement |
|---|---|---|
| `business_id` | UUID | required |
| `current_observation_context` | `ObservationContextRequest` | required |
| `comparison_observation_context` | `ObservationContextRequest` | required |
| `evidence_perspective` | `EvidencePerspective` | required |
| `authorization_context` | `AuthorizationContext` | required |

`EvidencePerspective` is exactly:

```text
HISTORICAL_REPORTED
CURRENT_RECONSTRUCTION
```

Consumers must not submit arbitrary date ranges, construct Accounting period identities, derive period membership, or reinterpret declared observation boundaries.

## 7. Paired Evidence Response

`FinancialPerformanceEvidenceResponse` contains:

| Field | Type | Requirement |
|---|---|---|
| `business_id` | UUID | required |
| `current_result` | `FinancialPerformanceEvidenceResult` | required |
| `comparison_result` | `FinancialPerformanceEvidenceResult` | required |
| `comparison_determinations` | `FinancialPerformanceComparisonDeterminations` | required |
| `contract_id` | literal `AFPE-CONTRACT-001` | required |
| `contract_version` | literal `1.2` | required |
| `evidence_perspective` | `EvidencePerspective` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |

`current_result` and `comparison_result` are independent. A missing, invalid, unavailable, or insufficient comparison result must never be interpreted as the current result or as an aggregate result.

## 8. Independent Financial Performance Result

`FinancialPerformanceEvidenceResult` contains:

| Field | Type | Requirement |
|---|---|---|
| `observation_context` | `ObservationContext` | required |
| `evidence_result_id` | string | required |
| `evidence_state` | `EvidenceState` | required |
| `period_revenue_total` | `FinancialPerformanceFieldEvidence` or null | conditional |
| `period_expense_total` | `FinancialPerformanceFieldEvidence` or null | conditional |
| `period_net_result` | `FinancialPerformanceFieldEvidence` or null | conditional |
| `qualifiers` | `EvidenceQualifiers` | required |
| `evidence_references` | tuple of `EvidenceReference` | required |
| `provenance` | `EvidenceProvenance` | required |
| `policy_context` | `AccountingPolicyContext` | required |
| `lineage` | `EvidenceLineage` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |

When `evidence_state` is `UNAVAILABLE` or `INSUFFICIENT`, applicable unavailable or insufficient fields are null and at least one limitation is required.

## 9. Field Evidence and Accounting Materiality

Each `FinancialPerformanceFieldEvidence` contains:

| Field | Type | Requirement |
|---|---|---|
| `value` | `MonetaryValue` | required |
| `materiality` | `AccountingMaterialityDetermination` | required |
| `evidence_references` | tuple of `EvidenceReference` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |

`AccountingMaterialityDetermination` contains:

- `outcome: string` — Accounting-defined published materiality outcome;
- `materiality_policy_id: string`;
- `materiality_policy_version: string`;
- `basis: string`;
- `limitations: tuple of EvidenceLimitation`.

The materiality outcome’s meaning is governed solely by the declared Accounting materiality policy. Momentum consumes it and must not calculate, infer, override, or reinterpret it.

## 10. Monetary Representation

`MonetaryValue` contains:

| Field | Type | Requirement |
|---|---|---|
| `amount` | base-10 decimal string | required |
| `currency` | ISO 4217 alphabetic currency code | required |
| `scale` | non-negative integer | required |
| `rounding_mode` | string | required |

Amounts must not be represented as binary floating point. Consumers must not infer, convert, or re-round a published amount.

## 11. Comparison Determinations

`FinancialPerformanceComparisonDeterminations` contains one `FieldComparisonDetermination` for each eligible field.

`FieldComparisonDetermination` contains:

| Field | Type | Requirement |
|---|---|---|
| `field` | one registered field name | required |
| `baseline_eligibility` | `BaselineEligibility` | required |
| `currency_compatibility` | `CurrencyCompatibility` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |
| `provenance` | `EvidenceProvenance` | required |
| `policy_context` | `AccountingPolicyContext` | required |

`BaselineEligibility` is exactly:

```text
ZERO
NEAR_ZERO
ELIGIBLE
UNDETERMINABLE
```

Its rules are Accounting-owned:

- exact governed normalized zero → `ZERO`;
- supported configured currency with `0 < abs(baseline) < N` → `NEAR_ZERO`;
- supported configured currency with `abs(baseline) >= N` → `ELIGIBLE`;
- unavailable currency, threshold configuration, precision/rounding context, or other required governed context → `UNDETERMINABLE`.

No supported currency or numeric threshold `N` is currently configured. Therefore, for v1.0, threshold-based Financial Performance baseline eligibility is `UNDETERMINABLE` for every currency, with an explicit limitation.

`CurrencyCompatibility` is exactly:

```text
SAME_CURRENCY
DIFFERENT_CURRENCY
UNDETERMINABLE
```

Only `SAME_CURRENCY` is comparison-compatible. Momentum performs no currency conversion and must not select an exchange-rate source.

## 12. Observation Context

`ObservationContext` contains:

- `observation_period_id`
- `period_start`
- `period_end`
- `granularity`
- `inclusion_basis: POSTING_DATE`
- `period_policy_id`
- `period_policy_version`
- `reconstruction_context_id` or null
- `as_of` or null

The declared interval is `[period_start, period_end)`. It is an Accounting-owned description of governed period meaning, not authority for a consumer to derive or alter membership.

## 13. States, Qualifiers, and Limitations

`EvidenceState` is exactly:

```text
AVAILABLE
UNAVAILABLE
INSUFFICIENT
```

Qualifiers remain independent:

- reproducibility;
- freshness context;
- material contradiction;
- limitations.

A technical or delivery failure is not an Accounting evidence state. It must never be silently converted into an available result, stable conclusion, or any Momentum outcome.

## 14. Historical, Reconstruction, and Lineage Semantics

`HISTORICAL_REPORTED` returns an immutable published evidence artifact under its recorded historical reporting context.

`CURRENT_RECONSTRUCTION` returns a distinct result under a declared reconstruction context and `as_of` value. It does not overwrite, collapse, or reinterpret historical reported evidence.

`EvidenceLineage` contains explicit lineage identity, predecessor evidence-result identity where applicable, supersession context, and revision context. Consumers must not infer lineage from timestamps, ordering, or changed totals.

Historical results preserve their originally declared evidence, policy, threshold-policy context where one existed, provenance, limitations, and lineage.

## 15. Determinism and Errors

For identical governed Accounting evidence, request context, observation contexts, evidence perspective, policy versions, materiality context, and authorization scope, operations return semantically equivalent results.

Technical/access outcomes use `FinancialPerformanceEvidenceError`:

```text
UNAUTHENTICATED
UNAUTHORIZED_BUSINESS_SCOPE
OBSERVATION_CONTEXT_NOT_FOUND
INVALID_OBSERVATION_CONTEXT
OBSERVATION_CONTEXT_RESOLUTION_UNAVAILABLE
DELIVERY_FAILURE
```

Business-evidence inability is represented in a successful response through `UNAVAILABLE` or `INSUFFICIENT`, applicable comparison determination, and preserved limitations.

## 16. Consumer Restrictions

Authorized consumers may retrieve, preserve, present, and apply separately authorized policy to the published evidence.

They may not:

- bypass this contract;
- query Accounting persistence, repositories, ORM models, or internal services;
- recalculate Accounting evidence;
- derive Accounting periods;
- calculate or reinterpret Accounting materiality;
- choose a near-zero threshold;
- infer a supported currency;
- perform currency conversion;
- redefine correction, reversal, restatement, reconstruction, or lineage semantics;
- mutate published evidence;
- substitute internal Accounting read models for unavailable evidence.

## 17. Momentum Registration and Change Control

AFPE v1.2 remains registered for Momentum only for the three listed Financial Performance fields.

This contract does not authorize new fields, dimensions, thresholds, Momentum rate policy, whole-business rate, scoring, weighting, ranking, prediction, recommendation, AI authority, or canonical Momentum identity/history semantics.

Any change to Accounting business meaning, eligibility, period semantics, materiality, currency, baseline threshold, evidence states, historical/reconstruction semantics, lineage, authorization, or consumer restrictions requires Accounting ownership and applicable Founder governance.
