"""ERP automation orchestration service."""

import uuid
from collections.abc import Callable, Sequence
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.exceptions import TaxPilotException
from app.modules.documents.automation.events import (
    AutomationCompletedEvent,
    AutomationFailedEvent,
    AutomationStartedEvent,
)
from app.modules.documents.automation.exceptions import (
    AutomationConflictException,
    AutomationNotFoundException,
    AutomationValidationException,
)
from app.modules.documents.automation.models import (
    AutomationRun,
    AutomationState,
)
from app.modules.documents.automation.schemas import (
    AutomationResult,
    AutomationRunResponse,
)
from app.modules.documents.automation.strategies import AutomationStrategy
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.review.models import ValidationSeverity
from app.modules.documents.review.schemas import DocumentValidationResponse
from app.modules.documents.review.services import DocumentReviewService


class AutomationRunRepositoryProtocol(Protocol):
    """Automation run repository behavior."""

    async def create_started(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        automation_type: object,
        idempotency_key: str,
    ) -> AutomationRun:
        """Create a running automation run."""
        ...

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return latest automation run for document."""
        ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AutomationRun | None:
        """Return automation run by idempotency key."""
        ...

    async def get_running_for_document(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return running automation for document."""
        ...

    async def mark_completed(
        self,
        run: AutomationRun,
        *,
        erp_record_type: str,
        erp_record_id: uuid.UUID,
    ) -> AutomationRun:
        """Mark automation completed."""
        ...

    async def mark_failed(
        self,
        run: AutomationRun,
        *,
        reason: str,
    ) -> AutomationRun:
        """Mark automation failed."""
        ...


