from .allin1 import AllInOneStructureAdapter
from .base import StructureAdapter, StructureMetadata, StructureResult
from .external_json import ExternalJsonStructureAdapter

ADAPTERS: dict[str, type[StructureAdapter]] = {
    "allin1": AllInOneStructureAdapter,
    "external_json": ExternalJsonStructureAdapter,
}

__all__ = [
    "ADAPTERS",
    "AllInOneStructureAdapter",
    "ExternalJsonStructureAdapter",
    "StructureAdapter",
    "StructureMetadata",
    "StructureResult",
]
