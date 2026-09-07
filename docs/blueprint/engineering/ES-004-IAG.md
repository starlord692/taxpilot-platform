# ES-004-IAG — Business Momentum Implementation Authorization

**Status:** Founder Approved  
**Capability:** Business Momentum  
**Version:** 1.0  
**Authorization Type:** Implementation Authorization  
**Scope:** ES-004 Business Momentum v1.0

## 1. Purpose

This document authorizes implementation of Business Momentum v1.0 within the approved ES-004 scope.

Implementation is authorized only against the approved Business Momentum governance decisions, evidence contracts, policies, artifact semantics, and read-contract semantics defined by the authoritative documents referenced by this authorization.

Implementation must not introduce new business-policy decisions.

## 2. Authoritative Evidence Boundary

Business Momentum shall consume only authoritative evidence exposed through the approved Business Momentum Evidence Contract Registry.

For v1.0, the authoritative registered evidence contract is:

**AFPE-CONTRACT-001 v1.0**

The explicitly registered Momentum-eligible fields are:

- `period_revenue_total`
- `period_expense_total`
- `period_net_result`

Momentum shall not directly consume Accounting internal models, repositories, services, database tables, or unregistered outputs.

In particular, the following are not Momentum evidence boundaries:

- `GeneralLedgerEntry`
- `AccountBalance`
- Trial Balance
- Profit and Loss statements
- Balance Sheet statements
- internal Accounting repositories
- internal Accounting services

Future evidence contracts may become authoritative only through the approved evidence-contract registration process.

## 3. Approved Momentum Policies

Implementation shall follow these Founder-approved policies:

- `MOM-DIRECTION-POLICY-001 v1.0`
- `MOM-RATE-POLICY-001 v1.0`
- `MOM-COMPARISON-POLICY-001 v1.0`

Their approved semantics shall not be altered during implementation.

### Direction

Whole-business direction uses:

- `IMPROVING`
- `DETERIORATING`
- `BROADLY_UNCHANGED`
- `INSUFFICIENT_INFORMATION`

### Dimension Movement

Dimension movement uses:

- `IMPROVING`
- `DETERIORATING`
- `STABLE`
- `INSUFFICIENT_INFORMATION`

### Rate

Relative rate uses:

- `GRADUAL`
- `MODERATE`
- `RAPID`
- `NOT_DETERMINABLE`

### Comparison

Approved comparison contexts are:

- `PREVIOUS_COMPARABLE_PERIOD`
- `PRIOR_EQUIVALENT_PERIOD`
- `APPROVED_ROLLING_WINDOW`
- `NO_VALID_COMPARISON`

No implementation may invent additional comparison windows or silently substitute incomparable periods.

## 4. V1.0 Evidence Availability

The approved Momentum dimensions are:

1. Financial Performance
2. Cash & Receivables
3. Expenses
4. Operations
5. Customers
6. Suppliers

Growth/Expansion remains contextual and Compliance is not a standalone Momentum dimension.

For the initial v1.0 implementation, only Financial Performance has registered authoritative evidence.

Therefore the implementation must not fabricate or substitute evidence for the other dimensions.

Under `MOM-DIRECTION-POLICY-001 v1.0`, fewer than three valid core dimensions results in:

**`INSUFFICIENT_INFORMATION`**

The implementation must therefore fail closed rather than infer a whole-business direction from the available Financial Performance evidence alone.

## 5. Evidence Failure

Momentum shall fail closed when required evidence is:

- unavailable
- insufficient
- stale under the applicable evidence policy
- materially contradictory
- otherwise unable to support the declared result

Invalid or unavailable evidence must never silently become:

- `STABLE`
- `BROADLY_UNCHANGED`
- `IMPROVING`
- `DETERIORATING`

Where no valid comparison exists:

- Direction → `INSUFFICIENT_INFORMATION`
- Rate → `NOT_DETERMINABLE`

The reason and limitation context must be preserved.

## 6. Whole-Business Direction

Implementation shall follow `MOM-DIRECTION-POLICY-001 v1.0`.

The six core dimensions are treated equally.

The policy requires:

- a minimum of three valid dimensions;
- a strict majority for `IMPROVING`;
- a strict majority for `DETERIORATING`;
- `BROADLY_UNCHANGED` only where sufficient valid evidence supports that conclusion;
- `INSUFFICIENT_INFORMATION` where the minimum evidence requirement is not satisfied.

