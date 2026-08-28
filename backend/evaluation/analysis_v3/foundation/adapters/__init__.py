from .base import EmbeddingResult, FoundationModelAdapter, ModelMetadata
from .clamp3 import CLaMP3Adapter
from .clap import CLAPAdapter
from .mert import MERTAdapter
from .muq import MuQAdapter
from .musicfm import MusicFMAdapter

ADAPTERS: dict[str, type[FoundationModelAdapter]] = {
    "mert": MERTAdapter,
    "muq": MuQAdapter,
    "musicfm": MusicFMAdapter,
    "clamp3": CLaMP3Adapter,
    "clap": CLAPAdapter,
}

__all__ = [
    "FoundationModelAdapter",
    "EmbeddingResult",
    "ModelMetadata",
    "MERTAdapter",
    "MuQAdapter",
    "MusicFMAdapter",
    "CLaMP3Adapter",
    "CLAPAdapter",
    "ADAPTERS",
]
