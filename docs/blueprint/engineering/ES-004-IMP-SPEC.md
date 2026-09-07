# ES-004-IMP-SPEC — Business Momentum v1.0

**Status:** Founder Approved  
**Capability:** Business Momentum  
**Version:** 1.0  
**Authorization:** ES-004-IAG  
**Implementation Plan:** ES-004-IMP-PLAN

## 1. Specification Authority

This specification defines the approved implementation semantics for Business Momentum v1.0.

It does not authorize new business-policy decisions. Where an implementation detail is not resolved by this specification or its referenced approved authorities, implementation must stop rather than invent policy.

Authoritative dependencies:

- `KP-004` — Business Momentum product boundary
- `ES-004-IAG` — implementation authorization
- `ES-004-IMP-PLAN` — implementation plan
- `AFPE-CONTRACT-001 v1.0` — Accounting Financial Performance Evidence Contract
- `MOM-DIRECTION-POLICY-001 v1.0`
- `MOM-RATE-POLICY-001 v1.0`
- `MOM-COMPARISON-POLICY-001 v1.0`
- approved MOM-FD-011A/011B and MOM-FD-012–016 decisions

## 2. Authority Chain

The implementation shall preserve the following authority chain:

```text
Accounting authoritative financial facts
        ↓
AFPE-CONTRACT-001 v1.0
        ↓
Business Momentum Evidence Registry
        ↓
Business Momentum
        ↓
approved Momentum policies
        ↓
canonical Momentum assessment
        ↓
read-only consumers
```

Momentum is not an Accounting subsystem and must not bypass the evidence-contract boundary.

## 3. Authoritative Evidence

For v1.0, Momentum may consume only the following registered fields from `AFPE-CONTRACT-001 v1.0`:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

The contract is the technology-neutral evidence boundary.

Momentum must not directly consume Accounting persistence models, repositories, services, or internal APIs as authoritative evidence.

In particular, these are not direct Momentum evidence sources:

- General Ledger entries;
- Account Balance read models;
- Trial Balance;
- Profit and Loss statements;
- Balance Sheet statements;
- other unregistered Accounting outputs.

## 4. Evidence Validation

An evidence item may participate only when the approved contract and registry establish the required authority and context.

Validation must establish, as applicable:

- business scope;
- registered contract identity and version;
- eligible field identity;
- observation-period identity;
- current observation context;
- comparison context;
- evidence state;
- reproducibility requirements;
- provenance;
- material contradiction state;
- applicable limitations.

Evidence that does not satisfy the required conditions must fail closed.

Momentum must never infer a positive, negative, or stable result from missing or invalid evidence.

## 5. Comparison Semantics

Implement `MOM-COMPARISON-POLICY-001 v1.0`.

Controlled comparison contexts:

- `PREVIOUS_COMPARABLE_PERIOD`
- `PRIOR_EQUIVALENT_PERIOD`
- `APPROVED_ROLLING_WINDOW`
- `NO_VALID_COMPARISON`

Selection priority:

1. `PREVIOUS_COMPARABLE_PERIOD`
2. `PRIOR_EQUIVALENT_PERIOD`
3. `APPROVED_ROLLING_WINDOW` where explicitly authorized
4. `NO_VALID_COMPARISON`

Comparison requires semantic and temporal comparability.

The implementation must not:

- invent a comparison period;
- silently substitute an incomparable period;
- blend multiple windows into an unapproved window;
- allow Season to override comparison policy;
- infer a valid comparison from proximity alone.

When no valid comparison exists, the result must fail closed:

- direction → `INSUFFICIENT_INFORMATION`;
- rate → `NOT_DETERMINABLE`.

Current and comparison contexts must be preserved in the canonical assessment.

## 6. Dimension Movement

Dimension movement uses exactly:

- `IMPROVING`
- `DETERIORATING`
- `STABLE`
- `INSUFFICIENT_INFORMATION`

Movement must be derived deterministically from registered evidence and the applicable source-domain materiality result.

Momentum does not determine Accounting materiality.

A movement result must retain sufficient current/comparison context to explain how the result was obtained, including relevant evidence identity, materiality context, provenance, and limitations.

## 7. Whole-Business Direction

Implement `MOM-DIRECTION-POLICY-001 v1.0`.

Whole-business direction uses exactly:

- `IMPROVING`
- `DETERIORATING`
- `BROADLY_UNCHANGED`
- `INSUFFICIENT_INFORMATION`

Rules:

