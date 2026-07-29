# TaxPilot Domain Architecture

| Field | Value |
|---|---|
| Version | 1.0.0 |
| Status | Approved |
| Owner | TaxPilot Architecture Governance |
| Effective date | 2026-07-26 |

## Purpose

This document defines the business-capability ownership model for TaxPilot. It
identifies bounded contexts, assigns authority for business facts and
lifecycles, and establishes the contracts through which domains collaborate.

## Scope

This document governs domain boundaries across the TaxPilot platform, including
current modules, temporarily co-located capabilities, planned domains, shared
contracts, domain events, external-system translation boundaries, and future
domain evolution.

It defines **who owns business capabilities**. It does not define detailed
business rules, database schemas, API payloads, source-code organization,
technology choices, or deployment topology. Those concerns belong in Business
Workflow Specifications, Engineering Specifications, Coding Standards, ADRs,
and the [Platform Architecture](Platform-Architecture.md).

## Audience

This document is normative for product owners, domain experts, architects,
engineers, data and AI practitioners, technical reviewers, and AI coding agents
designing or changing TaxPilot capabilities.

## Table of Contents

1. [Normative Language](#1-normative-language)
2. [Domain-Driven Design Approach](#2-domain-driven-design-approach)
3. [Bounded Contexts](#3-bounded-contexts)
4. [Domain Ownership](#4-domain-ownership)
5. [Core Domains](#5-core-domains)
6. [Supporting Domains](#6-supporting-domains)
7. [Generic Platform Services](#7-generic-platform-services)
8. [Domain Interaction Rules](#8-domain-interaction-rules)
9. [Shared Contracts](#9-shared-contracts)
10. [Domain Events](#10-domain-events)
11. [Anti-Corruption Layers](#11-anti-corruption-layers)
12. [Data Ownership](#12-data-ownership)
13. [Future Domain Evolution](#13-future-domain-evolution)
14. [References](#14-references)
15. [Version History](#15-version-history)

## 1. Normative Language

The terms **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** have the meanings established by the [TaxPilot Architecture
Constitution](TaxPilot-Constitution-v1.0.md#1-normative-language).

Constitutional terms, including Material Business Fact, Material Workflow,
Consequential Business Action, Critical Operation, and Trusted Platform
Authority, retain their constitutional definitions.

## 2. Domain-Driven Design Approach

### 2.1 Capability alignment

TaxPilot SHALL organize business behavior by bounded context. A bounded context
defines one cohesive model, vocabulary, authority boundary, and set of published
contracts for a business capability.

A bounded context is a logical ownership boundary. It MAY be implemented inside
the modular monolith or deployed independently in accordance with the Platform
Architecture. Runtime placement MUST NOT alter domain ownership.

### 2.2 Domain model autonomy

Each bounded context MUST maintain the model required to enforce its own
invariants. The same real-world subject MAY have different representations in
different contexts when their meanings and responsibilities differ.

One context MUST NOT reuse another context's internal model as a shared mutable
domain model. Cross-context meaning MUST be communicated through an
owner-published contract.

### 2.3 Strategic classification

TaxPilot classifies capabilities as:

| Classification | Meaning |
|---|---|
| Core domain | A capability central to TaxPilot's trusted financial, statutory, or intelligence proposition and requiring platform-specific domain expertise |
| Supporting domain | A business capability required to operate the product but not itself a generic technical service |
| Generic platform service | A reusable technical capability that carries no independent business authority |

Classification guides investment and modeling depth. It does not establish
dependency direction or permit a core domain to override another context's
owned facts.

### 2.4 Context mapping

Context relationships SHALL use one of the following forms:

| Relationship | Use |
|---|---|
| Published contract | A consumer invokes an owner-defined application or API contract |
| Published event | An owner announces a committed business fact |
| Published read model | An owner exposes a stable, derived view for cross-context queries |
| Anti-corruption layer | A context translates an external or legacy model into its own language |
| Shared kernel | A deliberately minimal, jointly governed semantic type used by more than one context |

Shared kernels are exceptional. They MUST identify joint owners, compatibility
rules, and change approval. Shared infrastructure, tables, and source-code
utilities are not shared kernels.

## 3. Bounded Contexts

The following bounded contexts constitute the approved TaxPilot domain map.

| Bounded context | Classification | Owns | Explicitly does not own | Current placement |
|---|---|---|---|---|
| Identity and Access | Supporting | User identity, credentials, sessions, role and permission definitions, and role-to-permission mapping | Business membership, business-scoped role assignment, business records, or final domain authorization decisions | Identity module |
| Business Administration | Supporting | Business identity, legal and operating profile, membership, business-scoped role assignment, business settings, and declared tax profile | User credentials, domain authorization policy, GST calculation, filings, or ledger records | Business module |
| Catalog | Supporting | Canonical commercial identity of products and services, item lifecycle, product-or-service classification, and HSN/SAC assignment | GST legal interpretation, effective tax rates, tax determination, stock balances, pricing transactions, or invoice lines | Catalog module |
| Sales | Supporting | Customer records, sales invoices, invoice numbering, sales terms, and sales lifecycle | Payment allocation, ledger posting, stock mutation, GST filing, or document delivery | Sales module |
| Payments | Supporting | Inbound receipts, outbound payment instructions and disbursements, payment instruments as business records, allocations, settlement lifecycle, refunds, failures, and reversals | Invoice issuance, payable source-document lifecycle, external bank-statement truth, or ledger authority | Temporarily co-located behind legacy Sales APIs; independent target boundary |
| Purchases | Supporting | Supplier records, purchase invoices, and purchase lifecycle | Payment execution, stock mutation, input-tax filing, or ledger posting | Purchases module |
| Expenses | Supporting | Vendor records, expense records, classification within the expense workflow, and expense lifecycle | Payment instruction or allocation, tax authority, or ledger posting | Expenses module |
| Inventory | Supporting | Inventory capability profiles, warehouses, stock movements, stock balances, and inventory lifecycle | Canonical item identity, commercial invoice lifecycle, or accounting ledger | Inventory module |
| Accounting | Core | Chart of accounts, journal entries, posted financial effects, balances, trial balance, and financial statements | Operational source-document lifecycle, statutory filing acceptance, or payment-provider state | Accounting module |
| GST | Core | GST registrations, HSN/SAC reference semantics, effective GST rule interpretation, tax rates, and tax determination | Catalog item classification or assignment, source-transaction lifecycle, filing submission lifecycle, or accounting ledger | GST module |
| Compliance | Core | Statutory report preparation, validation, submission, acknowledgement, filing status, e-invoicing, and related regulatory workflow | Source transaction ownership, tax calculation authority, or ledger posting | Temporarily co-located in GST module; independent target boundary |
| Documents | Supporting | Source-document identity, storage lifecycle, extraction results, review decisions, and document automation state | Final authority for extracted business facts or target-domain lifecycle | Documents module |
| Banking | Supporting | Bank connections, bank accounts as integration records, imported bank transactions, bank-side execution evidence, matching, and reconciliation workflow | Bank-provider source truth, payment instruction, payment allocation, TaxPilot payment settlement lifecycle, or accounting ledger | Planned boundary |
| Reporting | Supporting | Cross-domain analytical definitions, reporting projections, freshness, and report delivery | Source-domain facts, journal authority, statutory filing status, or domain invariants | Planned boundary |
| Intelligence | Core | Advisory models, recommendation semantics, evidence, confidence, and intelligence evaluation lifecycle | Authority to mutate source-domain records, post financial effects, or determine compliance | Domain-owned contracts with currently embedded advisory capabilities |

### 3.1 Co-location and planned boundaries

Temporary co-location is an implementation state, not an ownership assignment.
The containing module MUST preserve the independent capability's contract and
model boundary. New behavior MUST target the owner identified in this document,
even when its code remains temporarily co-located.

A planned boundary is authoritative for ownership before a standalone module
exists. Interim behavior MUST be explicitly assigned by an ADR and MUST NOT
create a competing source of truth.

The bounded context remains the business owner. A host module is only the
**interim implementation steward**: it maintains isolation and routes access
through the bounded context's contract but cannot change its model or claim its
facts. Every temporary or planned placement MUST be governed by this document
and an accepted ADR or Engineering Specification before material implementation
is added.

| Boundary | Interim implementation stewardship | Permitted interim responsibility | Migration condition |
|---|---|---|---|
| Payments | Sales module for existing legacy payment APIs | Preserve existing inbound-payment compatibility behind a Payments-owned contract | Establish a distinct Payments module before adding outbound payments, non-Sales allocations, settlement orchestration, or a new canonical payment API; retire legacy placement after consumers migrate |
| Compliance | GST module for current GST-related compliance behavior | Host GST-related submission and e-invoicing behavior behind a Compliance-owned lifecycle contract | Establish a distinct Compliance module before adding a non-GST regime or a separately deployed compliance API or worker; migrate existing behavior when the standalone contract becomes authoritative |
| Banking | No interim host | No domain may persist Banking-owned facts outside an explicitly approved adapter boundary | Establish the Banking module before the first production bank connection, imported bank-transaction authority, matching, or reconciliation workflow |
| Reporting | Source domains may expose owner-published read models; no interim Reporting owner exists | Produce domain-local reports without creating a cross-domain authority | Establish the Reporting module before persisting a cross-domain projection or publishing a cross-domain analytical definition |
| Intelligence | The requesting domain may host an adapter to an Intelligence-owned advisory contract; Sales is the current accepted instance | Evaluate domain-scoped advice without mutating source facts or creating a shared intelligence store | Establish a distinct Intelligence module before cross-domain evaluation, durable recommendation storage, shared model governance, or independent scaling |

Crossing a migration condition requires an accepted ADR and Engineering
Specification. Until migration completes, both legacy and target contracts MUST
identify the same bounded-context owner, and no dual authority is permitted.

### 3.2 Authoritative context relationship map

The following table is the authoritative context map. A relationship not listed
here MUST be added through an accepted ADR and reflected in this document before
it becomes a supported cross-context dependency. Contract and event schemas
remain defined in BWS documents and Engineering Specifications.

| Provider or publisher | Consumer | Permitted relationship | Purpose |
|---|---|---|---|
| Identity and Access | Business Administration; Catalog; Sales; Payments; Purchases; Expenses; Inventory; Accounting; GST; Compliance; Documents; Banking; Reporting; Intelligence | Published identity and permission contract | Authenticate the principal and resolve role and permission definitions |
| Business Administration | Identity and Access; Catalog; Sales; Payments; Purchases; Expenses; Inventory; Accounting; GST; Compliance; Documents; Banking; Reporting; Intelligence | Published business-context contract and business or membership events | Establish tenant identity, active membership, business-scoped role assignment, settings, and declared profile |
| Catalog | Sales; Purchases; Expenses; Inventory; GST | Published catalog contract and catalog events | Provide item identity, product-or-service classification, and HSN/SAC assignment |
| Sales | Payments; Accounting; Inventory; GST; Compliance; Reporting; Intelligence | Sales application contract and invoice events | Communicate authoritative sales and invoice facts |
| Payments | Sales; Purchases; Expenses; Accounting; Banking; Reporting; Intelligence | Payments application contract and payment events | Communicate receipt, disbursement, allocation, settlement, refund, failure, and reversal facts |
| Purchases | Payments; Accounting; Inventory; GST; Compliance; Reporting; Intelligence | Purchases application contract and purchase events | Communicate authoritative supplier and purchase-invoice facts |
| Expenses | Payments; Accounting; GST; Compliance; Reporting; Intelligence | Expenses application contract and expense events | Communicate authoritative vendor and expense facts |
| Inventory | Accounting; Reporting; Intelligence | Inventory contract and inventory events | Communicate stock movement and stock-position outcomes |
| Accounting | Reporting; Intelligence | Accounting read contracts and accounting events | Provide posted financial outcomes and financial statements |
| GST | Sales; Purchases; Expenses; Compliance; Reporting; Intelligence | GST determination contract and GST events | Provide effective GST interpretation and authoritative tax determinations |
| Compliance | Sales; Purchases; Expenses; GST; Reporting; Intelligence | Compliance contract and submission events | Provide statutory preparation, submission, acknowledgement, and filing outcomes |
| Documents | Sales; Purchases; Expenses; Reporting | Document contract and extraction or review events | Provide reviewed document evidence to currently approved target contexts |
| Banking | Payments; Accounting; Reporting; Intelligence | Banking contract and banking events | Provide imported bank evidence, matching, and reconciliation outcomes |
| Intelligence | Sales | Advisory contract and advisory events | Provide the currently accepted Sales advisory capability |

The provider or publisher retains authority for every relationship. A consumer
MUST NOT infer additional access, reverse direction, or authority from its
presence in this map.

## 4. Domain Ownership

### 4.1 Ownership rule

For every Material Business Fact, one bounded context SHALL be the Trusted
Platform Authority. The owner controls:

- the fact's canonical meaning and vocabulary;
- creation and identity rules;
- validation and invariants;
- lifecycle and permitted transitions;
- authoritative persistence;
- correction, reversal, and retention behavior;
- published contracts and events; and
- compatibility and deprecation decisions.

### 4.2 Consumer responsibility

A consuming context MAY retain a stable identifier, an explicitly authorized
historical snapshot, or a derived projection. It MUST identify the owning
context and MUST NOT present its copy as current authority.

A consumer MUST NOT modify an owner's data directly, infer an unpublished state
transition, or expand the meaning of a contract beyond the owner's definition.

### 4.3 Collaborative workflows

A workflow spanning contexts has no implicit super-domain. Each participant
remains authoritative for its own outcome. The initiating context coordinates
the user-visible process but MUST NOT claim that downstream accounting,
inventory, payment, tax, compliance, banking, or delivery outcomes succeeded
until their owners confirm them.

### 4.4 Ownership conflict

When two contexts appear to own the same fact, new implementation MUST pause at
the architecture boundary. The conflict MUST be resolved in this document or by
an accepted ADR consistent with it before either context creates a competing
authority.

## 5. Core Domains

### 5.1 Accounting

Accounting is authoritative for posted financial effects. Operational contexts
publish or submit evidence of business transactions; Accounting determines and
records their ledger representation under approved accounting rules.

Accounting owns financial statements derived from the ledger. Reporting MAY
present those statements or combine them with operational projections but MUST
NOT recalculate a competing ledger truth.

### 5.2 GST

GST is authoritative for GST registrations, applicable GST rule interpretation,
HSN/SAC reference semantics and effective validity, tax rates, supply rules, and
deterministic tax determination. It consumes business, Catalog assignment,
party, and transaction context through published contracts.

GST does not own whether a Catalog item is a product or service, the HSN/SAC code
assigned to that item, or the source transaction lifecycle. Catalog remains
authoritative for the current item assignment.

The source transaction context owns the immutable historical snapshot recorded
on its transaction. That snapshot MUST preserve the product-or-service
classification, assigned HSN/SAC code, GST determination, and effective rule
context required by its BWS. Snapshot ownership preserves transaction history;
it does not make the source context authoritative for current Catalog data or
GST policy.

### 5.3 Compliance

Compliance is authoritative for statutory preparation, validation, submission,
provider acknowledgement, rejection, amendment, and filing lifecycle. It
consumes committed facts and tax results from their owners.

Compliance MUST distinguish prepared, submitted, accepted, rejected, and filed
states. It MUST NOT treat transport success or AI output as statutory
acceptance.

### 5.4 Intelligence

Intelligence is authoritative for recommendation definitions, evaluations,
confidence, explanations, and advisory lifecycle. It consumes authorized facts
or projections without acquiring ownership of them.

Intelligence MUST remain advisory unless an approved BWS assigns an explicit,
bounded automation policy. The affected domain remains authoritative for every
committed business action.

## 6. Supporting Domains

### 6.1 Identity and Access

Identity and Access establishes who a user is and defines authentication,
session, role, permission, and role-to-permission concepts. It is authoritative
for identity validity and the meaning of platform permission identifiers. It
MUST NOT assign business membership or make the final authorization decision for
a domain operation.

### 6.2 Business Administration

Business Administration owns the legal and operating identity of a TaxPilot
tenant, its membership, business-scoped role assignments, membership suspension
and revocation, settings, and declared tax profile. It is authoritative for
whether an authenticated principal is an active member of a business and which
roles that membership carries. It MUST NOT define the domain operation protected
by a permission.

Other contexts MAY consume Business Administration facts but MUST retain
historical snapshots when later changes must not alter finalized records.

### 6.2.1 Effective authorization

The bounded context that owns the requested business operation is the Trusted
Platform Authority for the effective authorization decision. It MUST evaluate:

1. the authenticated principal attested by Identity and Access;
2. active business membership and business-scoped role assignments attested by
   Business Administration; and
3. the permission, resource ownership, record state, and domain policy required
   by the owning context.

A denial or unavailable prerequisite from any authority MUST result in denial.
Identity and Access or Business Administration MAY provide reusable enforcement
capabilities, but that technical placement does not transfer ownership of the
domain authorization decision.

### 6.3 Catalog

Catalog provides the canonical commercial identity of goods and services.
Inventory adds an optional inventory capability without redefining catalog
identity.

Catalog owns whether an item is a product or service and the HSN or SAC code
assigned to it. Catalog validates assignment shape and product-versus-service
compatibility. GST owns the legal meaning and effective validity of HSN/SAC
reference data for GST, the applicable rates and rules, and the resulting tax
determination. A Catalog assignment is an input to GST; it is not a tax
determination.

### 6.4 Sales

Sales owns customers, invoice identity, invoice terms, authoritative sales
calculations assigned to it, and invoice lifecycle. Issuance communicates a
completed sales fact; it does not itself post ledger entries, allocate payments,
move stock, file statutory data, or deliver documents.

### 6.5 Payments

Payments owns inbound receipt and outbound disbursement instructions, execution
state within TaxPilot, allocation to receivable and payable references,
settlement state, refund, failure, cancellation, and reversal lifecycle. It may
allocate value to a sales invoice, purchase, expense, or another payable or
receivable reference, but the referenced context retains ownership of its source
document and payable or receivable basis.

Sales delegates receipt allocation and refund execution to Payments. Purchases
and Expenses delegate outbound payment instruction, disbursement tracking, and
allocation to Payments. They MUST NOT maintain a competing payment lifecycle.

Banking owns imported bank evidence, bank-side execution evidence, matching, and
reconciliation. Payments owns TaxPilot's payment settlement conclusion and
consumes Banking evidence through its published contract. Accounting owns the
posted financial effect. These confirmations MAY update Payments state or
projections without transferring source ownership.

### 6.6 Purchases

Purchases owns supplier and purchase-invoice lifecycle. It communicates
confirmed purchasing facts to Accounting, Inventory, GST, Compliance, Payments,
and Reporting through owned contracts or events. It delegates outbound payment
instruction, execution tracking, allocation, settlement, and reversal to
Payments.

### 6.7 Expenses

Expenses owns vendor and expense lifecycle. It distinguishes the operational
expense record from payment instruction, allocation, settlement, tax authority,
and ledger posting. It delegates its payment lifecycle to Payments.

### 6.8 Inventory

Inventory owns where and why stock changes and the resulting stock position.
It references Catalog identity and consumes committed operational facts. It MUST
NOT modify sales, purchase, or catalog records to reconcile inventory state.

### 6.9 Documents

Documents owns uploaded and generated document artifacts, extraction evidence,
review state, and automation progress. Extracted values remain proposed data
until the target domain validates and accepts them through its own contract.

### 6.10 Banking

Banking owns provider connections, imported statement records, matching, and
reconciliation workflow. A bank remains authoritative for its external
statement; Banking owns TaxPilot's accepted representation and reconciliation
state. Banking communicates execution and settlement evidence to Payments but
does not own the payment instruction, allocation, or TaxPilot payment lifecycle.
Accounting remains authoritative for ledger effects.

### 6.11 Reporting

Reporting owns governed cross-domain projections, report definitions, freshness,
and delivery. A report MUST identify its authoritative sources and MUST preserve
the distinction between operational, accounting, tax, and compliance facts.

Reporting MUST NOT become a write path into source contexts or a competing
system of record.

## 7. Generic Platform Services

Generic platform services are defined technically in the [Platform
Architecture](Platform-Architecture.md#6-shared-platform-services). They include
configuration, database infrastructure, cache and coordination, event delivery,
background execution, document storage, provider integration, API framework,
operational telemetry, time, and identifier capabilities.

These services:

- MUST NOT own Material Business Facts;
- MUST NOT contain domain-specific lifecycle or policy;
- MUST operate through contracts owned by the relevant domain or platform
  capability; and
- MAY carry domain context only for delivery, isolation, security, or
  observability.

Document storage is a generic technical service; the Documents bounded context
owns document business identity and lifecycle. Event delivery is a generic
technical service; publishing domains own event meaning. Background execution
is a generic technical service; initiating domains own work purpose and business
outcome.

## 8. Domain Interaction Rules

### 8.1 Permitted interactions

Contexts MAY interact through:

1. a synchronous owner-published application contract;
2. a versioned API contract;
3. a committed domain or integration event;
4. an owner-published projection or stable read model; or
5. an anti-corruption layer over an external or legacy contract.

### 8.2 Prohibited interactions

A context MUST NOT:

- read or mutate another context's internal persistence;
- depend on another context's internal classes or undocumented behavior;
- reuse another context's repository as its own data access path;
- publish an event on behalf of the context that owns the fact;
- treat a cache, report, AI output, or external transport response as domain
  authority; or
- coordinate a cross-domain workflow by bypassing participant contracts.

### 8.3 Synchronous interaction

Synchronous interaction SHOULD be limited to information or decisions required
to complete the caller's current operation. The provider retains ownership of
the result. Cyclic synchronous dependencies are prohibited and MUST be resolved
by changing ownership, using an event, or introducing an explicit coordination
boundary.

### 8.4 Asynchronous interaction

Asynchronous interaction communicates committed facts or initiates independently
owned work. The consumer controls its own transaction and failure handling. A
publisher MUST expose pending downstream outcomes when they are material to the
workflow.

Delivery guarantees and background execution boundaries are defined in the
[Platform Architecture](Platform-Architecture.md#8-event-driven-communication).

### 8.5 Cross-domain coordination

An application coordinator MAY sequence multiple context contracts. It MUST
remain free of participant-owned business rules and MUST represent partial
completion honestly. A coordinator is not a new source of truth.

## 9. Shared Contracts

### 9.1 Contract ownership

Every shared contract MUST have exactly one owning context or an explicitly
governed joint owner. The owner defines semantics, validation, versioning,
compatibility, and retirement.

### 9.2 Contract categories

| Contract | Intended use | Authority behavior |
|---|---|---|
| Application contract | Synchronous interaction inside an approved application boundary | Owner evaluates the request and returns its authoritative result |
| API contract | Interaction across client, runtime, or external boundaries | Owner exposes stable transport semantics without exposing internal models |
| Event contract | Notification of a committed fact | Publisher owns meaning; consumer owns reaction |
| Read-model contract | Cross-context query or reporting | Owner defines source, schema, freshness, and lifecycle |
| Snapshot contract | Historical facts embedded in another context's finalized record | Consumer owns the snapshot record; source domain owns the original meaning |

### 9.3 Shared semantic types

Stable identifiers, monetary values, currency codes, time values, tax
classification references, and business-context references MAY use shared
semantic contracts where consistency is required.

A shared semantic type MUST remain behaviorally minimal. Domain-specific rules
MUST remain with the owning context and MUST NOT accumulate in a generic shared
model.

### 9.4 Contract change

Contract change MUST preserve compatibility or follow a governed migration and
deprecation path. A consumer MUST NOT infer compatibility from shared deployment
or database access.

## 10. Domain Events

### 10.1 Ownership and publication

Only the context that owns a fact MAY publish its domain event. An event becomes
publishable only after the authoritative change commits, as defined by the
[Platform Architecture](Platform-Architecture.md#83-transactional-relationship).

### 10.2 Event content

A domain event contract MUST identify:

- the publishing context;
- event identity and type;
- aggregate or business-fact identity;
- business and tenant context where the fact is business-scoped;
- occurrence time;
- contract version; and
- the minimum fact data required by approved consumers.

An event SHOULD carry stable facts, not an internal domain object or a complete
copy of the publisher's record.

### 10.3 Principal event relationships

The following table identifies architectural relationships, not exhaustive event
schemas or workflow rules.

| Publishing context | Committed fact category | Principal consumers |
|---|---|---|
| Business Administration | Business or membership lifecycle changed | Identity and Access, Catalog, Sales, Payments, Purchases, Expenses, Inventory, Accounting, GST, Compliance, Documents, Banking, Reporting, Intelligence |
| Catalog | Catalog item or classification assignment changed | Sales, Purchases, Expenses, Inventory, GST |
| Sales | Sales invoice lifecycle changed | Payments, Accounting, Inventory, GST, Compliance, Reporting, Intelligence |
| Payments | Receipt, disbursement, allocation, settlement, refund, failure, or reversal lifecycle changed | Sales, Purchases, Expenses, Accounting, Banking, Reporting, Intelligence |
| Purchases | Purchase invoice lifecycle changed | Payments, Accounting, Inventory, GST, Compliance, Reporting, Intelligence |
| Expenses | Expense lifecycle changed | Payments, Accounting, GST, Compliance, Reporting, Intelligence |
| Inventory | Stock movement or balance outcome committed | Accounting, Reporting, Intelligence |
| Accounting | Journal or accounting-period outcome committed | Reporting, Intelligence |
| GST | Tax determination or registration state changed | Sales, Purchases, Expenses, Compliance, Reporting, Intelligence |
| Compliance | Submission or filing lifecycle changed | Sales, Purchases, Expenses, GST, Reporting, Intelligence |
| Documents | Extraction or review lifecycle changed | Sales, Purchases, Expenses, Reporting |
| Banking | Import, match, or reconciliation lifecycle changed | Payments, Accounting, Reporting, Intelligence |
| Intelligence | Sales advisory evaluation completed | Sales |

### 10.4 Consumer autonomy

Consumers MUST decide their own reaction under their owned rules. A consumer
MUST NOT use an event to mutate the publisher's records. A failed reaction MUST
remain attributable to the consumer and MUST NOT reinterpret the publisher's
committed fact.

## 11. Anti-Corruption Layers

### 11.1 Purpose

An anti-corruption layer translates between an external or legacy model and the
language of a TaxPilot bounded context. It prevents provider terminology,
identifier schemes, lifecycle assumptions, and data quality from contaminating
the owning domain model.

### 11.2 Required boundaries

Anti-corruption layers MUST protect TaxPilot domains from:

| Boundary | Translation responsibility |
|---|---|
| Statutory systems | Provider payloads, acknowledgement states, error semantics, and statutory identifiers into Compliance or GST language |
| Banking providers | Account, transaction, consent, synchronization, and reconciliation representations into Banking language |
| AI and OCR providers | Probabilistic or extracted output into proposed, validated domain input |
| Communication and document providers | Delivery and rendering states into Documents or the initiating domain's language |
| Legacy TaxPilot APIs and data | Transitional schemas and lifecycles into the approved bounded-context model |

### 11.3 Authority

Translation does not confer trust. Translated input MUST still pass the owning
context's validation and authorization. An anti-corruption layer MUST NOT make
business decisions that belong to the domain.

### 11.4 Legacy retirement

A legacy anti-corruption layer MUST identify its owner, supported consumers,
migration path, and retirement condition. New consumers SHOULD use the approved
domain contract rather than extend a legacy boundary.

## 12. Data Ownership

### 12.1 Authoritative data classes

| Data class | Authoritative owner |
|---|---|
| User credentials, sessions, roles, permission definitions, and role-to-permission mapping | Identity and Access |
| Business identity, membership, business-scoped role assignments, settings, and declared tax profile | Business Administration |
| Product and service commercial identity, product-or-service classification, and current HSN/SAC assignment | Catalog |
| Customer and sales invoice records, including required historical catalog and tax snapshots | Sales |
| Inbound receipts, outbound disbursements, allocations, settlement, refunds, failures, and reversals | Payments |
| Supplier and purchase invoice records, including required historical catalog and tax snapshots | Purchases |
| Vendor and expense records, including required historical classification and tax snapshots | Expenses |
| Warehouses, stock movements, and stock balances | Inventory |
| Journal, account balance, trial balance, and financial statements | Accounting |
| GST registrations, HSN/SAC reference semantics and effective validity, rates, rules, and tax determinations | GST |
| Statutory submissions, acknowledgements, and filing lifecycle | Compliance |
| Documents, extraction evidence, and review decisions | Documents |
| Imported bank records, matches, and reconciliation state | Banking |
| Cross-domain analytical projections and report definitions | Reporting |
| Recommendations, evidence, confidence, and advisory lifecycle | Intelligence |

### 12.2 References and snapshots

A context MAY store another context's stable identifier. It MAY store a snapshot
when the snapshot is required to preserve the historical meaning of a finalized
record. The snapshot MUST identify its source and MUST NOT be used as an
uncontrolled substitute for current authoritative data.

For a finalized transaction, its source context owns the historical snapshot of
Catalog classification and HSN/SAC assignment and the GST determination used at
that time. Catalog remains authoritative for the current item assignment, and
GST remains authoritative for the governing tax interpretation and
determination rules.

### 12.3 Projections

A cross-domain projection MUST identify its owning context, source contracts,
freshness, rebuild strategy, and authority limitations. Source contexts remain
authoritative. A projection MUST be replaceable from its published sources
unless an approved retention requirement makes the projection itself a governed
historical record.

### 12.4 Physical co-location

Physical co-location in PostgreSQL does not create shared ownership. Each
context's internal persistence remains private. Cross-context access MUST use an
owner-published contract, projection, or stable read model as defined by the
Platform Architecture.

## 13. Future Domain Evolution

### 13.1 Adding a bounded context

A proposed bounded context MUST identify:

- the business capability and vocabulary it owns;
- the Material Business Facts and lifecycles for which it is authoritative;
- facts owned elsewhere that it consumes;
- published contracts and events;
- data migration and compatibility boundaries;
- classification as core or supporting; and
- relationships to existing contexts.

It MUST NOT be introduced solely to group technical utilities or mirror an
organizational team.

### 13.2 Splitting or merging contexts

A split, merge, or ownership transfer requires an accepted ADR and an update to
this document. The change MUST preserve historical provenance, contract
compatibility, tenant isolation, and a single authority throughout migration.

### 13.3 Independent deployment

Extracting a context from the modular monolith changes runtime placement, not
business ownership. Extraction MUST meet the Platform Architecture requirements
for contracts, consistency, event delivery, security, observability, migration,
and operational ownership.

### 13.4 Planned boundaries

Payments, Compliance, Banking, Reporting, and Intelligence MAY evolve into
separately implemented or deployed modules. Until then, their identified owners
and anti-corruption boundaries remain binding. Temporary implementation MUST NOT
make the host module authoritative for their facts. Interim stewardship and the
mandatory migration conditions are defined in
[Co-location and planned boundaries](#31-co-location-and-planned-boundaries).

### 13.5 Context review

Domain boundaries SHOULD be reviewed when repeated translation, cyclic
dependencies, duplicated rules, competing facts, or coordinated changes show
that ownership is unclear. Such evidence triggers architecture review; it does
not authorize an implementation-level boundary change.

## 14. References

### Normative references

- [TaxPilot Architecture Constitution v1.0](TaxPilot-Constitution-v1.0.md)
- [TaxPilot Platform Architecture v1.0](Platform-Architecture.md)

### Accepted architecture decisions

- [ADR-0015: Canonical catalog with optional capability profiles](../adr/0015-canonical-catalog-domain.md)
- [ADR-0016: Canonical Sales workflow with legacy compatibility](../adr/0016-canonical-sales-workflow.md)
- [ADR-0018: Canonical Sales Financial Rules Engine](../adr/0018-sales-financial-rules-engine.md)
- [ADR-0019: Advisory Sales Intelligence](../adr/0019-advisory-sales-intelligence.md)

### Related governance documents

- [Constitution Change Policy](Constitution-Change-Policy.md)
- [Engineering Charter](../engineering/Engineering-Charter.md)
- [Business Workflow Specification Template](../bws/BWS-Template.md)
- [Engineering Specification Template](../engineering/Engineering-Specification-Template.md)

References that are not yet approved are informative until approved under the
governance rules established by the Constitution.

## 15. Version History

| Version | Date | Status | Summary |
|---|---|---|---|
| 1.0.0 | 2026-07-26 | Approved | Initial TaxPilot Domain Architecture ratified and effective. |
