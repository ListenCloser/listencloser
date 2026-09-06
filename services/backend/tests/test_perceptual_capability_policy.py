from domain.capability_policy import capability_policy, is_product_evidence


def test_perceptual_series_is_product_evidence_but_not_directly_exposed() -> None:
    policy = capability_policy("perceptual_series")

    assert policy["status"] == "production"
    assert policy["input"] == "audio"
    assert policy["engine"] == "librosa"
    assert policy["exposure"] == {
        "inspector": False,
        "annotations": False,
        "ask": False,
    }
    assert is_product_evidence("perceptual_series") is True
    assert "within-work" in policy["validated_domain"]
    assert "RMS" in policy["notes"]
