# AFPE-CONTRACT-001 — Accounting Financial Performance Evidence Contract

**Version:** 1.1
**Status:** Owner Published / Founder Registered for Momentum use
**Owner:** Accounting
**Scope:** One business (`business_id`)
**Consumer:** Business Momentum and other explicitly authorized consumers
**Supersedes for executable representation:** AFPE-CONTRACT-001 v1.0
**Governing decisions:** AFPE-FD-012A–012M; AFPE-FD-013A–013E

## 1. Purpose and Authority

AFPE-CONTRACT-001 v1.1 is the executable, technology-neutral, Accounting-owned read contract for Financial Performance evidence. It preserves AFPE-CONTRACT-001 v1.0 business meaning and publishes its exact read representation without exposing Accounting persistence models, repositories, ORM models, database structures, or internal service contracts.

Accounting remains authoritative for posted financial effects, observation-period membership, materiality, correction, reversal, restatement, lineage, and ledger-derived Financial Performance evidence. This contract publishes evidence only. It does not determine Momentum direction, rate, aggregation, scoring, ranking, prediction, recommendation, or AI authority.

## 2. Logical Operation

The sole logical operation is **Retrieve Financial Performance Evidence**. It is read-only, business-scoped, deterministic, and Accounting-owned.

```text
retrieve_financial_performance_evidence(request: FinancialPerformanceEvidenceRequest)
    -> FinancialPerformanceEvidenceResponse | FinancialPerformanceEvidenceError
```

The operation is technology-neutral. It neither prescribes transport, API paths, persistence, serializers, nor exceptions.

## 3. Request Representation

`FinancialPerformanceEvidenceRequest` contains exactly:

| Field | Type | Requirement | Meaning |
|---|---|---|---|
| `business_id` | UUID | required | The single authorized business scope. |
| `current_observation_context` | `ObservationContextRequest` | required | Accounting-owned identifier of the current governed observation context. |
| `comparison_observation_context` | `ObservationContextRequest` | required | Accounting-owned identifier of the comparison governed observation context. |
| `evidence_perspective` | `EvidencePerspective` | required | `HISTORICAL_REPORTED` or `CURRENT_RECONSTRUCTION`. |
| `authorization_context` | `AuthorizationContext` | required | Existing platform caller and business authorization context; it grants no new authority. |

`EvidencePerspective` is exactly:

```text
HISTORICAL_REPORTED
CURRENT_RECONSTRUCTION
```

`AuthorizationContext` is an opaque representation of the existing platform authorization context. Its contents and evaluation remain owned by the platform. A caller-supplied `business_id` is requested scope only and never grants access.

### ObservationContextRequest

`ObservationContextRequest` contains exactly:

| Field | Type | Requirement | Meaning |
|---|---|---|---|
| `observation_period_id` | string | required | Accounting-owned stable identity for the requested governed observation period. |
| `period_policy_id` | string | required | Identity of the governed Accounting period policy. |
| `period_policy_version` | string | required | Version of that period policy. |
| `reconstruction_context_id` | string | conditional | Required for `CURRENT_RECONSTRUCTION`; absent for `HISTORICAL_REPORTED`. |
| `as_of` | timezone-aware datetime | conditional | Required for `CURRENT_RECONSTRUCTION`; absent for `HISTORICAL_REPORTED`. |

Consumers identify Accounting contexts using this representation. They must not submit arbitrary date ranges, derive period membership, or reinterpret observation boundaries.

## 4. Response Representation

On a successful authorized retrieval, `FinancialPerformanceEvidenceResponse` contains exactly:

| Field | Type | Requirement |
|---|---|---|
| `business_id` | UUID | required |
| `current_observation` | `ObservationContext` | required |
| `comparison_observation` | `ObservationContext` | required |
| `evidence_perspective` | `EvidencePerspective` | required |
| `evidence_result_id` | string | required |
| `contract_id` | literal `AFPE-CONTRACT-001` | required |
| `contract_version` | literal `1.1` | required |
| `period_revenue_total` | `MonetaryValue` or null | conditional on evidence state |
| `period_expense_total` | `MonetaryValue` or null | conditional on evidence state |
| `period_net_result` | `MonetaryValue` or null | conditional on evidence state |
| `evidence_state` | `EvidenceState` | required |
| `qualifiers` | `EvidenceQualifiers` | required |
| `evidence_references` | tuple of `EvidenceReference` | required; may be empty only when the declared state/context supports no contributing evidence |
| `provenance` | `EvidenceProvenance` | required |
| `policy_context` | `AccountingPolicyContext` | required |
| `lineage` | `EvidenceLineage` | required |
| `limitations` | tuple of `EvidenceLimitation` | required; may be empty |

The only Momentum-eligible fields are exactly `period_revenue_total`, `period_expense_total`, and `period_net_result`. No other field is made eligible by this publication.

## 5. Observation Context

`ObservationContext` contains exactly:

| Field | Type | Requirement | Meaning |
|---|---|---|---|
| `observation_period_id` | string | required | Stable Accounting-owned period identity. |
| `period_start` | timezone-aware datetime | required | Inclusive declared boundary. |
| `period_end` | timezone-aware datetime | required | Exclusive declared boundary. |
| `granularity` | string | required | Accounting-declared period granularity. |
| `inclusion_basis` | literal `POSTING_DATE` | required | Accounting-owned basis for period membership. |
| `period_policy_id` | string | required | Period-policy identity. |
| `period_policy_version` | string | required | Period-policy version. |
| `reconstruction_context_id` | string or null | required | Null for historical reported evidence; declared identity for reconstruction. |
| `as_of` | timezone-aware datetime or null | required | Null for historical reported evidence; declared reconstruction context otherwise. |