class ExtractedDocumentRepositoryProtocol(Protocol):
    """Extracted document repository behavior."""

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extracted document by source document UUID."""
        ...


class AutomationUnitOfWork(Protocol):
    """Unit of Work contract for automation orchestration."""

    automation_runs: AutomationRunRepositoryProtocol
    extracted_documents: ExtractedDocumentRepositoryProtocol

    async def __aenter__(self) -> "AutomationUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], AutomationUnitOfWork]


class DocumentAutomationService:
    """Coordinate reviewed document automation through existing ERP services."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        review_service: DocumentReviewService,
        strategies: Sequence[AutomationStrategy],
        event_dispatcher: EventDispatcher,
    ) -> None:
        """Initialize automation dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._review_service = review_service
        self._strategies = list(strategies)
        self._event_dispatcher = event_dispatcher

    async def automate(
        self,
        document_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> AutomationResult:
        """Automate a reviewed document by delegating to an ERP service."""
        validation = await self._review_service.get_validation(document_id)
        self._ensure_review_ready(validation, business_id)
        extracted_document = await self._get_extracted_document(document_id)
        strategy = self._select_strategy(extracted_document)
        strategy.validate(extracted_document, validation)
        key = idempotency_key or self._deterministic_key(
            document_id=document_id,
            business_id=business_id,
            strategy_name=strategy.erp_record_type,
        )

        existing = await self._get_existing_run(document_id, key)
        if existing is not None:
            return existing

        run = await self._start_run(
            document_id=document_id,
            business_id=business_id,
            strategy=strategy,
            idempotency_key=key,
        )
        try:
            request = strategy.map(extracted_document)
            result = await strategy.execute(request, business_id=business_id)
            erp_record_id = strategy.result_id(result)
            completed = await self._complete_run(
                key,
                erp_record_type=strategy.erp_record_type,
                erp_record_id=erp_record_id,
            )
            return AutomationResult(
                run=AutomationRunResponse.model_validate(completed),
                reused_existing=False,
            )
        except TaxPilotException as exc:
            await self._fail_run(run, reason=exc.message)
            raise
        except Exception as exc:
            await self._fail_run(run, reason=str(exc))
            raise

    async def get_automation(self, document_id: uuid.UUID) -> AutomationRunResponse:
        """Return latest automation run for a document."""
        async with self._unit_of_work_factory() as uow:
            run = await uow.automation_runs.get_by_document_id(document_id)
            if run is None:
                raise AutomationNotFoundException(
                    "Document automation was not found",
                    details={"document_id": str(document_id)},
                )
            await uow.commit()
        return AutomationRunResponse.model_validate(run)

    async def _get_extracted_document(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument:
        """Return extracted document or raise."""
        async with self._unit_of_work_factory() as uow:
            extracted_document = await uow.extracted_documents.get_by_document_id(
                document_id
            )
            if extracted_document is None:
                raise AutomationValidationException(
                    "Document extraction is required before automation",
                    details={"document_id": str(document_id)},
                )
            await uow.commit()
        return extracted_document

    def _ensure_review_ready(
        self,
        validation: DocumentValidationResponse,
        business_id: uuid.UUID,
    ) -> None:
        """Raise when review state is not automation-ready."""
        if validation.business_id != business_id:
            raise AutomationValidationException(
                "Document does not belong to requested business",
                details={
                    "document_business_id": str(validation.business_id),
                    "requested_business_id": str(business_id),
                },
            )
        unresolved_errors = [
            issue
            for issue in validation.issues
            if issue.severity == ValidationSeverity.ERROR and not issue.resolved
        ]
        if unresolved_errors:
            raise AutomationValidationException(
                "Document has unresolved validation errors",
                details={"document_id": str(validation.document_id)},
            )
        if not validation.ready_for_automation:
            raise AutomationValidationException(
                "Document has not been approved for automation",
                details={"document_id": str(validation.document_id)},
            )

    def _select_strategy(
        self,
        extracted_document: ExtractedDocument,
    ) -> AutomationStrategy:
        """Select strategy for the extracted document type."""
        for strategy in self._strategies:
            if strategy.supports(extracted_document):
                return strategy
        raise AutomationValidationException(
            "Document type is not supported for automation",
            details={"document_type": extracted_document.document_type.value},
        )

    async def _get_existing_run(
        self,
        document_id: uuid.UUID,
        idempotency_key: str,
    ) -> AutomationResult | None:
        """Return existing idempotent result or prevent duplicate automation."""
        async with self._unit_of_work_factory() as uow:
            existing_by_key = await uow.automation_runs.get_by_idempotency_key(
                idempotency_key
            )
            if existing_by_key is not None:
                if existing_by_key.status == AutomationState.COMPLETED:
                    await uow.commit()
                    return AutomationResult(
                        run=AutomationRunResponse.model_validate(existing_by_key),
                        reused_existing=True,
                    )
                if existing_by_key.status == AutomationState.RUNNING:
                    raise AutomationConflictException(
                        "Automation is already running for this idempotency key",
                        details={"idempotency_key": idempotency_key},
                    )

            existing_by_document = await uow.automation_runs.get_by_document_id(
                document_id
            )
            if (
                existing_by_document is not None
                and existing_by_document.status == AutomationState.COMPLETED
            ):
                await uow.commit()
                return AutomationResult(
                    run=AutomationRunResponse.model_validate(existing_by_document),
                    reused_existing=True,
                )

            running = await uow.automation_runs.get_running_for_document(document_id)
            if running is not None:
                raise AutomationConflictException(
                    "Automation is already running for this document",
                    details={"document_id": str(document_id)},
                )
            await uow.commit()
        return None

    async def _start_run(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        strategy: AutomationStrategy,
        idempotency_key: str,
    ) -> AutomationRun:
        """Create and publish a running automation record."""
        async with self._unit_of_work_factory() as uow:
            run = await uow.automation_runs.create_started(
                document_id=document_id,
                business_id=business_id,
                automation_type=strategy.automation_type,
                idempotency_key=idempotency_key,
            )
            await self._event_dispatcher.dispatch(
                AutomationStartedEvent(
                    run_id=run.id,
                    document_id=document_id,
                    business_id=business_id,
                    automation_type=strategy.automation_type,
                )
            )
            await uow.commit()
        return run

    async def _complete_run(
        self,
        idempotency_key: str,
        *,
        erp_record_type: str,
        erp_record_id: uuid.UUID,
    ) -> AutomationRun:
        """Mark automation completed and publish event."""
        async with self._unit_of_work_factory() as uow:
            run = await uow.automation_runs.get_by_idempotency_key(idempotency_key)
            if run is None:
                raise AutomationNotFoundException("Automation run was not found")
            run = await uow.automation_runs.mark_completed(
                run,
                erp_record_type=erp_record_type,
                erp_record_id=erp_record_id,
            )
            await self._event_dispatcher.dispatch(
                AutomationCompletedEvent(
                    run_id=run.id,
                    document_id=run.document_id,
                    business_id=run.business_id,
                    erp_record_type=erp_record_type,
                    erp_record_id=erp_record_id,
                )
            )
            await uow.commit()
        return run

    async def _fail_run(self, run: AutomationRun, *, reason: str) -> None:
        """Mark automation failed and publish event."""
        async with self._unit_of_work_factory() as uow:
            current = await uow.automation_runs.get_by_idempotency_key(
                run.idempotency_key
            )
            if current is None:
                return
            failed = await uow.automation_runs.mark_failed(current, reason=reason)
            await self._event_dispatcher.dispatch(
                AutomationFailedEvent(
                    run_id=failed.id,
                    document_id=failed.document_id,
                    business_id=failed.business_id,
                    reason=reason,
                )
            )
            await uow.commit()

    def _deterministic_key(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        strategy_name: str,
    ) -> str:
        """Return deterministic fallback idempotency key."""
        value = f"{business_id}:{document_id}:{strategy_name}"
        return uuid.uuid5(uuid.NAMESPACE_URL, value).hex
