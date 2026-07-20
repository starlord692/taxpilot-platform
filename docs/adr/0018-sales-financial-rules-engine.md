# ADR 0018: Canonical Sales Financial Rules Engine

## Status

Accepted for EP-016C.

## Decision

All canonical Sales monetary calculations are owned by `SalesFinancialRulesEngine`. It delegates GST component calculation to the existing GST engine, applies a configured round-off policy, derives supported payment-term due dates, validates invoice currency against Business Settings, and reconciles persisted values before issuance.

Canonical invoice currency and payment terms are persisted as snapshots. Historical invoices retain nullable values; canonical operations resolve missing currency through the configured business currency. Client-provided totals and round-off values are never authoritative.

Credit management is not implemented. Asynchronous credit validation hooks receive the calculated total and currency before draft persistence. Inventory, accounting, payments, filing, document delivery, and AI remain downstream capabilities.

## Consequences

- Financial calculations no longer live in the canonical workflow service.
- Issuance fails closed when persisted totals do not reconcile.
- Pre-engine canonical drafts receive a compatibility reconstruction of missing GST components before issue.
- New payment-term policies, tax supply rules, and credit providers can be introduced without changing invoice lifecycle events.
