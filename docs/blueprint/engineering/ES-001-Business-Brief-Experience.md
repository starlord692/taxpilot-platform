# ES-001 â€” Business Brief Experience

| Attribute | Value |
|---|---|
| Version | 1.0 |
| Status | Approved |
| Owner | Engineering |
| Last Updated | 2026-08-04 |
| Authority | Approved Tier 1 Business Knowledge Foundation |

## 1. Purpose

This Engineering Specification translates the approved Business Brief definition into implementable requirements. It specifies how the platform must assemble, present, explain, and protect the Business Brief experience without redefining any business concept.

The following Knowledge Packs remain authoritative for all business meaning:

- KP-001 â€” Business DNA
- KP-002 â€” Business Health
- KP-003 â€” Business Confidence
- KP-004 â€” Business Momentum
- KP-005 â€” Business Brief

Where this specification conflicts with an approved Knowledge Pack, the Knowledge Pack prevails.

## 2. Scope

This specification covers the Business Brief experience as the delivery of a coherent, point-in-time business narrative to an authorized owner.

It includes:

- retrieval and integration of approved context, deterministic business understanding, canonical signals, material activity, priorities, opportunities, and risks;
- composition of an explainable Business Brief narrative;
- presentation of source-assessment context and material limitations;
- AI-assisted explanation and recommendation within approved authority; and
- high-level integration, event, security, audit, and quality requirements.

It excludes the canonical definition or calculation of any source concept, detailed operational workflows, and technical design artifacts listed in Section 16.

## 3. Traceability Matrix

| ES Requirement Area | Authoritative Source | Trace |
|---|---|---|
| Point-in-time narrative | KP-005 â€” Business Brief | Â§Â§ 3, 6, 14, 17 |
| Owner clarity and reduced uncertainty | KP-005 â€” Business Brief | Â§Â§ 2, 5, 14, 15 |
| Contextual relevance | KP-001 â€” Business DNA | Â§Â§ 3, 6, 14, 17 |
| Current-condition context | KP-002 â€” Business Health | Â§Â§ 3, 11, 14, 17 |
| Reliability and limitations | KP-003 â€” Business Confidence | Â§Â§ 3, 11, 14, 17 |
| Direction and rate context | KP-004 â€” Business Momentum | Â§Â§ 3, 11, 14, 17 |
| Deterministic truth and AI boundaries | KP-002, KP-003, KP-004, KP-005 | AI Rules and Engineering Rules in each applicable pack |
| Owner approval and control | KP-005 â€” Business Brief | Â§Â§ 14, 15, 16, 17 |
| High-level data and integration needs | KP-005 â€” Business Brief | Â§Â§ 10, 12, 19, 23 |

## 4. User Journey

1. An authorized owner requests the Business Brief for the current business context. [Trace: KP-005 Â§18; KP-005 Â§17]
2. The platform identifies the relevant point in time and collects the approved inputs for the narrative. [Trace: KP-005 Â§Â§3, 10, 17]
3. The platform presents a concise narrative that explains material current understanding, rather than a disconnected collection of data. [Trace: KP-005 Â§Â§2, 3, 9, 14]
4. The owner can understand current Business Health, Business Momentum, and Business Confidence as distinct source signals, without the Brief redefining them. [Trace: KP-005 Â§Â§6, 14, 15; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14]
5. The owner can identify material activity, priorities, opportunities, and risks relevant to the business. [Trace: KP-005 Â§Â§5, 10, 11, 15]
6. The owner can request an explanation of a material statement or recommendation. [Trace: KP-005 Â§Â§14, 16, 18]
7. The platform explains the relevant deterministic evidence, approved context, and material limitations without making a decision or executing a consequential action. [Trace: KP-005 Â§16; KP-003 Â§Â§14, 16; KP-002 Â§16; KP-004 Â§16]
8. The owner may choose to continue into an appropriate downstream experience or take an action requiring approval; the Business Brief itself does not execute the action. [Trace: KP-005 Â§Â§14, 15, 18]

## 5. Functional Requirements

