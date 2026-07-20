# ADR-0015: Canonical catalog with optional capability profiles

Status: Accepted

## Context

TaxPilot's existing `inventory_products` model combines commercial identity with stock-specific behavior and cannot represent services without imposing inventory fields.

## Decision

Introduce `CatalogItem` as the stable commercial and tax identity for products and services. Introduce `InventoryItemProfile` as an optional one-to-one capability extension. Existing inventory product UUIDs are reused as catalog UUIDs. Legacy inventory APIs remain operational through a repository adapter that mirrors product writes into the catalog in the same transaction.

Tax classification is a reusable domain value object. Product items accept HSN classification and service items accept SAC classification; invalid combinations are rejected centrally.

## Migration

The migration is additive: create catalog tables, backfill catalog items and inventory profiles from `inventory_products`, preserve UUIDs, and retain existing tables and foreign keys. Downstream modules migrate to catalog references in later packages.

## Consequences

The catalog stays independent of stock behavior, services require no inventory profile, and existing inventory consumers continue to work. During transition, legacy product columns remain as a synchronized compatibility projection.
