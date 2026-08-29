from .base import PulseAdapter, PulseMetadata, PulseResult
from .beat_this import BeatThisAdapter, BeatThisSingleFinal0Adapter
from .beatnet import BeatNetAdapter
from .current import CurrentBaselineAdapter

ADAPTERS: dict[str, type[PulseAdapter]] = {
    "current": CurrentBaselineAdapter,
    "beat_this": BeatThisAdapter,
    "beat_this_single_final0": BeatThisSingleFinal0Adapter,
    "beatnet": BeatNetAdapter,
}

__all__ = [
    "PulseAdapter",
    "PulseResult",
    "PulseMetadata",
    "CurrentBaselineAdapter",
    "BeatThisAdapter",
    "BeatThisSingleFinal0Adapter",
    "BeatNetAdapter",
    "ADAPTERS",
]