| ID | Requirement | Trace |
|---|---|---|
| FR-001 | The system shall produce a Business Brief as a coherent business narrative for a defined point in time. | KP-005 Â§Â§3, 11, 14 |
| FR-002 | The system shall integrate only relevant approved context, deterministic business understanding, canonical signals, material activity, priorities, opportunities, and risks into the narrative. | KP-005 Â§Â§10, 14, 15; KP-001 Â§14 |
| FR-003 | The system shall preserve the independent meaning of Business DNA, Business Health, Business Momentum, and Business Confidence when using them as inputs. | KP-005 Â§Â§6, 14, 17; KP-001 Â§14; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14 |
| FR-004 | The system shall make material changes, current meaning, relevant attention items, opportunities, risks, and recommendations understandable to the owner. | KP-005 Â§Â§5, 11, 15 |
| FR-005 | The system shall provide an explanation for every recommendation presented through the Business Brief. | KP-005 Â§Â§14, 15, 16 |
| FR-006 | The system shall identify material limitations in available understanding where they affect the reliability of the narrative or a material explanation. | KP-005 Â§Â§9, 15; KP-003 Â§Â§3, 11, 14 |
| FR-007 | The system shall present Business Health as current condition, Business Momentum as observed direction and rate, and Business Confidence as reliability of understanding. | KP-005 Â§Â§6, 15; KP-002 Â§3; KP-003 Â§3; KP-004 Â§3 |
| FR-008 | The system shall not substitute a dashboard, report, widget collection, chat interaction, or KPI page for the Business Brief narrative. | KP-005 Â§Â§3, 14, 17, 21 |
| FR-009 | The system shall not calculate, alter, or redefine a source canonical signal within the Business Brief experience. | KP-005 Â§Â§6, 10, 14, 17 |
| FR-010 | The system shall not execute a consequential business action from the Business Brief without explicit owner approval and deterministic validation. | KP-005 Â§Â§14, 16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 6. Non-Functional Requirements

| ID | Requirement | Trace |
|---|---|---|
| NFR-001 | The narrative shall be concise and prioritize clarity, relevance, and business understanding over information volume. | KP-005 Â§Â§2, 9, 14, 15 |
| NFR-002 | The narrative shall remain explainable: each material statement, source signal, and recommendation must be traceable to relevant deterministic evidence and approved context. | KP-005 Â§Â§14, 17, 19; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14 |
| NFR-003 | The experience shall remain useful when understanding is incomplete and shall communicate material limitations honestly. | KP-005 Â§Â§9, 15, 19; KP-003 Â§Â§14, 15 |
| NFR-004 | The experience shall preserve source-concept separation across all integrated content. | KP-005 Â§Â§6, 14, 17; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14 |
| NFR-005 | The experience shall maintain owner control over consequential business decisions and actions. | KP-005 Â§Â§14, 15, 16, 17 |
| NFR-006 | The experience shall use only information relevant to the authorized business context. | KP-005 Â§Â§10, 15, 17; KP-001 Â§Â§6, 14 |

## 7. Backend Responsibilities

| ID | Responsibility | Trace |
|---|---|---|
| BE-001 | Resolve the requested business and point-in-time context for the Brief. | KP-005 Â§Â§3, 10, 17 |
| BE-002 | Retrieve and integrate the approved Brief inputs while retaining their source identity and meaning. | KP-005 Â§Â§10, 12, 17, 19 |
| BE-003 | Obtain canonical signal assessments from their authoritative owners; do not calculate Health, Momentum, or Confidence within the Brief boundary. | KP-005 Â§Â§6, 14, 17; KP-002 Â§17; KP-003 Â§17; KP-004 Â§17 |
| BE-004 | Provide traceable evidence and approved context for material narrative statements and recommendations. | KP-005 Â§Â§14, 16, 17, 19 |
| BE-005 | Identify and carry forward material limitations relevant to reliable understanding. | KP-005 Â§Â§9, 15, 19; KP-003 Â§Â§11, 17 |
| BE-006 | Enforce that the Brief boundary can recommend but cannot itself execute consequential actions. | KP-005 Â§Â§14, 17; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 8. Frontend Responsibilities

| ID | Responsibility | Trace |
|---|---|---|
| FE-001 | Present the Business Brief as one coherent narrative rather than as a generic dashboard, report, widget collection, chat, or KPI page. | KP-005 Â§Â§3, 9, 14, 17 |
| FE-002 | Make material changes, current understanding, priorities, opportunities, risks, and recommendation reasoning understandable. | KP-005 Â§Â§5, 11, 15 |
| FE-003 | Clearly distinguish the source roles of Health, Momentum, and Confidence. | KP-005 Â§Â§6, 15; KP-002 Â§3; KP-003 Â§3; KP-004 Â§3 |
| FE-004 | Make material limitations in current understanding visible where relevant to an ownerâ€™s interpretation. | KP-005 Â§Â§9, 15; KP-003 Â§Â§3, 14 |
| FE-005 | Provide access to explanation of material narrative content and recommendations without implying AI or system authority to decide. | KP-005 Â§Â§14, 16, 18 |
| FE-006 | Present downstream action opportunities as owner-controlled; require the appropriate approval path outside the Brief when an action is consequential. | KP-005 Â§Â§14, 15, 18 |

