# MOM-FD-020 — Momentum Evidence Consumption & Comparison Binding

**Status:** Founder Approved
**Decision Type:** Governance / Policy
**Scope:** Business Momentum v1.0

## Founder Approval

Founder approved MOM-FD-020A through MOM-FD-020L.

## Decisions

### MOM-FD-020A — Registered-contract-only consumption
Business Momentum shall consume Financial Performance evidence only through the registered `AFPE-CONTRACT-001 v1.2` contract. It shall not access Accounting repositories, models, database tables, internal services, or internal read models directly.

### MOM-FD-020B — Observation-context resolution
Momentum shall use Accounting's `resolve_financial_performance_observation_contexts()` operation to obtain permitted comparison contexts. Momentum may select among contexts permitted by Accounting according to `MOM-COMPARISON-POLICY-001`; it shall not construct Accounting period semantics itself.

### MOM-FD-020C — Paired evidence retrieval
For every Financial Performance comparison, Momentum shall retrieve explicit `current_result` and `comparison_result` results from `retrieve_financial_performance_evidence()`. A single result shall never be reused as both sides of a comparison.

### MOM-FD-020D — Field-level materiality authority
Momentum shall consume Accounting's published `AccountingMaterialityDetermination` for each eligible Financial Performance field. Momentum shall not calculate or reinterpret Accounting materiality.

### MOM-FD-020E — Comparison eligibility
A Financial Performance field is eligible for movement classification only when its required evidence is valid under the registered contract, including sufficient evidence state, valid observation context, Accounting materiality determination, permitted comparison context, compatible currency, and valid baseline eligibility. Otherwise the field contributes no movement conclusion.

### MOM-FD-020F — Rate fail-closed behavior
For v1.0, `ZERO`, `NEAR_ZERO`, and `UNDETERMINABLE` baseline eligibility, `DIFFERENT_CURRENCY`, and invalid or non-comparable evidence result in `NOT_DETERMINABLE` rate behavior. Momentum shall not invent thresholds, perform currency conversion, or infer missing Accounting semantics.

### MOM-FD-020G — Direction and rate remain independent
A valid direction classification does not imply a valid rate classification. Financial Performance direction may be determinable while rate is `NOT_DETERMINABLE`.

### MOM-FD-020H — v1.0 whole-business rate
Whole-business rate remains explicitly `NOT_DETERMINABLE`. No whole-business rate-combination policy is approved for v1.0.

### MOM-FD-020I — Evidence preservation
Every Momentum assessment shall preserve references to the Accounting evidence results and applicable contract and policy contexts so the resulting assessment remains explainable and historically traceable.

### MOM-FD-020J — AI boundary
AI may explain or present the resulting Momentum assessment, but shall not select alternative evidence, calculate Accounting materiality, override comparison eligibility, override direction or rate, substitute missing evidence, or generate a Momentum conclusion outside deterministic approved policies.

### MOM-FD-020K — Fail-closed implementation boundary
If the contract returns an Accounting-owned semantic that Momentum cannot deterministically interpret under an approved policy, Momentum shall return the appropriate insufficient or not-determinable outcome rather than invent behavior.

### MOM-FD-020L — No implementation authorization from this decision alone
MOM-FD-020 closes the consumption-policy gate only. It does not authorize implementation unless subsequent reconciliation confirms that all implementation-critical semantics are closed.

## Authority and Constraints

This decision is subordinate to the TaxPilot Constitution and the approved Business Momentum governance decisions and policies, including `AFPE-CONTRACT-001 v1.2`, `MOM-DIRECTION-POLICY-001 v1.0`, `MOM-RATE-POLICY-001 v1.0`, `MOM-COMPARISON-POLICY-001 v1.0`, `MOM-FD-016`, and `MOM-FD-017`.

This decision authorizes no unrelated repository changes and does not authorize direct implementation of Accounting semantics.
