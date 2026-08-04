"""Unit tests for DNA-002 deterministic Business DNA assembly."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_dna import (
    BusinessDNAContextInput,
    BusinessDNAProfileProvenance,
    BusinessDNAService,
    FinancialProfile,
)
from tests.test_business_dna_models import context


def input_context() -> BusinessDNAContextInput:
    """Provide complete authoritative descriptive input for service tests."""
    source = context()
    return BusinessDNAContextInput(
        business_id=source.business_id,
        revision=source.revision,
        recorded_at=source.recorded_at,
        identity=source.identity,
        operational=source.operational,
        financial=source.financial,
        compliance=source.compliance,
        strategic=source.strategic,
    )


def test_service_assembles_authoritative_context_without_changing_profiles() -> None:
    """The service preserves declared profiles, provenance, and limitations exactly."""
    supplied = input_context()

    result = BusinessDNAService().assemble(supplied)

    assert result.business_id == supplied.business_id
    assert result.revision == supplied.revision
    assert result.identity is supplied.identity
    assert result.operational is supplied.operational
    assert result.financial is supplied.financial
    assert result.compliance is supplied.compliance
    assert result.strategic is supplied.strategic


def test_service_preserves_explicit_incomplete_context_without_inference() -> None:
    """An explicit limitation remains available rather than being filled or derived."""
    supplied = input_context()
    limited_provenance = BusinessDNAProfileProvenance(
        source=supplied.financial.provenance.source,
        reference=supplied.financial.provenance.reference,
        description=supplied.financial.provenance.description,
        effective_at=supplied.financial.provenance.effective_at,
        limitations=("Financial profile has not been confirmed",),
    )
    limited_financial = FinancialProfile(provenance=limited_provenance)
    limited = replace(supplied, financial=limited_financial)

    result = BusinessDNAService().assemble(limited)

    assert result.financial == limited_financial
    assert result.financial.provenance.limitations == (
        "Financial profile has not been confirmed",
    )


def test_service_rejects_source_effective_after_context_is_recorded() -> None:
    """Temporal traceability cannot claim unavailable future source context."""
    supplied = input_context()
    future_provenance = replace(
        supplied.identity.provenance,
        effective_at=supplied.recorded_at + timedelta(seconds=1),
    )
    future_identity = replace(supplied.identity, provenance=future_provenance)
    invalid = replace(supplied, identity=future_identity)

    with pytest.raises(ValueError, match="cannot be effective after"):
        BusinessDNAService().assemble(invalid)


def test_service_is_deterministic_for_identical_authoritative_input() -> None:
    """The service has no time-dependent, inferential, or AI behavior."""
    service = BusinessDNAService()
    supplied = input_context()

    assert service.assemble(supplied) == service.assemble(supplied)
