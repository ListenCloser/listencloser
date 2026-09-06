from __future__ import annotations

from domain.capabilities import _is_product_melody_evidence, _product_melody_findings


def test_product_melody_findings_admit_only_registered_product_evidence() -> None:
    findings = [
        {"kind": "melody_register_peak", "claim": "High point"},
        {"kind": "melody_large_leap", "claim": "Large leap"},
        {"kind": "melody_contour_arch", "claim": "Arch"},
        {"kind": "melody_contour_static", "claim": "Static"},
        {"kind": "melody_contour_inverted_arch", "claim": "Inverted arch"},
        {"kind": "melody_activity_dense", "claim": "Dense passage"},
    ]

    admitted = _product_melody_findings(findings)

    assert [finding["kind"] for finding in admitted] == [
        "melody_register_peak",
        "melody_activity_dense",
    ]


def test_melody_motif_remains_evaluation_only_at_persistence_boundary() -> None:
    assert not _is_product_melody_evidence("melody_motif")


def test_unregistered_melody_kind_fails_closed_without_raising() -> None:
    assert not _is_product_melody_evidence("melody_contour_static")
    assert not _is_product_melody_evidence("melody_contour_inverted_arch")


def test_registered_experimental_melody_kind_remains_persistable() -> None:
    assert _is_product_melody_evidence("melody_register_low")
    assert _is_product_melody_evidence("melody_contour_descending")