## 9. AI Responsibilities

| ID | Responsibility | Trace |
|---|---|---|
| AI-001 | Assist in composing and explaining the Brief only from deterministic evidence and approved business context. | KP-005 Â§16 |
| AI-002 | Preserve the independent meanings of Business Health, Business Momentum, and Business Confidence. | KP-005 Â§Â§6, 16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |
| AI-003 | Explain recommendation reasoning and material business relevance. | KP-005 Â§Â§14, 16 |
| AI-004 | Communicate material limitations rather than imply unsupported certainty. | KP-005 Â§16; KP-003 Â§Â§14, 16 |
| AI-005 | Not invent, set, override, or alter deterministic business facts, canonical signals, priorities, opportunities, or risks. | KP-005 Â§16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |
| AI-006 | Not execute consequential business actions; route any such action through explicit owner approval and deterministic validation. | KP-005 Â§16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 10. Deterministic Responsibilities

| ID | Responsibility | Trace |
|---|---|---|
| DR-001 | Provide deterministic business facts and source assessments used by the Brief. | KP-005 Â§Â§10, 17, 19 |
| DR-002 | Remain the authoritative basis for Business Health, Business Momentum, and Business Confidence inputs. | KP-002 Â§Â§14, 17; KP-003 Â§Â§14, 17; KP-004 Â§Â§14, 17 |
| DR-003 | Support traceability from a material Brief statement or recommendation to its relevant evidence and approved context. | KP-005 Â§Â§14, 17, 19 |
| DR-004 | Validate consequential actions before execution after explicit owner approval. | KP-005 Â§Â§14, 16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 11. API Requirements

The implementation shall expose high-level, business-oriented integration capabilities only; this specification defines no endpoint shapes or payloads.

| ID | Capability | Trace |
|---|---|---|
| API-001 | Retrieve the current Business Brief for an authorized business context and relevant point in time. | KP-005 Â§Â§3, 10, 17 |
| API-002 | Retrieve the explanation, deterministic evidence references, approved context references, and material limitations associated with a Brief statement or recommendation. | KP-005 Â§Â§14, 16, 17, 19; KP-003 Â§14 |
| API-003 | Retrieve source-signal context while preserving the independent roles of Health, Momentum, and Confidence. | KP-005 Â§Â§6, 17; KP-002 Â§17; KP-003 Â§17; KP-004 Â§17 |
| API-004 | Initiate an owner-controlled transition to a downstream action or explanation experience; it shall not execute a consequential action within the Brief interface. | KP-005 Â§Â§14, 18; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 12. Domain Events

The following high-level events communicate changes relevant to refreshing or explaining a Business Brief. They do not define event payloads, transport, or technical delivery mechanisms.

| Event | Meaning | Consumer Responsibility | Trace |
|---|---|---|---|
| BusinessContextUpdated | Approved Business DNA, Business Season, or Business Goals context relevant to the Brief changed. | Reassess narrative relevance without redefining the source context. | KP-001 Â§Â§6, 14, 17; KP-005 Â§Â§10, 17 |
| BusinessHealthUpdated | The authoritative current-condition assessment changed. | Integrate the source assessment into the Brief without recalculation. | KP-002 Â§Â§14, 17; KP-005 Â§Â§6, 17 |
| BusinessMomentumUpdated | The authoritative observed-direction-and-rate assessment changed. | Integrate the source assessment into the Brief without recalculation or forecasting. | KP-004 Â§Â§14, 17; KP-005 Â§Â§6, 17 |
| BusinessConfidenceUpdated | The authoritative reliability-of-understanding communication changed. | Refresh material limitations and reliability context where relevant. | KP-003 Â§Â§14, 17; KP-005 Â§Â§9, 17 |
| MaterialBusinessActivityRecorded | Deterministic activity relevant to the point-in-time narrative was recorded. | Evaluate whether it is material to the Brief narrative. | KP-005 Â§Â§10, 11, 15, 19 |
| PrioritiesOrOpportunityContextUpdated | Relevant attention, opportunity, or risk context changed. | Evaluate relevance for inclusion in the Brief narrative. | KP-005 Â§Â§10, 11, 15, 17 |

