# AFPE-CONTRACT-001 — Accounting Financial Performance Evidence Contract

**Version:** 1.0  
**Status:** Owner Published / Founder Registered for Momentum use  
**Owner:** Accounting  
**Scope:** One business (`business_id`)  
**Consumer:** Business Momentum and other explicitly authorized consumers

## 1. Purpose

AFPE-CONTRACT-001 is the technology-neutral, Accounting-owned deterministic evidence contract for Financial Performance.

It publishes Accounting evidence for a business without exposing or authorizing direct consumption of Accounting persistence models, repositories, services, or database structures.

This contract defines evidence. It does not define Momentum direction, whole-business aggregation, Momentum rate, scoring, prediction, recommendation, or AI authority.

## 2. Authority

Accounting is authoritative for posted financial effects and Accounting-owned ledger-derived financial evidence.

The authority chain for Momentum consumption is:

```text
Accounting
   ↓
AFPE-CONTRACT-001 v1.0
   ↓
Momentum Evidence Contract Registry
   ↓
Business Momentum
```

Registration of this contract does not authorize Momentum to bypass this contract and read Accounting internals.

## 3. Business Scope

Each contract result is scoped to exactly one business:

- `business_id`

The contract does not establish parent-business, group, or cross-business aggregation semantics.

Consumers must preserve business isolation.

## 4. Observation Period

The contract identifies an Accounting-owned observation period for every published Financial Performance result.

The observation period is part of the evidence identity and must not be inferred by consumers from generated timestamps.

Period membership is determined by the Accounting contract's declared period policy and posting-date inclusion semantics.

The contract preserves the distinction between:

- transaction date — authoritative transaction provenance;
- posting date — authoritative basis for period inclusion;
- generated time — time the evidence result was produced, not historical truth by itself.

The contract must carry sufficient period identity and boundary information for consumers to distinguish observations deterministically.

## 5. Authoritative Fields

The following fields are published by this contract:

### `period_revenue_total`

Deterministic total revenue for the declared business and observation period under the Accounting evidence context.

### `period_expense_total`

Deterministic total expense for the declared business and observation period under the Accounting evidence context.

### `period_net_result`

Deterministic net result for the declared business and observation period under the Accounting evidence context.

These are the only fields registered for Business Momentum consumption in v1.0.

No other Accounting field or output is implicitly eligible for Momentum.

## 6. Evidence Identity

Evidence identity is layered. The following identities remain distinct:

- business identity;
- observation-period identity;
- evidence/result identity;
- contract identity and version;
- applicable Accounting policy identity/version;
- applicable materiality-policy identity/version;
- lineage references;
- historical/reconstruction context.

Persistence identifiers such as journal or ledger UUIDs are source references and are not substitutes for the published evidence identity.

## 7. Historical Reported State

A historical reported Financial Performance result is an immutable published evidence artifact representing what Accounting published at the stated historical reporting context.

Historical reported evidence must preserve the original result and its declared:

- business;
- observation period;
- evidence identity;
- contract version;
- Accounting policy context;
- materiality policy context;
- reporting/generation context;
- provenance;
- reproducibility state;
- limitations;
- lineage where applicable.

A later correction, restatement, or reconstruction must not destructively rewrite the historical reported artifact.

## 8. Current Reconstruction

A current reconstruction is a distinct result describing what Accounting now reconstructs a historical period to mean under an explicitly declared reconstruction context.

A reconstruction must identify the applicable:

- business;
- observation period;
- inclusion basis;
- as-of/reconstruction context;
- contributing evidence;
- Accounting policy context;
- materiality context;
- change/correction/restatement treatment;
- provenance;
- reproducibility state;
- limitations;
- lineage.

Current reconstruction and historical reported state are distinct concepts and must not be collapsed.

## 9. Reversal, Correction, Restatement and Lineage

The contract preserves Accounting-defined treatment of later changes.

Where a reversal, correction, adjustment, or restatement affects a Financial Performance result, the later result must be distinguishable from the predecessor and must preserve explicit lineage where applicable.

The contract must not infer correction or supersession merely from timestamps, record ordering, or changed totals.

Original historical evidence remains preserved even when a later result is authoritative for current reconstruction.

## 10. Evidence State

The contract supports the primary evidence states:

- `AVAILABLE`
- `UNAVAILABLE`
- `INSUFFICIENT`

These states must remain semantically distinct.

### AVAILABLE

Required contract-supported evidence can be retrieved for the declared business, period, and context and supports the declared result.

### UNAVAILABLE

Required evidence cannot currently be retrieved, does not exist, or is outside the contract boundary. The reason must be explicit.

