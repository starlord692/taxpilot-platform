"""Canonical assistant action manifest registry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.actions.enums import AssistantActionType
from app.modules.assistant.actions.schemas import (
    ACTION_MANIFEST_REGISTRY_VERSION,
    ActionManifest,
)
from app.modules.assistant.models import ApprovalLevel, ToolSideEffect


class GenericActionPayload(BaseModel):
    """Conservative generic payload accepted by draft-first assistant actions."""

    model_config = ConfigDict(extra="forbid")

    data: dict[str, object] = Field(default_factory=dict)


class ActionManifestRegistry:
    """Canonical registry of assistant-supported ERP actions."""

    version = ACTION_MANIFEST_REGISTRY_VERSION

    def __init__(self, manifests: list[ActionManifest] | None = None) -> None:
        """Initialize with default service-backed action definitions."""
        configured = manifests or self._default_manifests()
        self._manifests = {manifest.action_type: manifest for manifest in configured}

    def get(self, action_type: AssistantActionType) -> ActionManifest:
        """Return one enabled manifest."""
        manifest = self._manifests[action_type]
        return manifest

    def list_definitions(self) -> list[ActionManifest]:
        """Return all registered action manifests."""
        return list(self._manifests.values())

    def supports(self, action_type: AssistantActionType) -> bool:
        """Return whether an action is registered and enabled."""
        manifest = self._manifests.get(action_type)
        return manifest is not None and manifest.enabled

    def _default_manifests(self) -> list[ActionManifest]:
        """Build conservative default action manifests."""
        schema = GenericActionPayload.model_json_schema()
        return [
            ActionManifest(
                action_type=AssistantActionType.SALES_INVOICE_CREATE_DRAFT,
                description="Create a sales invoice draft through SalesInvoiceService.",
                domain_owner="sales",
                required_service="SalesInvoiceService",
                input_schema=schema,
                approval_level=ApprovalLevel.EXPLICIT_USER_APPROVAL,
                side_effect=ToolSideEffect.WRITE,
                readiness_rules=["payload_present", "business_context_valid"],
                downstream_integrations=["GST", "Inventory", "Accounting"],
                result_record_type="sales_invoice",
            ),
            ActionManifest(
                action_type=AssistantActionType.PURCHASE_INVOICE_CREATE_DRAFT,
                description="Create a purchase invoice draft through PurchaseService.",
                domain_owner="purchases",
                required_service="PurchaseService",
                input_schema=schema,
                approval_level=ApprovalLevel.EXPLICIT_USER_APPROVAL,
                side_effect=ToolSideEffect.WRITE,
                readiness_rules=["payload_present", "business_context_valid"],
                downstream_integrations=["GST", "Inventory", "Accounting"],
                result_record_type="purchase_invoice",
            ),
            ActionManifest(
                action_type=AssistantActionType.EXPENSE_CREATE_DRAFT,
                description="Create an expense draft through ExpenseService.",
                domain_owner="expenses",
                required_service="ExpenseService",
                input_schema=schema,
                approval_level=ApprovalLevel.EXPLICIT_USER_APPROVAL,
                side_effect=ToolSideEffect.WRITE,
                readiness_rules=["payload_present", "business_context_valid"],
                downstream_integrations=["GST", "Accounting"],
                result_record_type="expense",
            ),
            ActionManifest(
                action_type=AssistantActionType.VENDOR_CREATE_DRAFT,
                description="Create a vendor draft through VendorService.",
                domain_owner="expenses",
                required_service="VendorService",
                input_schema=schema,
                approval_level=ApprovalLevel.EXPLICIT_USER_APPROVAL,
                side_effect=ToolSideEffect.WRITE,
                readiness_rules=["payload_present", "business_context_valid"],
                downstream_integrations=[],
                result_record_type="vendor",
            ),
            ActionManifest(
                action_type=AssistantActionType.PAYMENT_RECORD,
                description="Record a customer payment through PaymentService.",
                domain_owner="sales",
                required_service="PaymentService",
                input_schema=schema,
                approval_level=ApprovalLevel.EXPLICIT_USER_APPROVAL,
                side_effect=ToolSideEffect.WRITE,
                readiness_rules=["payload_present", "business_context_valid"],
                downstream_integrations=["Accounting"],
                result_record_type="payment",
            ),
        ]
