# Engineering Technical Debt

This backlog records approved platform gaps that require dedicated engineering design and implementation. Items must reuse authoritative domain services and may not fabricate business data.

## TD-001 — Business Health Service

Implement an authoritative backend service that determines overall business health from verified business metrics. The service must define traceable health criteria and must not infer health from incomplete or paginated datasets.

## TD-002 — Workspace Summary API

Create a dedicated workspace summary endpoint that composes existing domain services without duplicating their business logic. The response should provide verified:

- Sales summary
- Purchase summary
- Expense summary
- Collections
- Outstanding receivables
- Cash position
- Pending reviews
- Compliance status

## TD-003 — AI Insights Service

Implement an AI insights backend service that generates evidence-based business recommendations. Every insight must identify and be supported by actual business data; fabricated recommendations are prohibited.

## TD-004 — Recent Activity Feed

Create a verified cross-module activity feed covering:

- Documents
- Invoices
- Payments
- GST actions
- Customer updates
- Supplier updates

The feed must preserve business isolation and authoritative event ordering.

## TD-005 — Quick Actions

Introduce dedicated creation flows for:

- Create Invoice
- Add Customer
- Add Supplier

Until these flows exist, workspace actions must route only to supported module destinations and clearly communicate the available behavior.