### INSUFFICIENT

Evidence is available but cannot support the declared result under the required period, lineage, policy, or other declared context.

The contract may also carry independent qualifiers for:

- reproducibility;
- freshness;
- material contradiction.

These qualifiers must not be collapsed into availability or sufficiency.

## 11. Reproducibility

Reproducibility is explicitly declared rather than inferred from timestamps.

A result may be considered reproducible only when the declared context permits reconstruction of the result from the governed evidence set, including as applicable:

- business identity;
- observation period;
- inclusion basis;
- as-of context;
- complete contributing evidence references;
- applicable policy versions;
- change lineage;
- provenance;
- limitations.

A non-reproducible result is not automatically contradictory.

## 12. Freshness

Freshness is a policy-defined evidence context and must not be inferred solely from:

- `generated_at`;
- `posting_date`;
- `last_posted_at`;
- record age.

No arbitrary universal timestamp-age threshold is defined by this contract.

Where freshness is relevant, the applicable Accounting policy/context must be declared.

## 13. Material Contradiction

Material contradiction is distinct from non-reproducibility and insufficiency.

A contradiction exists only under the applicable Accounting-defined materiality semantics.

The contract preserves the relevant contradiction determination and its policy provenance where applicable.

Momentum must not independently redefine Accounting materiality.

## 14. Materiality

Accounting owns Financial Performance materiality semantics.

Materiality may use layered field- and period-specific context and may include both absolute and relative comparison considerations according to the approved Accounting policy.

Numeric thresholds, formulas, currency-conversion parameters, and other substantive Accounting parameters are policy-controlled and are not to be invented by Momentum consumers.

The materiality result and its policy version are preserved as provenance/context, not as a Momentum score.

## 15. Provenance

Provenance distinguishes business facts from policy context.

Minimum provenance/context includes, as applicable:

- business identity;
- observation period;
- contributing ledger/source references;
- inclusion basis;
- transaction-date provenance;
- posting-date period membership;
- contract identity/version;
- Accounting policy identity/version;
- materiality policy identity/version;
- historical/reconstruction context;
- as-of context;
- reporting/generation context;
- lineage;
- reproducibility state;
- limitations.

## 16. Versioning

The following version axes remain independent and must not be collapsed into a single version value:

- contract version;
- Accounting policy version;
- observation-period policy version;
- materiality-policy version;
- evidence/result revision;
- reconstruction context/version;
- lineage context;
- supersession context where explicitly defined.

Consumers must preserve the versions relevant to a published result.

## 17. Availability and Limitations

A published result must make material limitations explicit.

A limitation should identify, where applicable:

- reason;
- affected field(s);
- affected period/context;
- affected evidence;
- provenance;
- applicable policy/contract reference;
- reproducibility or consumer impact.

Consumers must not silently turn a limitation into a positive or stable business conclusion.

## 18. Deterministic Guarantees

For identical governed Accounting evidence, declared observation period, reconstruction/reporting context, policy versions, and materiality context, the contract result is deterministic.

The contract does not authorize consumers to recalculate its meaning using uncontrolled source data.

## 19. Momentum Eligibility

The following fields are explicitly eligible for Business Momentum v1.0:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

Eligibility is field-specific and does not make all Accounting outputs eligible.

The registered Momentum evidence boundary is the published contract, not the underlying Accounting implementation.

## 20. Consumer Restrictions

Consumers may:

- retrieve published evidence;
- preserve evidence identity and provenance;
- present evidence;
- use the evidence according to their own separately authorized business policy.

Consumers may not:

- bypass the contract;
- mutate historical published evidence;
- redefine Accounting period membership;
- redefine Accounting materiality;
- reinterpret Accounting correction/restatement semantics;
- infer missing evidence;
- replace unavailable evidence with internal Accounting read models.

Business Momentum may apply its separately approved Momentum policies to this evidence, but those policies do not alter the Accounting contract's source-domain meaning.

## 21. Registration Boundary

AFPE-CONTRACT-001 v1.0 is registered for Momentum consumption only through the controlled Business Momentum Evidence Contract Registry.

Registration authorizes only the explicitly listed Momentum-eligible fields.

Adding a new field or changing eligibility requires the approved evidence-contract governance and registration process.

## 22. Contract Change Control

Changes to business meaning, eligible fields, period semantics, historical/reconstruction semantics, evidence state semantics, materiality semantics, provenance, or correction/lineage behavior require the applicable Accounting ownership and Founder governance process before becoming authoritative for Momentum.

Consumers must not silently adapt to a changed contract as though the semantics were unchanged.
