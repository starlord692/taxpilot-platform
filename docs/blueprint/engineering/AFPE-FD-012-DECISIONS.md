# AFPE-FD-012 — Executable Financial Performance Evidence Read Contract Decisions

**Status:** Founder Approved  
**Owner:** Accounting  
**Consumer:** Business Momentum  
**Contract:** AFPE-CONTRACT-001 v1.0 → executable v1.1 publication

## Authority

These decisions record the Founder-approved AFPE-FD-012A through AFPE-FD-012M decisions for finalizing the executable, technology-neutral read boundary of AFPE-CONTRACT-001. They do not authorize Momentum implementation and do not alter the business semantics of AFPE-CONTRACT-001 v1.0.

## 012A — Provider ownership

Accounting owns and publishes the executable provider/read boundary for AFPE-CONTRACT-001. Momentum is a consumer only. The provider must not expose Accounting persistence, ORM models, repositories, database structures, or internal service contracts as the public evidence contract.

## 012B — Operation model

The contract exposes one logical read operation: **Retrieve Financial Performance Evidence**. It is read-only, business-scoped, deterministic, and Accounting-owned.

## 012C — Request scope

The logical request identifies:

- `business_id`;
- current observation-period context;
- comparison observation-period context; and
- historical-reported versus current-reconstruction context.

The consumer does not define Accounting period membership, materiality, reversal, correction, adjustment, or restatement semantics.

## 012D — Current and comparison retrieval

Current and comparison observation contexts are explicitly identified. Momentum must not supply arbitrary ranges and independently derive Accounting periods. Accounting resolves the meaning of each observation context under its governed period policy.

## 012E — Result structure

The logical result contains, at minimum:

- business identity;
- observation-period identity;
- evidence/result identity;
- contract identity and version;
- the three registered financial fields;
- evidence state;
- reproducibility qualifier;
- freshness qualifier/context;
- material-contradiction qualifier;
- provenance;
- applicable policy context;
- historical/reconstruction context;
- lineage; and
- limitations.

The only Momentum-eligible fields in v1.0 remain `period_revenue_total`, `period_expense_total`, and `period_net_result`.

## 012F — Typed monetary values

Financial amounts must have an explicit Accounting-owned monetary representation including amount and currency, with applicable monetary precision/rounding context where required. Momentum must not infer currency, conversion, or rounding semantics.

## 012G — Evidence references

The result carries structured references to governed contributing evidence sufficient for provenance and reproducibility. These references do not authorize Momentum to query Accounting internals directly.

## 012H — Evidence state and qualifiers

The primary evidence-state vocabulary is:

- `AVAILABLE`
- `UNAVAILABLE`
- `INSUFFICIENT`

Independent qualifiers for reproducibility, freshness, and material contradiction remain distinct and must not be collapsed into the primary state.

## 012I — Historical versus reconstruction context

The executable contract explicitly distinguishes:

- `HISTORICAL_REPORTED`; and
- `CURRENT_RECONSTRUCTION`.

Historical reported evidence is immutable. Current reconstruction is a distinct result and must not overwrite historical reported evidence.

## 012J — Consumer restrictions

Momentum may retrieve, inspect, preserve, present, and apply separately authorized Momentum policy to the published evidence. Momentum may not bypass the contract, access Accounting persistence/repositories/internal services, recalculate Accounting evidence, redefine period membership or materiality, reinterpret correction/reversal/restatement semantics, substitute internal Accounting read models, or mutate published evidence.

## 012K — Determinism

For identical governed Accounting evidence, business identity, observation contexts, policy versions, and materiality context, the contract result is deterministic. Generation time is not by itself historical truth and must not silently alter business meaning.

## 012L — Error/result semantics

Business evidence states remain distinct from technical failures. Evidence that exists but cannot support the declared result is `INSUFFICIENT`; required evidence that cannot currently be retrieved, does not exist, or is outside the contract boundary is `UNAVAILABLE`. Technical failures must not be silently converted into a positive or stable business conclusion.

## 012M — Authorization

The read operation uses the platform's existing authorization model and preserves business isolation and read-only semantics. No new Momentum-specific authorization philosophy is introduced by this decision set.

## Implementation boundary

These decisions authorize Accounting owner publication of the executable contract representation only. They do **not** authorize:

- Business Momentum implementation;
- changes to Momentum policy;
- new Momentum dimensions or eligible Accounting fields;
- changes to Accounting business meaning; or
- direct Momentum access to Accounting internals.
