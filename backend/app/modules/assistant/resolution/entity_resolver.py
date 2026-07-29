"""Conversation-scoped entity resolution."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.context.schemas import ContextProvenance
from app.modules.assistant.memory.policies import (
    ENTITY_REFERENCE_TTL_HOURS,
    expires_in_hours,
)
from app.modules.assistant.models import (
    AssistantEntityReference,
    ContextSource,
    EntityResolutionConfidence,
)

ENTITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "invoice": ("invoice", "bill"),
    "customer": ("customer", "buyer"),
    "supplier": ("supplier", "purchase"),
    "vendor": ("vendor", "expense"),
    "document": ("document", "receipt"),
    "warehouse": ("warehouse", "stockroom"),
    "product": ("product", "item", "sku"),
    "expense": ("expense",),
    "gst_return_period": ("gstr", "gst return", "filing"),
    "accounting_report": ("trial balance", "balance sheet", "profit"),
}
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


@dataclass(frozen=True)
class EntityResolutionResult:
    """Result of deterministic entity resolution."""

    entity_type: str | None
    entity_id: uuid.UUID | None
    entity_label: str | None
    confidence: EntityResolutionConfidence
    confidence_score: float
    provenance: ContextProvenance
    expires_at: datetime


class EntityResolver:
    """Resolve conversation-local entity references without semantic search."""

    def detect_entity_type(self, message: str) -> str | None:
        """Detect an entity type using deterministic keyword rules."""
        normalized = message.lower()
        for entity_type, keywords in ENTITY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return entity_type
        return None

    def extract_entity_reference(
        self,
        *,
        message: str,
        source_id: uuid.UUID,
    ) -> EntityResolutionResult | None:
        """Extract explicit entity references from the current user message."""
        entity_type = self.detect_entity_type(message)
        if entity_type is None:
            return None
        entity_id = self._extract_uuid(message)
        confidence = (
            EntityResolutionConfidence.HIGH
            if entity_id is not None
            else EntityResolutionConfidence.LOW
        )
        score = 0.95 if entity_id is not None else 0.35
        label = entity_type.replace("_", " ")
        return EntityResolutionResult(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=label,
            confidence=confidence,
            confidence_score=score,
            provenance=ContextProvenance(
                source=ContextSource.USER_MESSAGE.value,
                source_id=str(source_id),
                source_version="assistant-entity-rules-v1",
                generated_by="EntityResolver",
                generated_at=utc_now(),
            ),
            expires_at=expires_in_hours(ENTITY_REFERENCE_TTL_HOURS),
        )

    def resolve_pronoun_reference(
        self,
        *,
        message: str,
        candidates: list[AssistantEntityReference],
    ) -> EntityResolutionResult:
        """Resolve vague references against active conversation-local candidates."""
        provenance = ContextProvenance(
            source=ContextSource.SYSTEM_DERIVED.value,
            source_id=None,
            source_version="assistant-entity-rules-v1",
            generated_by="EntityResolver",
            generated_at=utc_now(),
        )
        if not self._contains_pronoun_reference(message):
            return EntityResolutionResult(
                entity_type=None,
                entity_id=None,
                entity_label=None,
                confidence=EntityResolutionConfidence.UNRESOLVED,
                confidence_score=0,
                provenance=provenance,
                expires_at=expires_in_hours(ENTITY_REFERENCE_TTL_HOURS),
            )
        entity_type = self.detect_entity_type(message)
        narrowed = [
            candidate
            for candidate in candidates
            if entity_type is None or candidate.entity_type == entity_type
        ]
        if len(narrowed) == 1:
            candidate = narrowed[0]
            return EntityResolutionResult(
                entity_type=candidate.entity_type,
                entity_id=candidate.entity_id,
                entity_label=candidate.entity_label,
                confidence=EntityResolutionConfidence.MEDIUM,
                confidence_score=0.7,
                provenance=provenance,
                expires_at=candidate.expires_at,
            )
        confidence = (
            EntityResolutionConfidence.AMBIGUOUS
            if len(narrowed) > 1
            else EntityResolutionConfidence.UNRESOLVED
        )
        return EntityResolutionResult(
            entity_type=entity_type,
            entity_id=None,
            entity_label=None,
            confidence=confidence,
            confidence_score=0,
            provenance=provenance,
            expires_at=expires_in_hours(ENTITY_REFERENCE_TTL_HOURS),
        )

    def _extract_uuid(self, message: str) -> uuid.UUID | None:
        """Extract the first UUID from a message when present."""
        match = UUID_PATTERN.search(message)
        if match is None:
            return None
        return uuid.UUID(match.group(0))

    def _contains_pronoun_reference(self, message: str) -> bool:
        """Return whether the message contains a vague contextual reference."""
        normalized = message.lower()
        return any(
            term in normalized
            for term in ("that", "this", "same", "previous", "last")
        )

