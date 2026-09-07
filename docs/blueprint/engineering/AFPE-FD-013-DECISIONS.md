# AFPE-FD-013 — AFPE-CONTRACT-001 v1.1 Owner Publication Decisions

**Status:** Founder Approved  
**Owner:** Accounting  
**Contract:** AFPE-CONTRACT-001  
**Target publication:** v1.1

## Authority

These decisions record the Founder-approved AFPE-FD-013A through AFPE-FD-013E authorization for Accounting to finalize the exact executable representations of AFPE-CONTRACT-001 v1.1. They preserve the existing v1.0 business semantics and do not authorize Business Momentum implementation.

## 013A — Observation-context representation

Accounting is authorized to finalize the exact technology-neutral executable representation of the Accounting observation context, including sufficient information to identify the governed observation period and its boundary/inclusion semantics. Consumers must receive Accounting's period meaning rather than independently deriving period membership.

## 013B — Monetary-value representation

Accounting is authorized to finalize the exact technology-neutral representation of Financial Performance monetary values, including amount and currency and applicable monetary precision/rounding context where required. Consumers must not invent currency conversion or rounding semantics.

## 013C — Evidence-reference representation

Accounting is authorized to finalize the exact structured representation of contributing evidence references needed for provenance and reproducibility. Evidence references remain provenance and do not expose or authorize direct access to Accounting persistence, repositories, ORM models, or internal services.

## 013D — Evidence-state qualifier representation

Accounting is authorized to finalize the executable representation of the approved primary states `AVAILABLE`, `UNAVAILABLE`, and `INSUFFICIENT`, together with independent qualifiers for reproducibility, freshness, and material contradiction. These semantics must remain distinct and must not be collapsed into a single state.

## 013E — Request/response representation

Accounting is authorized to finalize the exact technology-neutral request and response structures for **Retrieve Financial Performance Evidence**, including request scope, authorization context, current/comparison observation contexts, historical-reported versus current-reconstruction context, typed evidence fields, states/qualifiers, provenance, policy context, lineage, limitations, deterministic behavior, and business/technical error semantics.

## Preservation constraints

The v1.1 publication authorized by 013A–013E must not change:

- Accounting ownership of posted financial effects and ledger-derived Financial Performance evidence;
- the three Momentum-eligible fields: `period_revenue_total`, `period_expense_total`, `period_net_result`;
- Accounting ownership of period membership and materiality;
- historical reported state immutability;
- current reconstruction as a distinct result;
- reversal/correction/restatement and lineage semantics;
- Momentum's fail-closed evidence requirements;
- Momentum direction/rate/aggregation policy;
- AI authority restrictions; or
- the prohibition on direct consumption of Accounting internals.

## Explicit non-authorization

These decisions authorize owner publication of the executable contract representation. They do not authorize Business Momentum implementation, database/API implementation choices beyond what is necessary to publish the contract, new evidence fields, new business policy, or any bypass of the approved Accounting-to-Momentum contract boundary.

If an Accounting-owned substantive semantic is still unresolved while preparing v1.1, publication must stop rather than invent a value.
