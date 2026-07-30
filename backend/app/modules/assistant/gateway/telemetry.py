"""Provider telemetry helpers."""

import time


class ProviderCallTimer:
    """Simple monotonic timer for provider gateway telemetry."""

    def __init__(self) -> None:
        """Start a new provider call timer."""
        self._started = time.perf_counter()

    def elapsed_ms(self) -> int:
        """Return elapsed milliseconds since timer creation."""
        return int((time.perf_counter() - self._started) * 1000)
