"""Analysis V3 evaluation aliases for the production-owned descriptor math.

#455/#468 originally introduced these functions under ``evaluation``. M1 moves
the validated implementation to :mod:`perceptual_evidence`; keeping these
aliases means the existing synthetic/stability harnesses continue exercising
the exact production math instead of a forked copy.
"""

from perceptual_evidence import (
    extract_measured_perceptual_series as extract_baseline_perceptual_evidence,
    MeasuredFeatureSeries as FeatureSeries,
    onset_strength_series,
    relative_band_energy_series,
    rms_series,
    spectral_centroid_series,
)

__all__ = [
    "FeatureSeries",
    "extract_baseline_perceptual_evidence",
    "onset_strength_series",
    "relative_band_energy_series",
    "rms_series",
    "spectral_centroid_series",
]
