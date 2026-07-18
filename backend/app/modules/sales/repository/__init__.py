"""Sales repository package."""

from app.modules.sales.repository.customer import CustomerRepository
from app.modules.sales.repository.invoice import SalesInvoiceRepository
from app.modules.sales.repository.payment import PaymentRepository

__all__ = [
    "CustomerRepository",
    "PaymentRepository",
    "SalesInvoiceRepository",
]
