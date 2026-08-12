"""Dataset adapters for the real-world evaluation corpus."""

from evaluation.datasets.asap import AsapAdapter
from evaluation.datasets.guitarset import GuitarSetAdapter
from evaluation.datasets.maestro import MaestroAdapter
from evaluation.datasets.registry import register
from evaluation.datasets.slakh import SlakhAdapter

register(MaestroAdapter())
register(AsapAdapter())
register(GuitarSetAdapter())
register(SlakhAdapter())

__all__ = ["register"]
