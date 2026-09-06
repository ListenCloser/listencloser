from uuid import uuid4

from domain.relation_findings import compose_grounded_relation_finding
from domain.relation_observations import (
    EvidenceRef,
    RelationMeasurement,
    RelationObservation,
    RelationSufficiency,
    SecondsSpanLocator,
)


def _locator(source_version_id, start: float, end: float):
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def _ref(report_version_id, feature: str):
    return EvidenceRef(id=f"{report_version_id}:{feature}")


def _observation(measurements, *, status: str = "supported"):
    source_version_id = uuid4()
    report_version_id = uuid4()
    support_refs = [_ref(report_version_id, item.feature) for item in measurements]
    return RelationObservation(
        subject_locator=_locator(source_version_id, 10.0, 14.0),
        comparison_locator=_locator(source_version_id, 2.0, 6.0),
        support_refs=support_refs,
        measurements=measurements,
        sufficiency=RelationSufficiency(status=status),
        provenance={
            "engine": "perceptual_span_compare",
            "semantic_interpretation_emitted": False,
        },
    )


def _rms(*, relative_delta: float = 0.25, direction: str = "higher"):
    return RelationMeasurement(
        feature="rms",
        unit="linear_amplitude",
        normalization="none",
        subject_value=0.25,
        comparison_value=0.20,
        delta=0.05,
        relative_delta=relative_delta,
        direction=direction,
        subject_frame_count=10,
        comparison_frame_count=10,
    )


def _centroid():
    return RelationMeasurement(
        feature="spectral_centroid",
        unit="hz",
        normalization="none",
        subject_value=1_240.0,
        comparison_value=1_000.0,
        delta=240.0,
        relative_delta=0.24,
        direction="higher",
        subject_frame_count=10,
        comparison_frame_count=10,
    )


def _band_energy():
    return RelationMeasurement(
        feature="relative_band_energy",
        unit="fraction_of_frame_power",
        normalization="per_frame_total_stft_power",
        components=["low", "low_mid", "mid", "high"],
        subject_value=[0.30, 0.20, 0.25, 0.25],
        comparison_value=[0.20, 0.25, 0.30, 0.25],
        delta=[0.10, -0.05, -0.05, 0.0],
        relative_delta=[0.50, -0.20, -0.1667, 0.0],
        direction="mixed",
        subject_frame_count=10,
        comparison_frame_count=10,
    )


def test_supported_relation_preserves_both_spans_and_every_support_ref():
    observation = _observation([_rms(), _centroid()])

    finding = compose_grounded_relation_finding(observation)

    assert finding is not None
    assert finding.source_relation_id == observation.id
    assert finding.subject_locator == observation.subject_locator
    assert finding.comparison_locator == observation.comparison_locator
    assert finding.support_refs == observation.support_refs
    assert [item.support_ref for item in finding.measurements] == observation.support_refs
    assert finding.sufficiency == observation.sufficiency
    assert finding.trust_class == observation.trust_class
    assert finding.maturity == observation.maturity
    assert finding.available_actions == ["focus", "compare", "evidence"]
    assert "2 of 2 supported audio measurements" in finding.headline


def test_scalar_copy_stays_literal_and_uses_relation_measurements():
    observation = _observation([_rms(), _centroid()])

    finding = compose_grounded_relation_finding(observation)

    assert finding is not None
    assert "Median RMS amplitude is 25.0% higher" in finding.evidence_summary
    assert "Median spectral centroid is 240 Hz higher" in finding.evidence_summary
    lowered = finding.evidence_summary.lower()
    for unsupported_term in ("loud", "bright", "energetic", "exciting", "fuller"):
        assert unsupported_term not in lowered


def test_relative_band_energy_uses_percentage_points_without_semantic_adjectives():
    observation = _observation([_band_energy()])

    finding = compose_grounded_relation_finding(observation)

    assert finding is not None
    assert "low: +10.0 pp" in finding.headline
    assert "low-mid: -5.0 pp" in finding.headline
    assert "high: +0.0 pp" in finding.headline
    assert "full" not in finding.headline.lower()
    assert "thin" not in finding.headline.lower()


def test_withheld_or_experimental_relation_emits_no_product_finding():
    withheld = _observation([_rms()], status="withhold")
    experimental = _observation([_rms()], status="experimental")

    assert compose_grounded_relation_finding(withheld) is None
    assert compose_grounded_relation_finding(experimental) is None


def test_inconsistent_support_mapping_fails_closed():
    observation = _observation([_rms(), _centroid()])
    wrong_refs = list(observation.support_refs)
    wrong_refs[0] = EvidenceRef(id=f"{uuid4()}:onset_strength")
    inconsistent = observation.model_copy(update={"support_refs": wrong_refs})

    assert compose_grounded_relation_finding(inconsistent) is None


def test_unexpected_evidence_unit_fails_closed_before_wording():
    observation = _observation([_rms()])
    bad_measurement = observation.measurements[0].model_copy(update={"unit": "db_spl"})
    inconsistent = observation.model_copy(update={"measurements": [bad_measurement]})

    assert compose_grounded_relation_finding(inconsistent) is None


def test_cross_source_comparison_fails_closed_even_if_marked_supported():
    observation = _observation([_rms()])
    comparison = observation.comparison_locator.model_copy(
        update={"source_artifact_version_id": uuid4()}
    )
    inconsistent = observation.model_copy(update={"comparison_locator": comparison})

    assert compose_grounded_relation_finding(inconsistent) is None


def test_unchanged_relation_does_not_claim_similarity():
    unchanged = RelationMeasurement(
        feature="rms",
        unit="linear_amplitude",
        normalization="none",
        subject_value=0.2,
        comparison_value=0.2,
        delta=0.0,
        relative_delta=0.0,
        direction="unchanged",
        subject_frame_count=10,
        comparison_frame_count=10,
    )
    observation = _observation([unchanged])

    finding = compose_grounded_relation_finding(observation)

    assert finding is not None
    assert finding.headline == (
        "The supported comparison found no measurable change in these audio features."
    )
    assert "similar" not in finding.headline.lower()