- the six approved core dimensions are treated equally;
- at least three valid core dimensions are required;
- a strict majority of valid dimensions is required for `IMPROVING`;
- a strict majority is required for `DETERIORATING`;
- otherwise `BROADLY_UNCHANGED` may be used only where sufficient valid evidence supports it;
- fewer than three valid dimensions results in `INSUFFICIENT_INFORMATION`;
- no single dimension overrides the policy;
- no hidden weighting or numerical scoring is permitted.

Counts are decision mechanics only and must never be exposed or persisted as a Momentum score.

### V1.0 Coverage Consequence

Only Financial Performance has registered authoritative evidence in v1.0.

Therefore fewer than three valid dimensions are available and the whole-business direction must resolve to:

**`INSUFFICIENT_INFORMATION`**

The implementation must not substitute other capabilities or Accounting internals to satisfy the minimum.

## 8. Relative Rate

Implement `MOM-RATE-POLICY-001 v1.0`.

Rate uses exactly:

- `GRADUAL`
- `MODERATE`
- `RAPID`
- `NOT_DETERMINABLE`

Rate is independent of direction.

Rate determination must:

- use only approved comparison contexts;
- use the approved normalized movement semantics;
- use the approved reference basis;
- respect zero-baseline handling;
- respect near-zero-baseline safeguards;
- respect sign-transition safeguards;
- require comparable periods;
- fail closed when determination is not possible.

No numerical rate thresholds may be invented during implementation. Thresholds or other substantive policy parameters must come from the approved policy authority.

Rate must not become:

- a score;
- an average;
- a ranking;
- a confidence value;
- a prediction;
- an urgency measure;
- a recommendation.

AI cannot determine or override rate.

## 9. Canonical Momentum Assessment

The canonical artifact is an immutable, business-scoped Momentum assessment.

It must preserve, as applicable:

- assessment identity;
- business identity;
- direction;
- rate;
- current observation context;
- comparison context;
- dimension movement results;
- authoritative evidence references;
- evidence state;
- contract version(s);
- policy version(s);
- provenance;
- limitations;
- correction lineage;
- historical/reconstruction context.

The artifact must be sufficient for a consumer to retrieve and explain the canonical result without recalculating it from uncontrolled source data.

## 10. Artifact Identity and Immutability

Each canonical Momentum assessment must have a distinct stable assessment identity within its business scope.

Historical canonical assessments are immutable.

A correction or later reconstruction must create a new assessment rather than mutate an existing historical artifact.

The predecessor relationship must be preserved explicitly where a later assessment corrects, supersedes, or reconstructs an earlier result according to the approved semantics.

The implementation must not infer historical lineage solely from timestamps or record ordering.

## 11. Historical Retrieval

Historical retrieval must preserve canonical historical results and their declared context.

A historical assessment must retain the policy and evidence context under which it was produced.

A later reconstruction is distinct from the historical reported assessment and must not destructively rewrite it.

History must be retrievable in a deterministic order and must preserve business isolation.

## 12. Correction Semantics

Corrections are represented by new canonical assessments with explicit predecessor lineage.

The implementation must not overwrite an earlier assessment to represent a correction.

Original and later results must remain distinguishable.

Any correction behavior that requires a new Accounting business-policy decision is outside this implementation specification and must stop for governance resolution.

## 13. Read Contract

The read layer shall support the conceptual operations:

- `get_current_momentum`
- `get_momentum_history`
- `get_momentum_assessment`

These operations are read-only.

They may retrieve and present canonical Momentum assessments and their preserved explanatory context.

They may not:

- recalculate Momentum;
- mutate canonical assessments;
- override canonical results;
- create alternative Momentum results;
- score or rank Momentum;
- convert Momentum into a forecast;
- silently reinterpret evidence into a different Momentum policy.

Existing platform authorization mechanisms remain applicable.

## 14. AI Boundary

AI is a consumer/interpreter of canonical Momentum, not its authority.

AI may:

- explain a canonical result;
- summarize supporting evidence;
- describe limitations;
- help users understand the result.

AI may not:

- determine canonical Momentum;
- override canonical Momentum;
- select unauthorized evidence;
- create hidden weighting;
- create a score;
- convert Momentum into a prediction or forecast without a separately authorized capability.

## 15. Persistence Requirements

Persistence must preserve:

- immutable canonical assessments;
- business identity;
- assessment identity;
- current/comparison contexts;
- dimension results;
- evidence references;
- contract/policy versions;
- provenance;
- limitations;
- correction lineage.

