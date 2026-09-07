# ES-004-IMP-PLAN — Business Momentum v1.0 Implementation Plan

**Status:** Founder Approved  
**Capability:** Business Momentum  
**Version:** 1.0  
**Depends on:** ES-004-IAG  
**Implementation Branch:** `codex/es-004-business-momentum-v1`  
**Base:** `main`

## 1. Purpose

This plan translates the approved ES-004 implementation authorization into a controlled engineering execution plan.

It is an implementation plan, not a source of new business policy. Where this plan conflicts with an approved governance artifact, the approved governance artifact prevails.

## 2. Implementation Objective

Implement Business Momentum v1.0 as a deterministic, evidence-bound, business-scoped capability that produces an immutable canonical Momentum assessment and exposes read-only retrieval semantics.

The implementation must preserve the approved authority chain:

**Accounting → AFPE-CONTRACT-001 → Momentum Evidence Registry → Business Momentum → approved Momentum policies → canonical assessment → read-only consumers**

## 3. Authoritative Evidence Boundary

The implementation shall consume authoritative evidence only through the registered evidence-contract boundary.

For v1.0, the only registered contract is:

**AFPE-CONTRACT-001 v1.2**

The only currently registered Momentum-eligible fields are:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

Momentum must not directly depend on Accounting internal models, repositories, services, or database tables.

The implementation must not treat existing Accounting read models as a substitute for the owner-published evidence contract.

Accounting resolves permitted Financial Performance observation contexts. For every comparison, Momentum retrieves independent `current_result` and `comparison_result` values through AFPE v1.2 and consumes Accounting's field-level materiality determination. Momentum must not construct Accounting observation contexts or calculate or reinterpret Accounting materiality.

## 4. V1.0 Dimension Coverage

The approved Momentum dimensions are:

1. Financial Performance
2. Cash & Receivables
3. Expenses
4. Operations
5. Customers
6. Suppliers

Only Financial Performance currently has registered authoritative evidence.

The implementation must therefore represent unavailable dimensions explicitly rather than fabricate or infer them.

Because the approved whole-business direction policy requires at least three valid core dimensions, the v1.0 whole-business direction will resolve to `INSUFFICIENT_INFORMATION` until sufficient registered evidence exists.

## 5. Module Structure

Create a dedicated Momentum module under:

`backend/app/modules/momentum/`

The implementation should preserve separation of concerns across appropriate layers, including:

- domain models and value semantics;
- application/orchestration logic;
- evidence-contract integration boundary;
- persistence/infrastructure;
- read/API boundary.

The exact internal class and file structure should follow established repository conventions without introducing unrelated architectural changes.

## 6. Processing Pipeline

The implementation pipeline shall conceptually follow:

```text
registered evidence
        ↓
evidence validation
        ↓
comparison-context selection
        ↓
dimension movement classification
        ↓
whole-business direction
        ↓
relative rate
        ↓
canonical Momentum assessment
        ↓
immutable persistence
        ↓
read-only retrieval
```

Each stage must preserve the evidence and policy context required by the approved canonical artifact.

## 7. Evidence Validation

Before evidence is used, the implementation must validate the requirements established by the approved contract and Momentum governance, including as applicable:

- business scope;
- registered contract and version;
- eligible field identity;
- observation-period identity;
- current/comparison context;
- evidence state;
- reproducibility requirements;
- provenance;
- material contradiction state;
- applicable limitations.

Financial Performance evidence also requires valid baseline eligibility and compatible currency under AFPE v1.2. Zero, near-zero unless separately approved, undeterminable baseline, different currency, or an invalid/non-comparable result fails closed for rate.

Evidence that cannot support a valid deterministic conclusion must fail closed.

## 8. Comparison Selection

Implement `MOM-COMPARISON-POLICY-001 v1.0` exactly.

The controlled contexts are:

- `PREVIOUS_COMPARABLE_PERIOD`
- `PRIOR_EQUIVALENT_PERIOD`
- `APPROVED_ROLLING_WINDOW`
- `NO_VALID_COMPARISON`

The approved selection priority is:

1. `PREVIOUS_COMPARABLE_PERIOD`
2. `PRIOR_EQUIVALENT_PERIOD`
3. `APPROVED_ROLLING_WINDOW` where authorized
4. `NO_VALID_COMPARISON`

The implementation must not invent periods, blend comparison windows, silently use incomparable periods, or allow Season to override the approved policy.

When no valid comparison exists:

- direction must be `INSUFFICIENT_INFORMATION`;
- rate must be `NOT_DETERMINABLE`.

## 9. Dimension Movement

Implement the approved dimension movement vocabulary:

- `IMPROVING`
- `DETERIORATING`
- `STABLE`
- `INSUFFICIENT_INFORMATION`

Movement results must retain current value/context, comparison value/context, materiality result where applicable, evidence identity, and relevant provenance/limitations.

The implementation must not determine source-domain materiality itself. Accounting-owned materiality semantics remain within the Accounting evidence contract/policy boundary.

## 10. Whole-Business Direction

Implement `MOM-DIRECTION-POLICY-001 v1.0`.

Requirements include:

- equal treatment of the six approved core dimensions;
- minimum three valid core dimensions;
- strict majority for `IMPROVING`;
- strict majority for `DETERIORATING`;
- `BROADLY_UNCHANGED` only where sufficient valid evidence supports that result;
- fewer than three valid dimensions → `INSUFFICIENT_INFORMATION`;
- no single-dimension override;
- no hidden weighting;
- no numerical Momentum score.

