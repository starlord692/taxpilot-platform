"""Dependencies for the Business Opportunity read transport."""

from fastapi import Request

from app.common.exceptions import InfrastructureException
from app.modules.business_opportunity.ports import BusinessOpportunityReadProvider


def get_business_opportunity_read_provider(
    request: Request,
) -> BusinessOpportunityReadProvider:
    """Return the owner-published opportunity read provider for this app."""
    provider = getattr(request.app.state, "business_opportunity_read_provider", None)
    if not isinstance(provider, BusinessOpportunityReadProvider):
        raise InfrastructureException(
            "Business Opportunity read provider is unavailable"
        )
    return provider
