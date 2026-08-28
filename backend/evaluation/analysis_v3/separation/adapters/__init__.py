from .base import SeparationAdapter, SeparationMetadata, SeparationResult
from .bs_roformer import BSRoFormerAdapter
from .demucs import DemucsAdapter

ADAPTERS: dict[str, type[SeparationAdapter]] = {
    "bs_roformer": BSRoFormerAdapter,
    "demucs": DemucsAdapter,
}

__all__ = [
    "SeparationAdapter",
    "SeparationResult",
    "SeparationMetadata",
    "BSRoFormerAdapter",
    "DemucsAdapter",
    "ADAPTERS",
]
