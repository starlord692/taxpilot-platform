# MOM-FD-017 — Business Momentum Read Contract

**Status:** Founder-approved governance artifact  
**Scope:** Business Momentum v1.0 read access and historical retrieval  
**Authority:** Business Momentum governance

## 1. Purpose

This document records the approved read-contract boundary for the canonical Business Momentum assessment.

The contract is technology-neutral and business-scoped. It defines what consumers may read and what they may not reinterpret or mutate.

## 2. Canonical Read Target

The read target is the canonical, immutable Business Momentum assessment produced under the approved Momentum policies.

A canonical assessment contains, at minimum, the approved result and its supporting context:

- business scope;
- whole-business direction;
- applicable relative rate where determinable;
- current observation context;
- comparison context;
- evidence references;
- provenance;
- applicable policy versions;
- limitations; and
- correction/history lineage where applicable.

The canonical assessment is an assessment artifact, not a recalculable view over arbitrary source-domain tables.

## 3. Business Scope

Reads are business-scoped.

A consumer may retrieve Momentum only within the authorized business scope established by the platform's existing authentication and authorization model.

The read contract does not create a new authorization mechanism or bypass existing platform access controls.

## 4. Read Operations

The approved read surface supports these technology-neutral operations:

1. **Read current canonical assessment** for an authorized business.
2. **Read a canonical assessment by its stable assessment identity.**
3. **Read historical canonical assessments** for an authorized business.
4. **Read the lineage/context associated with a canonical assessment**, including predecessor references where a correction created a later assessment.

Exact API paths, HTTP verbs, database queries, serializers, and framework-specific mechanisms are implementation details and are not defined by this governance artifact.

## 5. Historical Retrieval

Historical retrieval must preserve canonical history.

A historical assessment must be returned as the assessment that was published under its recorded context and policy versions. Retrieval must not silently recompute the historical result using current evidence or current policy.

Where a later correction or reconstruction exists, it is represented as a distinct assessment with explicit lineage to the affected predecessor rather than destructively replacing the predecessor.

History ordering is deterministic: `assessment_created_at` is the primary ordering field and `assessment_identity` is the deterministic tie-breaker. The canonical assessment's declared temporal/identity context remains preserved. Ordering is separate from correction lineage, and implementations must not infer business meaning from database row ordering alone.

## 6. Immutability

Consumers of the read contract cannot mutate a canonical assessment.

Corrections are represented by creating a new canonical assessment while preserving the predecessor and explicit lineage.

No consumer may update, delete, overwrite, or otherwise rewrite historical canonical Momentum through the read surface.

## 7. Consumer Capabilities

Consumers may:

- read the canonical result;
- present it to a user;
- explain its recorded evidence and policy context;
- display historical assessments;
- display correction lineage; and
- use the artifact for downstream presentation consistent with its declared meaning.

## 8. Consumer Restrictions

Consumers may not:

- recalculate Momentum from raw Accounting or other domain internals;
- recalculate direction using a different policy;
- recalculate rate using a different baseline or threshold;
- mutate the canonical assessment;
- override direction or rate;
- substitute missing evidence;
- score or rank Momentum dimensions;
- reinterpret a historical reconstruction as the original historical reported assessment;
- create an alternative canonical Momentum result outside the approved pipeline; or
- bypass business authorization.

## 9. AI Boundary

AI may consume the read contract to explain or summarize the canonical assessment.

AI is not an authority over the artifact. It may not change, recalculate, override, or replace the canonical Momentum result.

An AI explanation must remain distinguishable from the authoritative canonical assessment.

## 10. Evidence and Provenance Preservation

A read must expose or preserve the context necessary to understand the authority of the assessment, including applicable evidence references, policy versions, provenance, limitations, and historical/correction lineage.

The read contract must not strip context in a way that causes a consumer to mistake an assessment for an unsupported raw metric.

## 11. Historical vs Reconstruction Semantics

The read surface must preserve the distinction between:

- an immutable historical reported assessment; and
- a later current reconstruction.

Same business and same observation period do not make two artifacts the same historical result.

A later reconstruction must retain its distinct identity and declared context and must not overwrite the original historical artifact.

## 12. Determinism

Given the same canonical artifact and authorization context, read operations must return semantically equivalent results.

Historical retrieval must not depend on mutable current source-domain calculations.

## 13. Error and Absence Semantics

The read contract must distinguish at least the following situations:

- requested canonical assessment exists and is authorized;
- requested assessment does not exist;
- requested assessment exists but is outside the caller's authorization scope.

The implementation must not manufacture a Momentum result when no canonical assessment exists.

Absence of a canonical artifact is not permission to calculate one from unregistered evidence.

## 14. Version and Policy Context

Historical reads preserve the policy versions recorded on the canonical assessment, including applicable direction, rate, comparison, evidence-contract, and source-domain policy context.

Current policy versions must not be substituted for historical policy context during retrieval.

## 15. Technology-Neutral Boundary

This contract does not mandate:

- REST versus another transport;
- a particular database schema;
- ORM models;
- caching strategy;
- serialization library;
- URL or route naming;
- pagination mechanism; or
- internal service topology.

Those decisions remain implementation concerns subject to the approved Engineering Specification and Coding Standards.

## 16. Authority and Scope

This artifact records the approved `MOM-FD-017` read-contract and historical-retrieval decisions.

It applies only to Business Momentum v1.0 and does not authorize changes to source-domain contracts, Accounting semantics, platform authorization, or unrelated bounded contexts.

## 17. Founder Approval Record

The approved positions are:

- business-scoped, technology-neutral, read-only canonical Momentum access;
- consumers may read, present, and explain;
- consumers may not recalculate, mutate, override, score, rank, or reinterpret Momentum into an alternative result;
- AI may interpret/explain but has no authority;
- historical retrieval preserves canonical history;
- corrections create new assessments with predecessor lineage;
- existing platform authorization applies;
- historical and reconstruction artifacts remain distinct;
- canonical evidence and policy context remain preserved.

**Implementation authorization:** This artifact records approved read-contract semantics and does not authorize implementation outside the approved ES-004 scope.
