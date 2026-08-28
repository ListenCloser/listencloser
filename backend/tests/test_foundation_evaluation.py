"""Deterministic unit tests for the foundation model evaluation harness."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest
from backend.evaluation.analysis_v3.foundation.metrics.retrieval import (
    compute_mrr,
    compute_recall_at_k,
    compute_similarity_matrix,
    cosine_similarity,
    evaluate_cross_representation,
    evaluate_retrieval,
    retrieve_nearest_neighbors,
)
from backend.evaluation.analysis_v3.foundation.metrics.runtime import (
    OperationalResult,
    RuntimeMetrics,
    generate_synthetic_audio,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert cosine_similarity(a, b) == 0.0

    def test_similar_vectors(self):
        a = np.array([1.0, 1.0, 0.0])
        b = np.array([1.0, 0.9, 0.1])
        sim = cosine_similarity(a, b)
        assert 0.9 < sim < 1.0


class TestComputeSimilarityMatrix:
    def test_basic(self):
        embeddings = {
            "a": np.array([1.0, 0.0]),
            "b": np.array([0.0, 1.0]),
            "c": np.array([1.0, 1.0]),
        }
        matrix = compute_similarity_matrix(embeddings)
        assert matrix.shape == (3, 3)
        assert matrix[0, 0] == pytest.approx(1.0)
        assert matrix[1, 1] == pytest.approx(1.0)
        assert matrix[2, 2] == pytest.approx(1.0)
        assert matrix[0, 1] == pytest.approx(0.0)
        assert matrix[0, 2] > 0.0

    def test_symmetry(self):
        embeddings = {
            "a": np.array([1.0, 0.0]),
            "b": np.array([0.0, 1.0]),
        }
        matrix = compute_similarity_matrix(embeddings)
        assert matrix[0, 1] == pytest.approx(matrix[1, 0])


class TestRetrieveNearestNeighbors:
    def test_basic(self):
        embeddings = {
            "query": np.array([1.0, 0.0]),
            "similar": np.array([0.9, 0.1]),
            "different": np.array([0.0, 1.0]),
        }
        neighbors = retrieve_nearest_neighbors("query", embeddings)
        assert len(neighbors) == 2
        assert neighbors[0][0] == "similar"
        assert neighbors[1][0] == "different"

    def test_exclude_ids(self):
        embeddings = {
            "query": np.array([1.0, 0.0]),
            "a": np.array([0.9, 0.1]),
            "b": np.array([0.0, 1.0]),
        }
        neighbors = retrieve_nearest_neighbors("query", embeddings, exclude_ids={"a"})
        assert len(neighbors) == 1
        assert neighbors[0][0] == "b"

    def test_top_k(self):
        embeddings = {
            "query": np.array([1.0, 0.0]),
            "a": np.array([0.9, 0.1]),
            "b": np.array([0.8, 0.2]),
            "c": np.array([0.0, 1.0]),
        }
        neighbors = retrieve_nearest_neighbors("query", embeddings, top_k=2)
        assert len(neighbors) == 2


class TestComputeRecallAtK:
    def test_perfect(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert compute_recall_at_k(retrieved, relevant, 3) == pytest.approx(1.0)

    def test_partial(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "d"}
        assert compute_recall_at_k(retrieved, relevant, 3) == pytest.approx(0.5)

    def test_none(self):
        retrieved = ["a", "b", "c"]
        relevant = {"d", "e"}
        assert compute_recall_at_k(retrieved, relevant, 3) == pytest.approx(0.0)

    def test_empty_relevant(self):
        retrieved = ["a", "b", "c"]
        relevant: set[str] = set()
        assert compute_recall_at_k(retrieved, relevant, 3) == 0.0


class TestComputeMRR:
    def test_first_rank(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a"}
        assert compute_mrr(retrieved, relevant) == pytest.approx(1.0)

    def test_second_rank(self):
        retrieved = ["a", "b", "c"]
        relevant = {"b"}
        assert compute_mrr(retrieved, relevant) == pytest.approx(0.5)

    def test_third_rank(self):
        retrieved = ["a", "b", "c"]
        relevant = {"c"}
        assert compute_mrr(retrieved, relevant) == pytest.approx(1.0 / 3.0)

    def test_not_found(self):
        retrieved = ["a", "b", "c"]
        relevant = {"d"}
        assert compute_mrr(retrieved, relevant) == pytest.approx(0.0)

    def test_empty_relevant(self):
        retrieved = ["a", "b", "c"]
        relevant: set[str] = set()
        assert compute_mrr(retrieved, relevant) == 0.0


class TestEvaluateRetrieval:
    def test_basic(self):
        embeddings = {
            "query": np.array([1.0, 0.0]),
            "relevant": np.array([0.9, 0.1]),
            "other": np.array([0.0, 1.0]),
        }
        result = evaluate_retrieval("query", embeddings, {"relevant"})
        assert result.query_id == "query"
        assert result.retrieved_ids[0] == "relevant"
        assert result.recall_at_1 == pytest.approx(1.0)
        assert result.mrr == pytest.approx(1.0)


class TestEvaluateCrossRepresentation:
    def test_basic(self):
        audio_embeddings = {
            "a": np.array([1.0, 0.0]),
            "b": np.array([0.0, 1.0]),
        }
        symbolic_embeddings = {
            "a": np.array([0.9, 0.1]),
            "b": np.array([0.1, 0.9]),
        }
        matched_pairs = [("a", "a"), ("b", "b")]
        result = evaluate_cross_representation(audio_embeddings, symbolic_embeddings, matched_pairs)
        assert result["recall_at_1"] == pytest.approx(1.0)
        assert result["mrr"] == pytest.approx(1.0)


class TestGenerateSyntheticAudio:
    def test_duration(self):
        audio = generate_synthetic_audio(duration_seconds=5.0, sample_rate=24000)
        assert len(audio) == 5 * 24000

    def test_dtype(self):
        audio = generate_synthetic_audio()
        assert audio.dtype == np.float32

    def test_range(self):
        audio = generate_synthetic_audio()
        assert np.max(np.abs(audio)) <= 1.0


class TestManifestParsing:
    def test_diversity_probe(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "manifests",
            "diversity_probe.json",
        )
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            assert "probes" in manifest
            assert len(manifest["probes"]) > 0
            for probe in manifest["probes"]:
                assert "id" in probe
                assert "frequency_hz" in probe
                assert "duration_seconds" in probe

    def test_product_queries(self):
        manifest_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "manifests",
            "product_queries.json",
        )
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            assert "queries" in manifest
            assert len(manifest["queries"]) > 0
            for query in manifest["queries"]:
                assert "id" in query
                assert "text" in query


class TestResultSerialization:
    def test_operational_result(self):
        result = OperationalResult(
            candidate="test",
            model_id="test/model",
            install_success=True,
            load_success=True,
        )
        assert result.candidate == "test"
        assert result.install_success is True

    def test_runtime_metrics(self):
        metrics = RuntimeMetrics(
            latency_seconds=1.0,
            audio_duration_seconds=10.0,
            device="cpu",
        )
        assert metrics.latency_seconds == 1.0
        assert metrics.device == "cpu"


class TestAdapterUnsupportedCapability:
    def test_unsupported_text(self):
        from backend.evaluation.analysis_v3.foundation.adapters.base import FoundationModelAdapter

        class AudioOnlyAdapter(FoundationModelAdapter):
            name = "test"
            model_id = "test/model"

            def load(self):
                pass

            def embed_audio(self, audio, sample_rate):
                from backend.evaluation.analysis_v3.foundation.adapters.base import EmbeddingResult

                return EmbeddingResult(vector=np.array([1.0]))

            def metadata(self):
                from backend.evaluation.analysis_v3.foundation.adapters.base import ModelMetadata

                return ModelMetadata(candidate="test", model_id="test/model")

        adapter = AudioOnlyAdapter()
        assert adapter.supports_text() is False
        assert adapter.embed_text("test") is None
