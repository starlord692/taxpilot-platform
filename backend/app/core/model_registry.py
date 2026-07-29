"""SQLAlchemy model registry used for Alembic metadata discovery."""

from importlib import import_module

MODEL_MODULES: tuple[str, ...] = (
    "app.modules.identity.models",
    "app.modules.business.models",
    "app.modules.catalog.models",
    "app.modules.sales.models",
    "app.modules.purchases.models",
    "app.modules.expenses.models",
    "app.modules.inventory.models",
    "app.modules.accounting.chart_of_accounts.models",
    "app.modules.accounting.journal.models",
    "app.modules.accounting.ledger.models",
    "app.modules.accounting.balances.models",
    "app.modules.gst.models",
    "app.modules.gst.compliance.models",
    "app.modules.gst.einvoice.models",
    "app.modules.documents.models",
    "app.modules.documents.extraction.models",
    "app.modules.documents.review.models",
    "app.modules.documents.automation.models",
    "app.modules.assistant.models",
)


def import_all_models() -> None:
    """Import every SQLAlchemy model package so Base.metadata is complete."""
    for module_name in MODEL_MODULES:
        import_module(module_name)