## 13. Security Requirements

| ID | Requirement | Trace |
|---|---|---|
| SEC-001 | The system shall restrict Brief access to an authenticated and authorized owner or authorized business context. | KP-005 Â§Â§5, 15, 17 |
| SEC-002 | The system shall ensure that the Brief, its source information, explanations, and limitations are associated only with the authorized business context. | KP-005 Â§Â§10, 17, 19; KP-001 Â§Â§6, 17 |
| SEC-003 | The system shall protect owner control by preventing the Brief or AI-assisted explanation from executing consequential actions without explicit owner approval and deterministic validation. | KP-005 Â§Â§14, 16, 17 |
| SEC-004 | The system shall not expose source evidence or approved context beyond what is necessary to provide the authorized Brief and explanation. | KP-005 Â§Â§10, 15, 17, 19 |

## 14. Audit Requirements

| ID | Requirement | Trace |
|---|---|---|
| AUD-001 | The system shall retain an audit record of each Business Brief retrieval or generation, including the business context and relevant point in time. | KP-005 Â§Â§3, 17, 19 |
| AUD-002 | The system shall retain traceability from material narrative statements and recommendations to the relevant deterministic evidence and approved context. | KP-005 Â§Â§14, 16, 17, 19 |
| AUD-003 | The system shall retain material limitations that affected the reliability of a presented narrative or explanation. | KP-005 Â§Â§9, 15, 19; KP-003 Â§Â§11, 17 |
| AUD-004 | The system shall retain the owner approval and deterministic-validation outcome for any consequential action initiated from a Brief context. | KP-005 Â§Â§14, 16, 17; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |

## 15. Acceptance Criteria

| ID | Criterion | Trace |
|---|---|---|
| AC-001 | Given relevant approved inputs, the system produces one concise point-in-time Business Brief narrative. | KP-005 Â§Â§3, 11, 14 |
| AC-002 | A user can identify the current-condition, directional, and reliability meanings without their being conflated. | KP-005 Â§Â§6, 15; KP-002 Â§3; KP-003 Â§3; KP-004 Â§3 |
| AC-003 | Every recommendation displayed in the Brief has accessible reasoning grounded in relevant deterministic evidence and approved context. | KP-005 Â§Â§14, 16, 17, 19 |
| AC-004 | When material understanding is incomplete, the Brief communicates the limitation without presenting unsupported certainty. | KP-005 Â§Â§9, 15; KP-003 Â§Â§14, 16 |
| AC-005 | The Brief does not calculate or alter Health, Momentum, or Confidence. | KP-005 Â§Â§6, 14, 17 |
| AC-006 | The Brief is not delivered as a generic dashboard, report, widget collection, AI chat, or KPI page. | KP-005 Â§Â§3, 14, 17, 21 |
| AC-007 | A consequential action cannot be executed from the Brief without explicit owner approval and deterministic validation. | KP-005 Â§Â§14, 16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |
| AC-008 | A user cannot access a Brief or source explanation outside the authorized business context. | KP-005 Â§Â§10, 17, 19 |

## 16. Out of Scope

This specification does not define:

- the canonical business definitions of Business DNA, Business Health, Business Confidence, Business Momentum, or Business Brief;
- signal calculations, scoring algorithms, thresholds, or source-assessment methods;
- database schemas, data storage structures, API payloads, endpoint designs, code, technical architecture, or technology selection;
- UI mockups, layouts, visual design systems, or detailed operational workflows;
- the canonical definitions of Todayâ€™s Priorities, Opportunity Center, Decision Center, risks, or opportunities; or
- autonomous execution of consequential business actions.

All exclusions preserve the boundaries defined by KP-001 through KP-005. [Trace: KP-001 Â§21; KP-002 Â§21; KP-003 Â§21; KP-004 Â§21; KP-005 Â§21]

## 17. Dependencies

