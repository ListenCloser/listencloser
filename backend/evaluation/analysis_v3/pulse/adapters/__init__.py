from .base import PulseAdapter, PulseMetadata, PulseResult
from .beat_this import BeatThisAdapter
from .beatnet import BeatNetAdapter
from .current import CurrentBaselineAdapter

ADAPTERS: dict[str, type[PulseAdapter]] = {
    "current": CurrentBaselineAdapter,
    "beat_this": BeatThisAdapter,
    "beatnet": BeatNetAdapter,
}

__all__ = [
    "PulseAdapter",
    "PulseResult",
    "PulseMetadata",
    "CurrentBaselineAdapter",
    "BeatThisAdapter",
    "BeatNetAdapter",
    "ADAPTERS",
]
