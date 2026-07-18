"""Document automation strategy exports."""

from app.modules.documents.automation.strategies.base import AutomationStrategy
from app.modules.documents.automation.strategies.expense import (
    ExpenseAutomationStrategy,
)
from app.modules.documents.automation.strategies.purchase import (
    PurchaseAutomationStrategy,
)
from app.modules.documents.automation.strategies.sales import SalesAutomationStrategy

__all__ = [
    "AutomationStrategy",
    "ExpenseAutomationStrategy",
    "PurchaseAutomationStrategy",
    "SalesAutomationStrategy",
]
