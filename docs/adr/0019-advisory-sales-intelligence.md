# ADR 0019: Advisory Sales Intelligence

## Status

Accepted for EP-016D.

## Decision

Sales intelligence is a deterministic, read-only advisory layer around the
canonical invoice workflow. It evaluates invoice, customer, catalog, business
settings, tax profile, and bounded historical invoice data without mutating any
record. Recommendations are returned through a separate canonical endpoint and
include a category, severity, confidence score, explanation, and suggested
human action.

The existing financial engine remains the authority for reconciliation. The
existing lifecycle and domain events remain unchanged. Intelligence evaluation
may publish its own advisory event, but recommendations cannot block, issue, or
alter an invoice.

## Consequences

- Duplicate and pricing signals are explainable deterministic heuristics.
- Historical comparisons are bounded to the latest 100 canonical invoices for
  the same customer.
- Reference-number matching is deferred because the canonical invoice model has
  no external reference field.
- LLMs, external AI services, automated changes, and durable recommendation
  storage remain outside this package.