Counts are decision mechanics only and must not become a numerical Momentum score.

The implementation must not introduce:

- hidden weighting;
- scoring;
- ranking;
- single-dimension overrides;
- AI-based determination.

## 7. Relative Rate

Implementation shall follow `MOM-RATE-POLICY-001 v1.0`.

Rate is independent of direction.

Implementation shall:

- use approved comparison contexts;
- use the approved normalized movement semantics;
- respect approved reference bases;
- handle zero and near-zero baselines according to policy;
- handle sign transitions according to policy;
- require comparable periods;
- fail closed where rate cannot be determined.

Implementation must not invent numerical rate thresholds or convert rate into a score.

AI must not determine or override rate.

## 8. Canonical Momentum Assessment

Business Momentum shall produce the approved canonical Momentum assessment.

The canonical artifact shall preserve, as applicable:

- assessment identity;
- business identity;
- direction;
- rate;
- current comparison context;
- comparison context;
- dimension results;
- authoritative evidence references;
- evidence state;
- contract versions;
- policy versions;
- provenance;
- limitations;
- correction lineage;
- historical context.

The canonical assessment is immutable.

A correction must create a new assessment while preserving predecessor lineage.

Historical assessments must not be destructively rewritten.

## 9. Historical and Correction Semantics

Historical Momentum must preserve the canonical historical assessment and its declared context.

A later correction or reconstruction must create a distinct assessment and preserve lineage to the predecessor.

Implementation must not:

- overwrite historical assessments;
- infer lineage from timestamps alone;
- silently replace historical results;
- collapse original and corrected assessments into one mutable record.

## 10. Read Contract

Business Momentum shall expose read-only consumer semantics for:

- retrieving the current Momentum assessment;
- retrieving Momentum history;
- retrieving a specific Momentum assessment.

Consumers may:

- retrieve;
- present;
- explain

canonical Momentum.

Consumers may not:

- recalculate;
- mutate;
- override;
- score;
- rank;
- replace;
- reinterpret into an alternative Momentum result;
- convert the result into a forecast.

AI may explain or interpret the canonical result but has no authority to determine or override Momentum.

## 11. Prohibited Implementation Changes

This authorization does not authorize:

- modification of Accounting reversal semantics;
- modification of Accounting correction/restatement semantics;
- modification of `AFPE-CONTRACT-001 v1.0`;
- invention of Accounting materiality thresholds;
- invention of comparison windows;
- Momentum scoring;
- hidden weighting;
- Momentum confidence scoring;
- Momentum prediction;
- recommendation authority;
- use of Health as Momentum evidence;
- use of DNA as Momentum evidence;
- use of Season as Momentum evidence;
- use of Goals as Momentum evidence;
- use of Brief as Momentum evidence;
- use of Confidence as Momentum evidence;
- revival of historical Momentum implementation;
- unrelated repository refactoring.

## 12. Verification Requirements

Implementation must include verification of:

1. authoritative evidence-boundary enforcement;
2. registered-field enforcement;
3. deterministic comparison selection;
4. dimension movement classification;
5. whole-business direction;
6. relative-rate classification;
7. fail-closed evidence behavior;
8. canonical artifact immutability;
9. correction lineage;
10. historical retrieval;
11. business isolation;
12. read-only behavior;
13. absence of unauthorized scoring/weighting;
14. absence of AI decision authority;
15. regression safety.

Required engineering verification:

- Ruff
- MyPy
- focused Momentum tests
- full backend test suite

No verification result may be represented as passing unless the corresponding command has actually been executed.

## 13. Implementation Scope

Authorized implementation scope is limited to ES-004 Business Momentum v1.0.

Expected implementation areas include:

- `backend/app/modules/momentum/**`
- Momentum tests under `backend/tests/**momentum`
- required Alembic migration(s)
- minimal API/router registration where required

No unrelated capability work is authorized.

## 14. Founder Authorization

The Founder approved the following authorization:

> **Approve ES-004-IAG and authorize Codex to implement Business Momentum v1.0 within the approved ES-004 scope and constraints. Implementation shall consume only registered authoritative evidence, follow all approved Momentum policies and artifact/read-contract semantics, fail closed where evidence is insufficient, preserve historical/correction lineage, and make no unauthorized business-policy decisions or unrelated repository changes.**
