# ADR 0016: Canonical Sales workflow with legacy compatibility

## Status

Accepted for EP-016A.

## Decision

New Sales development uses a canonical workflow backed by `CatalogItem`, server-reserved financial-year invoice numbers, server-calculated totals, and explicit lifecycle transitions. Canonical issuance changes invoice state and publishes an event only; inventory, accounting, GST filing, payment, AI, and delivery side effects are future event subscribers.

Existing `/sales/invoices` and payment APIs remain temporarily operational. Historical line rows receive a nullable `catalog_item_id`; canonical requests require it. Canonical endpoints live below `/sales/workflow/invoices` until consumers migrate.

## Migration path

1. Add nullable catalog references, round-off, and sequence storage.
2. Route all new consumers to the canonical API.
3. Backfill historical line references where identity is provable; never guess mappings.
4. Migrate payment, inventory, ledger, GST, and document consumers through separate packages.
5. Deprecate legacy write APIs only after usage is verified as zero.

## Consequences

Two API surfaces coexist temporarily, but share persistence and domain rules where compatible. Legacy rows remain readable. Canonical issuance is deterministic and safe for future event-driven subscribers.
