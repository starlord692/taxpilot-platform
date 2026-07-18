"""Document automation mapper exports."""

from app.modules.documents.automation.mappers.expense import ExpenseMapper
from app.modules.documents.automation.mappers.purchase import PurchaseMapper
from app.modules.documents.automation.mappers.sales import SalesMapper

__all__ = [
    "ExpenseMapper",
    "PurchaseMapper",
    "SalesMapper",
]