| Dependency | Purpose | Trace |
|---|---|---|
| KP-001 â€” Business DNA | Provides approved enduring business context for relevance. | KP-001 Â§Â§3, 6, 14, 17; KP-005 Â§12 |
| KP-002 â€” Business Health | Provides the independent current-condition assessment. | KP-002 Â§Â§3, 14, 17; KP-005 Â§12 |
| KP-003 â€” Business Confidence | Provides the independent reliability-of-understanding communication. | KP-003 Â§Â§3, 14, 17; KP-005 Â§12 |
| KP-004 â€” Business Momentum | Provides the independent observed direction-and-rate assessment. | KP-004 Â§Â§3, 14, 17; KP-005 Â§12 |
| Deterministic business information | Provides material activity and evidence for the narrative and explanation. | KP-005 Â§Â§10, 17, 19 |
| Approved context providers | Provide Business Season, Business Goals, priorities, opportunities, and risks where relevant. | KP-005 Â§Â§10, 12, 17 |
| Owner approval and deterministic validation capability | Preserves human control over consequential actions. | KP-005 Â§Â§14, 16, 17 |

## 18. Risks

| Risk | Mitigation Requirement | Trace |
|---|---|---|
| The Brief becomes a dashboard, report, widget collection, or chat instead of a narrative. | Enforce narrative composition and acceptance criteria that validate coherent, concise business understanding. | KP-005 Â§Â§3, 9, 14, 17 |
| Source concepts drift or become conflated in the Brief. | Preserve source identity, traceability, and explicit separation of Health, Momentum, and Confidence. | KP-005 Â§Â§6, 14, 17; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14 |
| AI introduces unsupported statements or implied certainty. | Ground AI output in deterministic evidence and approved context; communicate material limitations. | KP-005 Â§16; KP-003 Â§Â§14, 16 |
| A recommendation is opaque or irrelevant. | Require explanation and relevance traceability for every recommendation. | KP-005 Â§Â§14, 15, 16 |
| Incomplete understanding is concealed. | Surface material limitations through the Brief using Business Confidence context. | KP-005 Â§Â§9, 15, 19; KP-003 Â§Â§3, 14 |
| A consequential action is executed without owner control. | Require explicit owner approval and deterministic validation outside the Brief boundary. | KP-005 Â§Â§14, 16, 17 |

## 19. Testing Strategy

| Test Area | Verification | Trace |
|---|---|---|
| Narrative composition | Verify that a Brief integrates only relevant approved inputs into a coherent point-in-time narrative. | KP-005 Â§Â§3, 10, 14, 15 |
| Concept separation | Verify that Health, Momentum, and Confidence retain their independent meanings in all Brief content. | KP-005 Â§Â§6, 14, 17; KP-002 Â§14; KP-003 Â§14; KP-004 Â§14 |
| Explainability | Verify that each material statement and recommendation is traceable to relevant evidence and approved context. | KP-005 Â§Â§14, 16, 17, 19 |
| Incomplete understanding | Verify that material limitations are communicated honestly and do not prevent a useful Brief. | KP-005 Â§Â§9, 15, 19; KP-003 Â§Â§14, 15 |
| AI boundaries | Verify that AI does not invent source facts or signals, imply unsupported certainty, or execute consequential actions. | KP-005 Â§16; KP-002 Â§16; KP-003 Â§16; KP-004 Â§16 |
| Owner control | Verify that consequential actions require explicit owner approval and deterministic validation. | KP-005 Â§Â§14, 15, 16 |
| Authorization and isolation | Verify that a Brief and its explanation are available only within the authorized business context. | KP-005 Â§Â§10, 17, 19 |
| Event responsiveness | Verify that relevant high-level source changes can refresh the Brief context without recalculating source signals in the Brief boundary. | KP-005 Â§17; KP-002 Â§17; KP-003 Â§17; KP-004 Â§17 |

## 20. Future Evolution

Future work may enrich Business Brief relevance as TaxPilot deepens Business DNA, Business Season, Business Goals, deterministic history, Business Memory, and the Business Knowledge Graph. Any evolution must preserve the Briefâ€™s role as canonical narrative integration, the independent meanings of its source concepts, deterministic grounding, explainability, honest limitations, and owner decision authority.

Future changes require review against the approved Knowledge Packs and must not redefine their canonical concepts. [Trace: KP-001 Â§20; KP-002 Â§20; KP-003 Â§20; KP-004 Â§20; KP-005 Â§20]

## Governance

This Engineering Specification is subordinate to the approved Tier 1 Knowledge Foundation. It may be approved, revised, or superseded through the applicable Blueprint governance process. Any change that alters the meaning of a canonical business concept requires founder-approved Knowledge Pack governance rather than a change to this specification.

## Version History

| Version | Date | Status | Change |
|---|---|---|---|
| 1.0 | 2026-08-04 | Approved | Founder approval; frozen as the implementation authority for the Business Brief Experience. |
