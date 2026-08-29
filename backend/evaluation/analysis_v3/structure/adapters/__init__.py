from .allin1 import AllInOneStructureAdapter
from .base import StructureAdapter, StructureMetadata, StructureResult
from .external_json import ExternalJsonStructureAdapter
from .songformer import SongFormerStructureAdapter

ADAPTERS: dict[str, type[StructureAdapter]] = {
    "allin1": AllInOneStructureAdapter,
    "songformer": SongFormerStructureAdapter,
    "external_json": ExternalJsonStructureAdapter,
}

__all__ = [
    "ADAPTERS",
    "AllInOneStructureAdapter",
    "ExternalJsonStructureAdapter",
    "SongFormerStructureAdapter",
    "StructureAdapter",
    "StructureMetadata",
    "StructureResult",
]
