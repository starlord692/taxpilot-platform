"""Outbox event subscriber registration and taxonomy.

This module defines the registration hook for production outbox consumers
and documents the event classification taxonomy for TaxPilot AI.

Event Classification Taxonomy:
1. sales.invoice.issued:
   Core financial domain event representing an issued sales invoice.
   Emitted on invoice issuance after inventory and accounting are committed.
   Downstream target: Reserved for future external tax portal reporting (e.g. NIC)
   or customer invoice email notification. In RC1, no external integration is active.

2. purchases.invoice.approved:
   Core financial domain event representing an approved purchase invoice.
   Emitted on purchase approval after stock receipt and accounting accruals.
   Downstream target: Reserved for supplier notification and payment scheduling.

3. purchases.invoice.paid:
   Core financial domain event representing full payment of a purchase bill.
   Emitted on supplier payment completion.
   Downstream target: Reserved for supplier remittance advice notification.

4. sales.payment.recorded:
   Core financial domain event representing a customer payment receipt.
   Emitted on payment recording.
   Downstream target: Reserved for customer payment receipt dispatch.
"""

from __future__ import annotations

from app.common.outbox.relay import OutboxRelay
from app.core.logging import get_logger

logger = get_logger(__name__)

# Canonical outbox event names
EVENT_SALES_INVOICE_ISSUED = "sales.invoice.issued"
EVENT_PURCHASES_INVOICE_APPROVED = "purchases.invoice.approved"
EVENT_PURCHASES_INVOICE_PAID = "purchases.invoice.paid"
# Backwards-compatibility alias
EVENT_PURCHASES_PURCHASE_PAID = EVENT_PURCHASES_INVOICE_PAID
EVENT_SALES_PAYMENT_RECORDED = "sales.payment.recorded"

CANONICAL_OUTBOX_EVENTS: frozenset[str] = frozenset(
    {
        EVENT_SALES_INVOICE_ISSUED,
        EVENT_PURCHASES_INVOICE_APPROVED,
        EVENT_PURCHASES_INVOICE_PAID,
        EVENT_SALES_PAYMENT_RECORDED,
    }
)


def register_subscribers(relay: OutboxRelay) -> None:
    """Register all active production consumers with the outbox relay.

    In RC1, no external consumers (email, SMS, or government tax webhooks)
    are provisioned in production. Zero placeholder or fake handlers are
    registered.

    Release Configuration & Operational Procedure:
    1. Default State: `outbox_relay_enabled` defaults to `False`. All business
       events staged during core financial operations are safely stored and
       retained in `PENDING` status in PostgreSQL. Unconsumed events do not
       undergo polling or dead-letter cycling.
    2. Operational Enablement Procedure:
       - Implement and test real downstream consumer handlers.
       - Register handlers here using `relay.subscribe(event_name, handler)`.
       - Enable the relay at runtime by setting the environment variable:
         `OUTBOX_RELAY_ENABLED=true`
       - Upon startup with registered subscribers and `OUTBOX_RELAY_ENABLED=true`,
         the background `OutboxRelay` worker claims the pending backlog in batches
         via `SELECT ... FOR UPDATE SKIP LOCKED` and delivers each event.
    """
    logger.info(
        "outbox_subscribers_bootstrapped",
        extra={
            "worker_id": relay.worker_id,
            "registered_event_count": 0,
        },
    )