The current v1.0 evidence set contains only one valid dimension, so the implementation must return `INSUFFICIENT_INFORMATION` for whole-business direction.

## 11. Relative Rate

Implement `MOM-RATE-POLICY-001 v1.0`.

Rate must remain independent from direction and use only approved comparison contexts.

The implementation must respect the approved handling for:

- normalized movement magnitude;
- reference basis;
- zero baselines;
- near-zero baselines;
- sign transitions;
- period comparability;
- insufficient evidence.

No unapproved numerical thresholds may be invented during implementation.

For Financial Performance, relative movement is `abs(current - comparison) / abs(comparison)` using a valid non-zero comparison baseline. Below 10% is `GRADUAL`; 10% to below 25% is `MODERATE`; 25% or greater is `RAPID`. Stable movement, invalid or unavailable evidence, insufficient evidence, stale evidence, contradictory evidence, non-comparable periods, zero or near-zero baseline unless separately approved, and sign transition result in `NOT_DETERMINABLE`. Whole-business rate is `NOT_DETERMINABLE` in v1.0.

Rate must not become a score, average, ranking, confidence value, prediction, or recommendation.

## 12. Canonical Artifact and Persistence

Implement the approved immutable canonical Momentum assessment.

The artifact must preserve, as applicable:

- assessment identity;
- business identity;
- direction;
- rate;
- current context;
- comparison context;
- dimension results;
- evidence references;
- evidence state;
- contract versions;
- policy versions;
- provenance;
- limitations;
- correction lineage;
- historical context.

Historical assessments must be immutable.

A correction must create a new assessment and preserve the predecessor relationship.

Persistence must be business-scoped and must prevent cross-business retrieval.

Use the existing repository migration/persistence conventions. No Accounting schema or semantic changes are authorized.

## 13. Read Contract

Implement read-only consumer operations corresponding to:

- `get_current_momentum`
- `get_momentum_history`
- `get_momentum_assessment`

The read layer may retrieve and present canonical assessments.

It must not expose mutation, recalculation, override, scoring, ranking, or alternative Momentum-generation semantics.

AI may explain or interpret a canonical result but is not an authority for determining or overriding it.

## 14. Testing Plan

Tests shall cover at least:

### Evidence boundary

- registered contract acceptance;
- registered-field enforcement;
- rejection of unregistered evidence;
- rejection of direct Accounting-internal dependency as Momentum authority.

### Evidence validity

- unavailable evidence;
- insufficient evidence;
- stale evidence where applicable;
- materially contradictory evidence;
- non-reproducible evidence where applicable;
- preservation of failure reason and limitation context.

### Comparison

- previous comparable period;
- prior equivalent period;
- approved rolling window where applicable;
- no valid comparison;
- prevention of invented or blended windows.

### Movement and direction

- deterministic dimension movement;
- minimum-three-dimension rule;
- strict-majority behavior;
- broadly unchanged behavior;
- current v1.0 one-dimension result being `INSUFFICIENT_INFORMATION`;
- no hidden weighting or scoring.

### Rate

- approved rate semantics;
- zero/near-zero handling;
- sign transitions;
- incomparable periods;
- `NOT_DETERMINABLE` fail-closed behavior.

### Canonical artifact

- immutable historical assessment;
- correction creates a new assessment;
- predecessor lineage;
- policy/contract traceability;
- historical retrieval.

### API and isolation

- read-only operations;
- no unauthorized mutation endpoint;
- business isolation;
- deterministic repeated evaluation.

### Regression

Run the existing backend regression suite after focused Momentum tests.

## 15. Verification Commands

The implementation must run and report actual results for:

```text
uv run ruff check .
uv run mypy .
uv run pytest
```

Focused Momentum tests should also be run before the full suite.

No command may be reported as passing unless it was actually executed.

## 16. Allowed Repository Scope

Implementation is limited to:

- `backend/app/modules/momentum/**`
- `backend/tests/**momentum`
- `backend/alembic/versions/**`
- minimal router registration required to expose the approved read contract.

No unrelated repository refactoring is authorized.

## 17. Explicitly Out of Scope

The implementation must not:

- change Accounting reversal semantics;
- change Accounting correction/restatement semantics;
- modify AFPE-CONTRACT-001 semantics;
- invent Accounting materiality thresholds;
- add unapproved evidence contracts;
- use Accounting internals as Momentum authority;
- use Health, DNA, Season, Goals, Brief, Confidence, or Forecast as Momentum evidence;
- revive historical Momentum implementation as authoritative;
- add AI decision authority;
- add scoring, weighting, ranking, prediction, or recommendation authority;
- modify unrelated capabilities.

## 18. Implementation Stop Conditions

Codex must stop and report rather than invent policy if implementation encounters a requirement that is not resolved by the approved authorities.

Examples include:

- missing business-policy semantics;
- missing evidence-contract semantics;
- unspecified comparison behavior;
- unspecified rate threshold semantics;
- unresolved canonical identity behavior;
- unresolved correction/lineage semantics;
- requirements that would require changing another bounded context.

Any such gap must return to Founder governance before implementation continues.

## 19. Expected Deliverable

The implementation deliverable consists of:

1. Business Momentum v1.0 module;
2. approved evidence-contract integration boundary;
3. deterministic policy execution;
4. immutable canonical assessment persistence;
5. correction/history lineage;
6. read-only retrieval contract;
7. comprehensive tests;
8. actual verification results;
9. clear list of changed files;
10. confirmation that no unauthorized repository areas were modified.

Implementation must remain on the dedicated ES-004 branch and must not be merged to `main` without the subsequent review and Founder acceptance gates.
