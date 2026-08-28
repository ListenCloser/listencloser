"""BS-RoFormer adapter for evaluation-only feasibility checks.

The upstream architecture package does not provide a production-ready official
checkpoint through the path evaluated here. Do not instantiate random weights
and treat them as a model result. Until a compatible, licensed checkpoint is
wired explicitly, this adapter must fail closed.
"""

from __future__ import annotations

import numpy as np

from .base import SeparationAdapter, SeparationMetadata, SeparationResult


class BSRoFormerAdapter(SeparationAdapter):
    name = "bs_roformer"
    model_id = "lucidrains/BS-RoFormer"

    def __init__(self, device: str = "cpu"):
        super().__init__(device)

    def load(self) -> None:
        if self._loaded:
            return
        raise RuntimeError(
            "BS-RoFormer is REVISIT in this evaluation: the evaluated Python 3.9 "
            "environment is incompatible with the package path attempted, and no "
            "verified compatible pretrained checkpoint is wired. Refusing to "
            "instantiate an untrained/random architecture as evaluation evidence."
        )

    def separate(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> SeparationResult:
        return SeparationResult(
            error=(
                "BS-RoFormer unavailable: no verified compatible pretrained "
                "checkpoint is wired for this evaluation environment"
            )
        )

    def metadata(self) -> SeparationMetadata:
        return SeparationMetadata(
            candidate="bs_roformer",
            model_id=self.model_id,
            code_license="MIT",
            weight_license=None,
            upstream_repo="https://github.com/lucidrains/BS-RoFormer",
            supports_vocals=True,
            supports_drums=True,
            supports_bass=True,
            supports_other=True,
            num_stems=4,
            notes=(
                "REVISIT: architecture package path was incompatible with Python "
                "3.9 and no verified compatible pretrained checkpoint is wired. "
                "Weight license must be recorded from the exact future checkpoint, "
                "not inferred from the code repository."
            ),
        )
