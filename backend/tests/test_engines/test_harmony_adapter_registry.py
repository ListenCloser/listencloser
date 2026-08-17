"""Harmony adapter registry sanity checks.

The `lv_chordia` adapter was removed because the `chordia` package is not on
PyPI and its repository no longer resolves — the adapter could never run and
presented a fake runnable option in the registry. These tests lock the
registry to the real, usable adapter only.
"""

from __future__ import annotations

from evaluation.engines.harmony import (
    HARMONY_ADAPTERS,
    get_harmony_adapter,
    list_harmony_adapters,
)


def test_harmony_registry_lists_only_the_available_adapter():
    assert list_harmony_adapters() == ["music21_symbolic"]


def test_harmony_registry_has_no_dead_adapter():
    assert "lv_chordia" not in HARMONY_ADAPTERS


def test_music21_adapter_remains_available():
    adapter = get_harmony_adapter("music21_symbolic")
    assert adapter.engine_info.name == "music21_symbolic"
    assert adapter.is_available()