`period_start` must precede `period_end`. The interval is `[period_start, period_end)`. This represents declared Accounting boundaries; it does not authorize consumers to derive or alter period membership.

## 6. Monetary Representation

`MonetaryValue` contains exactly:

| Field | Type | Requirement |
|---|---|---|
| `amount` | decimal string | required |
| `currency` | ISO 4217 alphabetic currency code | required |
| `scale` | non-negative integer | required |
| `rounding_mode` | string | required |

`amount` is a base-10 decimal string and must not be represented as binary floating point. `scale` and `rounding_mode` state the Accounting-owned precision context used for the published amount. Consumers must not infer, convert, or re-round currency values.

## 7. Evidence References, Provenance, and Policy Context

`EvidenceReference` contains exactly:

| Field | Type | Requirement |
|---|---|---|
| `reference_id` | string | required |
| `reference_type` | string | required |
| `source_capability` | literal `Accounting` | required |
| `role` | string | required |
| `period_membership` | string | required |
| `lineage_reference_id` | string or null | required |

References are governed provenance. They do not identify a public repository, ORM model, table, query, or internal service and do not authorize a consumer to retrieve Accounting internals.

`EvidenceProvenance` contains `reporting_generated_at` (timezone-aware datetime), `transaction_date_basis` (`TRANSACTION_DATE`), `period_membership_basis` (`POSTING_DATE`), and `historical_or_reconstruction_context` (`EvidencePerspective`). Generation time is not historical truth by itself.

`AccountingPolicyContext` contains `accounting_policy_id`, `accounting_policy_version`, `period_policy_id`, `period_policy_version`, `materiality_policy_id`, and `materiality_policy_version`, each as required strings.

`EvidenceLineage` contains `lineage_id` (string), `predecessor_evidence_result_id` (string or null), `supersession_context` (string or null), and `revision_context` (string or null). Lineage is explicit; consumers must not infer it from timestamps, ordering, or changed amounts.

## 8. Evidence State, Qualifiers, and Limitations

`EvidenceState` is exactly:

```text
AVAILABLE
UNAVAILABLE
INSUFFICIENT
```

`AVAILABLE` means required contract-supported evidence supports the declared result. `UNAVAILABLE` means required evidence cannot currently be retrieved, does not exist, or is outside the contract boundary. `INSUFFICIENT` means evidence is available but cannot support the declared result under the declared context.

`EvidenceQualifiers` contains exactly:

| Field | Type | Requirement |
|---|---|---|
| `reproducibility` | `REPRODUCIBLE` or `NOT_REPRODUCIBLE` | required |
| `freshness` | `FreshnessContext` | required |
| `material_contradiction` | `MATERIAL_CONTRADICTION_PRESENT` or `NO_MATERIAL_CONTRADICTION_DECLARED` | required |

`FreshnessContext` contains `policy_id`, `policy_version`, `declared_status`, and `basis`. It is policy-defined; no universal age threshold is implied. Qualifiers are independent and must not be collapsed into `evidence_state`.

`EvidenceLimitation` contains `reason`, `affected_fields` (tuple of strings), `affected_context`, `affected_evidence_reference_ids` (tuple of strings), `provenance_reference`, and `consumer_impact`. When evidence is `UNAVAILABLE` or `INSUFFICIENT`, at least one limitation is required.

## 9. Historical and Reconstruction Semantics

`HISTORICAL_REPORTED` returns the immutable published evidence artifact for its declared historical reporting context. `CURRENT_RECONSTRUCTION` returns a distinct current reconstruction under its declared `as_of` and reconstruction context. Neither perspective overwrites or collapses the other.

Corrections, reversals, adjustments, restatements, and reconstructions are represented through distinct evidence results and explicit lineage. This contract neither redefines Accounting treatment of those events nor allows consumers to reinterpret it.

## 10. Deterministic Result and Error Semantics

For identical governed Accounting evidence, request context, evidence perspective, observation contexts, policy versions, materiality context, and authorization scope, the operation returns a semantically equivalent response.

The operation returns `FinancialPerformanceEvidenceError` only for technical or access outcomes. It contains exactly `code`, `message`, and `details` (a non-business diagnostic mapping). Permitted codes are:

```text
UNAUTHENTICATED
UNAUTHORIZED_BUSINESS_SCOPE
OBSERVATION_CONTEXT_NOT_FOUND
INVALID_OBSERVATION_CONTEXT
DELIVERY_FAILURE
```

Technical errors are never converted to `AVAILABLE`, a positive financial conclusion, or a stable Momentum conclusion. A governed business-evidence inability is represented by `UNAVAILABLE` or `INSUFFICIENT` in a successful response, with limitations preserved.

## 11. Authorization and Consumer Boundary

The operation reuses the existing platform authentication and business-scoped authorization model. The platform must validate the caller's authorization for `business_id` before evidence is returned. This contract creates no new authorization vocabulary, permission system, retention model, or bypass.

Authorized consumers may retrieve, preserve, present, and apply separately authorized policy to published evidence. They may not bypass this contract; query Accounting repositories, persistence, ORM models, or internal services; recalculate Accounting evidence; redefine period membership, materiality, reversal, correction, restatement, or lineage semantics; mutate evidence; or substitute internal read models for unavailable evidence.

## 12. Momentum Registration Boundary

AFPE-CONTRACT-001 v1.1 remains registered for Business Momentum only through the controlled Momentum Evidence Contract Registry. Registration permits only:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

This executable representation does not authorize new fields, dimensions, rate parameters, direction policy, scoring, weighting, prediction, recommendation, or AI authority.

## 13. Change Control

Any change to the published business meaning, field eligibility, period semantics, monetary semantics, state semantics, policy context, historical/reconstruction distinction, lineage, authorization boundary, or consumer restrictions requires Accounting ownership and applicable Founder governance before it is authoritative.
