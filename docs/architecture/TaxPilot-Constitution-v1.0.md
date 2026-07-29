# TaxPilot Architecture Constitution

| Field | Value |
|---|---|
| Version | 1.0.0 |
| Status | Approved |
| Owner | TaxPilot Architecture Governance |
| Custodian | TaxPilot Architecture Governance |
| Approving authority | TaxPilot Architecture Governance Council |
| Effective date | 2026-07-26 |

## Purpose

This Constitution defines the enduring architectural principles that govern the
TaxPilot platform. It establishes the constraints within which product,
architecture, engineering, data, security, and artificial intelligence decisions
MUST be made.

## Scope

This Constitution applies to every TaxPilot product surface, service, module,
data store, integration, automation, artificial intelligence capability, and
engineering deliverable. It governs both human-authored and machine-generated
changes.

This document defines principles, not implementation. Technology selections,
component designs, business rules, delivery plans, and operational procedures
belong in the documents identified in [Governance](#12-governance).

## Audience

This document is normative for product leaders, architects, engineers, security
and compliance personnel, data and AI practitioners, reviewers, operators, and
AI coding agents contributing to TaxPilot.

## Table of Contents

1. [Normative Language](#1-normative-language)
2. [Definitions / Glossary](#2-definitions--glossary)
3. [Manifesto](#3-manifesto)
4. [Vision](#4-vision)
5. [Mission](#5-mission)
6. [Foundational Principles](#6-foundational-principles)
7. [Business Architecture Principles](#7-business-architecture-principles)
8. [AI Principles](#8-ai-principles)
9. [Platform and Engineering Principles](#9-platform-and-engineering-principles)
10. [API Principles](#10-api-principles)
11. [Security and Privacy Principles](#11-security-and-privacy-principles)
12. [Governance](#12-governance)
13. [References](#13-references)
14. [Version History](#14-version-history)

## 1. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** express requirement levels in this document.

- **MUST**, **MUST NOT**, **SHALL**, and **SHALL NOT** state mandatory
  requirements.
- **SHOULD** and **SHOULD NOT** state expectations from which a deviation is
  permitted only when its rationale and consequences are documented.
- **MAY** states an optional practice.

## 2. Definitions / Glossary

| Term | Constitutional meaning |
|---|---|
| Approved | Formally ratified by the Approving Authority, or through a process that authority has explicitly delegated. |
| Approving Authority | The TaxPilot Architecture Governance Council, which ratifies this Constitution and its amendments and resolves constitutional disputes. |
| Consequential Business Action | An action that creates, changes, finalizes, reverses, discloses, or deletes a Material Business Fact; changes access to one; or makes an external commitment based on one. |
| Constitution Custodian | TaxPilot Architecture Governance, which maintains the authoritative document, coordinates review, records approvals, and publishes approved versions. The Custodian cannot approve an amendment unless separately authorized as the Approving Authority. |
| Critical Operation | An operation whose failure or incorrect execution could materially compromise authoritative records, statutory obligations, access control, tenant isolation, or an external business commitment. |
| Material Business Fact | Information that affects a financial position, statutory obligation, inventory position, access entitlement, external commitment, or authoritative business report. |
| Material Workflow | A workflow that creates, changes, approves, finalizes, reverses, communicates, or coordinates a Material Business Fact. |
| Trusted Platform Authority | The domain or platform capability assigned authority for a fact, rule, decision, or control by approved platform or domain architecture. |

Where this Constitution uses **material**, **consequential**, **critical**,
**approved**, or **authoritative**, the term MUST be interpreted according to
this section and the ownership assigned by approved architecture.

## 3. Manifesto

TaxPilot is an AI-powered Business Operating System for Indian businesses. It
unifies the records, workflows, controls, and intelligence required to operate a
business while preserving the authority of financial records, statutory rules,
and accountable human decisions.

TaxPilot SHALL favor:

- correctness over convenience in financial and compliance outcomes;
- explicit domain ownership over shared mutable logic;
- traceable decisions over opaque automation;
- stable contracts over incidental coupling;
- safe evolution over disruptive replacement;
- secure, least-privilege access over implicit trust; and
- actionable intelligence over ungrounded prediction.

## 4. Vision

TaxPilot's vision is to provide Indian businesses with a dependable operating
system in which accounting, taxation, compliance, invoicing, purchases,
expenses, inventory, banking, reporting, and business intelligence work as a
coherent whole.

The platform SHALL enable a business to understand its operational and
financial state from consistent, explainable, and auditable information.

## 5. Mission

TaxPilot's mission is to reduce the effort and risk of running a business by:

1. maintaining trustworthy business and financial records;
2. coordinating workflows across business domains without erasing domain
   boundaries;
3. applying Indian tax and compliance rules deterministically;
4. providing timely, explainable intelligence and automation; and
5. preserving user control over consequential business actions.

## 6. Foundational Principles

### 6.1 Correctness is a product requirement

Financial, tax, compliance, inventory, and identity behavior MUST enforce their
approved invariants. The platform MUST reject an operation when required invariants
cannot be established. It MUST NOT fabricate, silently repair, or guess data to
make an invalid transaction appear valid.

### 6.2 Business records are authoritative and auditable

Every consequential business action MUST have an identifiable initiator,
effective time, outcome, and traceable relationship to the affected records.
Corrections to finalized or statutory records MUST preserve history. Destructive
replacement MUST NOT be used where an adjustment, reversal, or new version is
required for auditability.

### 6.3 One authority per business fact

Each material business fact, rule, and lifecycle MUST have one authoritative
domain owner. Other domains MAY consume that fact through a published contract
but MUST NOT independently redefine its meaning or maintain an ungoverned
competing source of truth.

### 6.4 Explicit state and deterministic transitions

Material workflows MUST use explicit states and validated transitions. The same
valid inputs, governing rules, and effective context SHOULD produce the same
business result. Hidden state transitions and implicit side effects MUST NOT be
used for consequential operations.

### 6.5 Evolution without loss of trust

Platform changes MUST preserve the integrity, readability, and provenance of
historical records. Breaking changes require an approved migration and consumer
transition plan. Compatibility mechanisms MAY be temporary and MUST have a
defined owner and retirement condition.

### 6.6 Evidence before assumption

System behavior, reports, recommendations, and compliance outcomes MUST be
derived from identified data and rules. When evidence is incomplete, the
platform MUST expose uncertainty or request resolution rather than present an
assumption as fact.

## 7. Business Architecture Principles

### 7.1 Domain-aligned organization

The platform SHALL be organized around cohesive business capabilities and
bounded contexts. A domain MUST own its vocabulary, invariants, lifecycle, and
authoritative records. Detailed boundaries and ownership are defined in the
[Domain Architecture](Domain-Architecture.md).

### 7.2 Business identity and tenancy

Business data MUST be associated with the business context that owns it. Access,
processing, reporting, and integration behavior MUST preserve tenant isolation.
Cross-business access MUST be explicit, authorized, and auditable.

### 7.3 Financial authority

Accounting records SHALL be the authority for posted financial effects.
Operational domains SHALL describe business events and retain their own source
documents; they MUST NOT bypass the accounting domain to create competing
ledger truth.

Monetary calculations MUST use explicit precision, rounding, currency, and tax
rules. Client-supplied totals MAY be accepted as input for comparison but MUST
NOT override authoritative server-side calculations.

### 7.4 Tax and compliance integrity

Tax classification, calculation, filing state, and statutory identifiers MUST be
governed by explicit, effective-dated rules where those rules can change over
time. Compliance output MUST be reproducible from retained source data, rule
context, and approved adjustments.

No intelligence or automation capability MAY silently override a statutory rule
or represent unverified data as filed, accepted, or compliant.

### 7.5 Separation of operational capabilities

Sales, purchases, expenses, inventory, banking, accounting, taxation,
compliance, documents, identity, reporting, and intelligence SHALL remain
separately accountable capabilities even where their workflows collaborate.
Shared user journeys MUST coordinate domain behavior through defined contracts;
they MUST NOT collapse domain ownership into a single undifferentiated model.

### 7.6 Events communicate completed facts

Domains SHOULD publish events for material facts that other domains need to
observe. An event MUST describe a fact that has occurred, not grant another
domain permission to mutate the publisher's records.

Cross-domain event communication MUST preserve fact ownership, traceability, and
the visibility of incomplete outcomes. Delivery and recovery semantics belong in
the [Platform Architecture](Platform-Architecture.md).

### 7.7 Business rules are governed artifacts

Detailed business rules and workflows MUST be specified in a Business Workflow
Specification. Architecture documents MUST NOT become a substitute for those
specifications. Implementation details MUST be defined in Engineering
Specifications, and significant architectural decisions MUST be recorded in
Architecture Decision Records.

## 8. AI Principles

### 8.1 AI augments accountable users

AI SHALL assist users with understanding, classification, extraction,
reconciliation, prediction, and recommended action. A user or explicitly
authorized deterministic policy MUST remain accountable for consequential
financial, statutory, security, or external actions.

### 8.2 Authority remains outside the model

An AI model MUST NOT be the system of record, the sole authority for a business
rule, or the final arbiter of a compliance outcome. Authoritative calculations,
permissions, workflow transitions, and validations MUST remain enforceable
without dependence on probabilistic model output.

### 8.3 Explainability and provenance

AI-derived output MUST be distinguishable from verified facts. Where output can
affect a business decision, the platform MUST retain or expose sufficient
provenance to identify relevant inputs, model or rule version, confidence or
uncertainty, and the reason for the recommendation.

### 8.4 Human review and reversibility

Material AI-proposed changes MUST be reviewable before commitment unless an
approved automation policy explicitly permits execution. Automated actions MUST
be bounded, observable, and reversible where the underlying business process
allows reversal.

### 8.5 Data protection and minimization

AI processing MUST follow the same authorization, tenant isolation, retention,
and confidentiality requirements as all other processing. Only the minimum data
required for the approved purpose MAY be disclosed to a model or provider.
Sensitive data MUST NOT be used for model training or improvement without an
explicitly approved legal, security, and product basis.

### 8.6 Safe failure

AI unavailability, low confidence, or invalid output MUST degrade to a safe and
understandable workflow. It MUST NOT prevent access to authoritative records or
corrupt a deterministic business process.

### 8.7 Continuous evaluation

Production AI capabilities MUST have defined quality, safety, and operational
measures appropriate to their risk. Material changes to models, prompts,
retrieval sources, or decision thresholds MUST be evaluated and versioned.

## 9. Platform and Engineering Principles

### 9.1 Layered responsibility

Business policy MUST remain independent of delivery mechanisms and technology
choices. The approved layer model and technology boundaries are defined in the
[Platform Architecture](Platform-Architecture.md).

### 9.2 Encapsulation and substitutability

Modules MUST expose intentional interfaces and MUST NOT depend on another
module's internal implementation. External capabilities SHOULD be replaceable
behind owned contracts when substitution is operationally or strategically
material.

### 9.3 Consistency and integrity

A Material Workflow MUST define its consistency expectations and MUST preserve
business invariants across domain boundaries. Incomplete or failed outcomes MUST
remain identifiable and recoverable.

### 9.4 Reliability is designed

Critical operations MUST define failure behavior, recovery behavior, and
protection against duplicate business effects. Degraded dependencies MUST NOT
silently weaken correctness or security controls. Implementation mechanisms are
defined in the Platform Architecture and Engineering Specifications.

### 9.5 Operational evidence preserves business context

The platform MUST produce operational evidence sufficient to diagnose failures
and reconstruct Consequential Business Actions. That evidence MUST preserve the
applicable business context while excluding secrets and unnecessary sensitive
data. Specific observability controls belong in the Platform Architecture and
Engineering Specifications.

### 9.6 Quality is continuously enforced

Changes MUST be subject to quality and security controls proportionate to their
risk. Those controls MUST protect domain invariants, authorization, financial
calculations, data evolution, and published contracts. Verification and release
mechanisms belong in the Engineering Charter and Coding Standards.

### 9.7 Simplicity and proportionality

Architecture MUST be no more complex than required by demonstrated business,
security, reliability, or scale needs. New infrastructure, abstractions, and
shared services require explicit ownership and justified lifecycle cost.

## 10. API Principles

### 10.1 Contract-first boundaries

Every internal or external API MUST have an owned, documented, and testable
contract. Contracts MUST define inputs, outputs, validation, errors,
authorization, idempotency where applicable, and compatibility expectations.

### 10.2 Domain semantics over storage semantics

APIs MUST express business concepts and lifecycle operations. They MUST NOT
expose persistence models as accidental public contracts or permit consumers to
bypass domain invariants.

### 10.3 Trusted platform authority

The platform MUST validate all API input regardless of its source. A Trusted
Platform Authority SHALL own calculated values, authorization decisions, and
state transitions assigned to it by approved architecture.

### 10.4 Consistent failure behavior

API failures MUST be represented through documented, stable, and safe contracts.
Internal details and secrets MUST NOT be exposed. Detailed error conventions
belong in the Coding Standards.

### 10.5 Compatibility and lifecycle

Breaking contract changes MUST be versioned or introduced through a governed
migration. Deprecation MUST identify affected consumers, a supported transition
path, and a retirement condition. Removal MUST NOT occur until the approved
condition is met.

## 11. Security and Privacy Principles

### 11.1 Secure by design and by default

Security and privacy requirements MUST be considered during design, not added
only after implementation. Defaults MUST minimize access, data exposure, and
unsafe configuration.

### 11.2 Explicit identity and least privilege

Every protected operation MUST authenticate its calling identity and authorize
the requested action in the applicable business context. Permissions MUST apply
least privilege, deny by default, and be enforced by a Trusted Platform
Authority.

### 11.3 Defense in depth

No single control SHALL be assumed infallible. Sensitive workflows SHOULD use
independent preventive, detective, and recovery controls proportional to risk.
Input validation, authorization, audit, encryption, and operational monitoring
MUST reinforce rather than replace one another.

### 11.4 Data lifecycle protection

Data MUST be classified, collected for an identified purpose, retained only as
required, and disposed of through an Approved process. Protection appropriate to
the data classification MUST apply throughout storage and transmission. Backups,
exports, logs, and derived data MUST receive protection consistent with their
source data.

### 11.5 Secrets and credentials

Secrets MUST NOT be embedded in source code, client-delivered artifacts, logs,
or documentation. Credentials MUST be scoped, protected throughout their
lifecycle, and capable of replacement. Detailed controls belong in the Coding
Standards and Platform Architecture.

### 11.6 Audit and incident readiness

Security-relevant and consequential business actions MUST generate tamper-
resistant audit evidence appropriate to their risk. The platform MUST support
detection, containment, investigation, recovery, and required notification of
security and privacy incidents.

### 11.7 Third-party responsibility

External services MUST be assessed according to the sensitivity and criticality
of the data and capability entrusted to them. Integrations MUST constrain data
sharing, permissions, failure impact, and provider access to the approved
purpose.

## 12. Governance

### 12.1 Authority and custodianship

The TaxPilot Architecture Governance Council is the Approving Authority for this
Constitution and all amendments. Approval requires a recorded decision of that
Council under the Constitution Change Policy.

TaxPilot Architecture Governance is the Constitution Custodian. It SHALL
maintain the authoritative copy, coordinate reviews, record approval evidence,
publish approved versions, and ensure that status and effective-date metadata
match the recorded decision.

No draft, including this version, is binding before approval. On approval, the
Approving Authority SHALL assign the effective date and the Custodian SHALL
record it in the metadata and version history.

### 12.2 Precedence

This Constitution is the highest-level architecture policy for TaxPilot. In the
event of conflict, the following order of precedence applies:

1. applicable law and binding regulatory obligations;
2. this Constitution;
3. approved platform and domain architecture;
4. accepted Architecture Decision Records;
5. approved Business Workflow Specifications;
6. approved Engineering Specifications; and
7. implementation and operational procedure.

A lower-level artifact MUST NOT silently contradict a higher-level artifact. A
conflict MUST be resolved by changing the lower-level artifact or initiating the
governed amendment process.

### 12.3 Required documentation path

| Change concern | Governing artifact |
|---|---|
| Platform-wide enduring principle | This Constitution |
| Amendment eligibility, approval, and versioning | [Constitution Change Policy](Constitution-Change-Policy.md) |
| Platform layers, interactions, and technology boundaries | [Platform Architecture](Platform-Architecture.md) |
| Domains, ownership, and integration boundaries | [Domain Architecture](Domain-Architecture.md) |
| Significant architectural choice and consequences | Architecture Decision Record |
| Detailed business rule or workflow | Business Workflow Specification |
| Implementable technical design and delivery plan | Engineering Specification |

### 12.4 Conformance

Every proposed material change MUST be assessed for conformance with this
Constitution. The proposer SHALL identify affected principles in the relevant
ADR, Business Workflow Specification, Engineering Specification, or pull
request.

Reviewers MUST reject a change that violates a mandatory principle unless an
approved constitutional amendment takes effect first. Schedule pressure,
implementation effort, or existing non-conforming behavior is not, by itself, a
basis for exemption.

### 12.5 Exceptions

This Constitution has no informal exceptions. A temporary deviation from a
**SHOULD** requirement MUST document its rationale, risk, accountable owner,
expiry or review date, and remediation path. A deviation from a **MUST** or
**SHALL** requirement requires a constitutional amendment.

### 12.6 Amendments

Amendments MUST follow the [Constitution Change
Policy](Constitution-Change-Policy.md). An amendment MUST be platform-wide and
principle-level; it MUST NOT be used to approve a single implementation choice
or bypass normal architecture review.

### 12.7 Pending normative documents

A referenced document that has not been approved is informative only. It becomes
normative when the Approving Authority or its explicitly delegated authority
records its approval and the Constitution Custodian publishes the approved
version. Approval of a referenced document MUST NOT alter this Constitution;
conflicts require resolution under [Precedence](#122-precedence) and, where
necessary, the amendment process.

Until the Constitution Change Policy is approved, the Approving Authority SHALL
use a recorded decision to ratify this initial Constitution. Subsequent
amendments MUST NOT proceed until that policy is approved.

## 13. References

### Normative references

- [Constitution Change Policy](Constitution-Change-Policy.md)
- [Platform Architecture](Platform-Architecture.md)
- [Domain Architecture](Domain-Architecture.md)
- [Engineering Charter](../engineering/Engineering-Charter.md)
- [ADR Template](../engineering/ADR-Template.md)
- [Engineering Specification Template](../engineering/Engineering-Specification-Template.md)
- [Business Workflow Specification Template](../bws/BWS-Template.md)

### Informative references

- [ADR-0015: Canonical catalog with optional capability profiles](../adr/0015-canonical-catalog-domain.md)
- [ADR-0016: Canonical Sales workflow with legacy compatibility](../adr/0016-canonical-sales-workflow.md)
- [ADR-0018: Canonical Sales Financial Rules Engine](../adr/0018-sales-financial-rules-engine.md)
- [ADR-0019: Advisory Sales Intelligence](../adr/0019-advisory-sales-intelligence.md)

## 14. Version History

| Version | Date | Status | Summary |
|---|---|---|---|
| 1.0.0 | 2026-07-26 | Approved | Initial TaxPilot Architecture Constitution ratified and effective. |