Persistence must enforce business isolation.

Any schema migration must follow existing repository Alembic conventions.

No Accounting schema change is authorized by ES-004.

## 16. V1.0 Dimension Model

The six approved core dimensions are:

1. Financial Performance
2. Cash & Receivables
3. Expenses
4. Operations
5. Customers
6. Suppliers

Growth/Expansion remains contextual and Compliance is not a standalone Momentum dimension.

Only Financial Performance has registered evidence in v1.0.

The implementation must represent unavailable dimensions explicitly and must not infer their movement from unrelated capabilities.

## 17. Determinism

For identical authoritative evidence, comparison context, policy versions, and declared context, repeated evaluation must produce the same canonical result.

The implementation must not depend on:

- AI-generated judgments;
- nondeterministic ranking;
- uncontrolled current-state data;
- hidden thresholds;
- arbitrary record ordering.

## 18. Evidence Failure and Limitations

Evidence failure must preserve the distinction between states such as:

- unavailable;
- insufficient;
- stale where governed;
- non-reproducible where governed;
- materially contradictory.

These states must not be collapsed into `STABLE` or `BROADLY_UNCHANGED` merely to produce a result.

Where a result cannot be supported, the canonical artifact must preserve the applicable limitation/reason context.

## 19. Forbidden Dependencies

Momentum implementation must not treat any of the following as authoritative Momentum evidence unless they independently become registered through the approved evidence-contract process:

- Health;
- DNA;
- Season;
- Goals;
- Brief;
- Confidence;
- Forecast;
- historical Momentum implementation;
- unregistered Accounting outputs;
- arbitrary domain-service results.

## 20. Implementation Boundary

Implementation is restricted to ES-004 Business Momentum v1.0.

Expected implementation areas:

- `backend/app/modules/momentum/**`
- `backend/tests/**momentum`
- required `backend/alembic/versions/**` migration(s)
- minimal router registration where required by the read contract.

Unrelated refactoring is prohibited.

## 21. Testing Requirements

The implementation must include tests for:

- authoritative evidence boundary;
- registered-field enforcement;
- business scope/isolation;
- evidence-state handling;
- fail-closed behavior;
- comparison selection;
- dimension movement;
- minimum-three-dimension direction rule;
- strict-majority direction behavior;
- v1.0 Financial Performance-only insufficient-information behavior;
- rate semantics;
- zero/near-zero/sign-transition safeguards;
- no scoring or hidden weighting;
- artifact immutability;
- correction creation and predecessor lineage;
- historical retrieval;
- read-only API behavior;
- deterministic repeated evaluation;
- regression behavior.

## 22. Verification

The implementation must execute and report actual results for:

```text
uv run ruff check .
uv run mypy .
uv run pytest
```

Focused Momentum tests must be executed before the full suite.

No test or verification command may be reported as passing unless actually executed.

## 23. Implementation Stop Conditions

Implementation must stop rather than invent policy when it encounters a requirement involving unresolved:

- business semantics;
- evidence-contract semantics;
- materiality semantics;
- comparison rules;
- rate thresholds or classification parameters;
- canonical identity semantics;
- persistence semantics that alter approved business meaning;
- correction/restatement semantics;
- read-contract authority.

Such a gap must return to Founder governance before implementation proceeds.

## 24. Acceptance Criteria

ES-004 v1.0 is implementation-complete only when:

1. Momentum consumes only registered authoritative evidence;
2. approved policies are implemented without reinterpretation;
3. invalid evidence fails closed;
4. current/comparison context is preserved;
5. whole-business direction obeys the minimum-three-dimension rule;
6. v1.0 correctly returns `INSUFFICIENT_INFORMATION` for whole-business direction with only Financial Performance registered;
7. rate follows the approved rate policy without invented thresholds;
8. canonical assessments are immutable;
9. corrections preserve predecessor lineage;
10. historical retrieval preserves canonical history;
11. read operations cannot mutate or recalculate Momentum;
12. AI has no canonical decision authority;
13. business isolation is enforced;
14. tests cover the approved invariants;
15. Ruff, MyPy, focused tests, and the full test suite have actual recorded results;
16. no unauthorized repository areas are modified.

## 25. Final Implementation Rule

The implementation must express the approved governance decisions in software, not create new governance decisions through code.

Where the specification is silent on a business-policy question, the correct implementation behavior is to stop and request governance clarification rather than guess.
