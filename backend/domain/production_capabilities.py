"""Production worker capability-registration policy.

Worker implementation registration is intentionally broader than the supported
production execution surface. Keep retirements explicit here so a legacy
handler cannot stay invocable merely because it still exists in
``domain.capabilities`` while cleanup is in flight.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger("production_capabilities")

# ``describe`` is a legacy descriptor bundle whose fallback path can silently
# change engines and can label an RMS-derived proxy as integrated LUFS. The
# canonical measured-audio path is ``perceptual_series`` plus the narrower
# trusted tempo/key capabilities. See #965.
_RETIRED_CAPABILITIES: dict[tuple[str, str], str] = {
    ("describe", "1.0"): "retired by #965; use canonical measured evidence capabilities",
}


class _Registrar(Protocol):
    def register(
        self,
        name: str,
        version: str,
        handler: Callable[..., list[str]],
    ) -> None: ...


class _ProductionRegistrar:
    """Forward only capabilities that are intentionally executable in production."""

    def __init__(self, worker: _Registrar) -> None:
        self._worker = worker

    def register(
        self,
        name: str,
        version: str,
        handler: Callable[..., list[str]],
    ) -> None:
        reason = _RETIRED_CAPABILITIES.get((name, version))
        if reason is not None:
            logger.info(
                "capability_registration_withheld",
                extra={"capability": f"{name}:{version}", "reason": reason},
            )
            return
        self._worker.register(name, version, handler)


def register_production_capabilities(
    worker: _Registrar,
    register_all: Callable[[_Registrar], None],
) -> None:
    """Register the legacy capability catalog through production policy."""

    register_all(_ProductionRegistrar(worker))
