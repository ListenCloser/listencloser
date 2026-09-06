"""Explicit progress reporting for worker capability composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ProgressSink = Callable[[float, str | None], None]


def _clamp_progress(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class ProgressReporter:
    """Report normalized progress, optionally mapped into a parent interval.

    The reporter deliberately knows nothing about jobs, persistence, Supabase, or
    worker clients. Capability composition supplies a sink for the product-owned
    publication boundary and child stages receive bounded reporters.
    """

    sink: ProgressSink
    base: float = 0.0
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.base <= 1.0:
            raise ValueError("progress base must be between 0 and 1")
        if not 0.0 <= self.scale <= 1.0:
            raise ValueError("progress scale must be between 0 and 1")
        if self.base + self.scale > 1.0:
            raise ValueError("progress interval must not exceed 1")

    def report(self, progress: float, message: str | None = None) -> None:
        """Publish progress through this reporter's interval."""

        mapped = self.base + self.scale * _clamp_progress(progress)
        self.sink(_clamp_progress(mapped), message)

    def span(self, start: float, end: float) -> ProgressReporter:
        """Return a reporter mapped into ``start..end`` of this interval."""

        if not 0.0 <= start <= end <= 1.0:
            raise ValueError("progress span must satisfy 0 <= start <= end <= 1")
        return ProgressReporter(
            sink=self.sink,
            base=self.base + self.scale * start,
            scale=self.scale * (end - start),
        )
