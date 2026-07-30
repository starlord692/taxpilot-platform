"""Provider request and response redaction utilities."""

from collections.abc import Mapping

SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "password_hash",
    "secret",
    "api_key",
    "private_key",
}


class ProviderPayloadRedactor:
    """Redact sensitive values at the provider boundary."""

    def redact_mapping(self, payload: Mapping[str, object]) -> dict[str, object]:
        """Return a recursively redacted mapping."""
        redacted: dict[str, object] = {}
        for key, value in payload.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, Mapping):
                redacted[key] = self.redact_mapping(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_mapping(item) if isinstance(item, Mapping) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted
