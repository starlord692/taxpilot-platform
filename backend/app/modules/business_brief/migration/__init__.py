"""Temporary ES-007 Business Brief migration boundary."""

from app.modules.business_brief.migration.facade import BusinessBriefCompatibilityFacade
from app.modules.business_brief.migration.projection import (
    BusinessBriefCompatibilityContextAlias,
    BusinessBriefCompatibilityProjectionDescriptor,
    BusinessBriefCompatibilityProjectionProvider,
    BusinessBriefCompatibilitySignalAlias,
)

__all__ = [
    "BusinessBriefCompatibilityContextAlias",
    "BusinessBriefCompatibilityFacade",
    "BusinessBriefCompatibilityProjectionDescriptor",
    "BusinessBriefCompatibilityProjectionProvider",
    "BusinessBriefCompatibilitySignalAlias",
]
