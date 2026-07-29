"""GST compliance API router."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.responses import SuccessResponse
from app.modules.business.api.context import ensure_active_business_membership
from app.modules.gst.compliance.api.dependencies import (
    get_gst_compliance_service,
    get_gst_compliance_unit_of_work,
)
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import (
    GSTAuditReportResponse,
    GSTExportFormat,
    GSTR1Report,
    GSTR3BReport,
    GSTReportRequest,
    HSNReportLine,
    ITCReport,
)
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.identity.dependencies import CurrentUser

router = APIRouter(prefix="/compliance", tags=["GST Compliance"])
ComplianceServiceDep = Annotated[
    GSTComplianceService,
    Depends(get_gst_compliance_service),
]
ComplianceUnitOfWorkDep = Annotated[Any, Depends(get_gst_compliance_unit_of_work)]


@router.get(
    "/gstr1",
    response_model=SuccessResponse[GSTR1Report],
    status_code=status.HTTP_200_OK,
    summary="Generate GSTR-1",
    description="Generates GSTR-1 from posted GST source data.",
)
async def generate_gstr1(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTR1Report] | Response:
    """Generate GSTR-1."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_gstr1(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GSTR-1 generated")


@router.get(
    "/gstr3b",
    response_model=SuccessResponse[GSTR3BReport],
    status_code=status.HTTP_200_OK,
    summary="Generate GSTR-3B",
    description="Generates GSTR-3B from posted GST source data.",
)
async def generate_gstr3b(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTR3BReport] | Response:
    """Generate GSTR-3B."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_gstr3b(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GSTR-3B generated")


@router.get(
    "/itc",
    response_model=SuccessResponse[ITCReport],
    status_code=status.HTTP_200_OK,
    summary="Generate ITC report",
    description="Generates input tax credit report from posted source data.",
)
async def generate_itc(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[ITCReport] | Response:
    """Generate ITC report."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_itc_report(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "ITC report generated")


@router.get(
    "/hsn",
    response_model=SuccessResponse[list[HSNReportLine]],
    status_code=status.HTTP_200_OK,
    summary="Generate HSN summary",
    description="Generates HSN summary from posted source data.",
)
async def generate_hsn(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[list[HSNReportLine]] | Response:
    """Generate HSN summary."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_hsn_summary(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "HSN summary generated")


@router.get(
    "/audit",
    response_model=SuccessResponse[GSTAuditReportResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate GST audit report",
    description="Audits posted source data for GST consistency issues.",
)
async def generate_audit(
    current_user: CurrentUser,
    uow: ComplianceUnitOfWorkDep,
    service: ComplianceServiceDep,
    business_id: Annotated[uuid.UUID, Query(description="Business UUID.")],
    tax_period: Annotated[str, Query(description="Tax period, e.g. 2026-04.")],
    filing_frequency: GSTFilingFrequency = GSTFilingFrequency.MONTHLY,
    export_format: GSTExportFormat = GSTExportFormat.JSON,
) -> SuccessResponse[GSTAuditReportResponse] | Response:
    """Generate GST audit report."""
    await _ensure_business_member(uow, business_id, current_user.id)
    report = await service.generate_audit_report(
        GSTReportRequest(
            business_id=business_id,
            tax_period=tax_period,
            filing_frequency=filing_frequency,
        )
    )
    return _format_response(service, report, export_format, "GST audit generated")


def _format_response(
    service: GSTComplianceService,
    report: Any,
    export_format: GSTExportFormat,
    message: str,
) -> SuccessResponse[Any] | Response:
    """Return JSON success response or CSV response."""
    if export_format == GSTExportFormat.CSV:
        return Response(
            content=service.export_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gst-report.csv"},
        )
    return SuccessResponse(success=True, message=message, data=report)


async def _ensure_business_member(
    uow: Any,
    business_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Raise when current user is not a business member."""
    async with uow:
        await ensure_active_business_membership(
            uow,
            business_id=business_id,
            user_id=user_id,
            entered=True,
        )
