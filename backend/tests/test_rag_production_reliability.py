"""
Tests for Production RAG Reliability:
- Serverless ONNX embedding engine caching and on-demand streaming download.
- SHA-256 archive checksum verification and anti-path-traversal protection.
- Download timeouts, thread safety, and warm in-memory session reuse.
- 384-dimensional unit-norm embedding generation.
- Graceful relational keyword fallback when vector search fails.
- Preservation of official opportunity metadata during fallback.
"""

import io
import os
import shutil
import socket
import sys
import tarfile
import tempfile
import threading
import urllib.error
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from app.rag.embeddings import (
    RobustEmbeddingFunction,
    download_and_extract_model,
    get_model_cache_dir,
    is_serverless_environment,
    embedding_function,
    REQUIRED_ONNX_FILES
)
from app.agent.tools import (
    SearchOpportunitiesInput,
    tool_search_opportunities,
    _search_opportunities_relational_fallback
)


def _create_dummy_tar_archive(entries=None, malicious_entry=None):
    """Helper to generate an in-memory tar.gz archive for tests."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if entries:
            for name, content in entries.items():
                data = content.encode("utf-8") if isinstance(content, str) else content
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        if malicious_entry:
            name, content = malicious_entry
            data = content.encode("utf-8") if isinstance(content, str) else content
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


class MockHTTPResponse:
    def __init__(self, data: bytes):
        self._data = io.BytesIO(data)

    def read(self, chunk_size=-1):
        return self._data.read(chunk_size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# 1. Model already cached
def test_model_already_cached(tmp_path):
    cache_dir = tmp_path / "onnx_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "model.onnx").write_text("dummy model")
    (cache_dir / "tokenizer.json").write_text("dummy tokenizer")

    with patch.dict(os.environ, {"OI_ONNX_CACHE_DIR": str(cache_dir)}):
        with patch("urllib.request.urlopen") as mock_urlopen:
            resolved_dir = get_model_cache_dir()
            assert resolved_dir == str(cache_dir)
            mock_urlopen.assert_not_called()


# 2. Model missing and downloaded successfully
def test_model_missing_and_downloaded_successfully(tmp_path):
    target_dir = tmp_path / "extracted_model"
    archive_data = _create_dummy_tar_archive(entries={
        "onnx/model.onnx": "mock binary model content",
        "onnx/tokenizer.json": '{"version": "1.0", "mock": true}',
        "onnx/config.json": '{"dim": 384}'
    })

    import hashlib
    correct_sha256 = hashlib.sha256(archive_data).hexdigest()

    with patch("urllib.request.urlopen", return_value=MockHTTPResponse(archive_data)):
        download_and_extract_model(
            target_dir=str(target_dir),
            expected_sha256=correct_sha256
        )

    assert (target_dir / "model.onnx").exists()
    assert (target_dir / "tokenizer.json").exists()
    assert (target_dir / "model.onnx").read_text() == "mock binary model content"


# 3. Invalid checksum raises ValueError and cleans up
def test_model_download_invalid_checksum(tmp_path):
    target_dir = tmp_path / "corrupted_model"
    archive_data = _create_dummy_tar_archive(entries={
        "onnx/model.onnx": "tampered content",
        "onnx/tokenizer.json": "{}"
    })

    with patch("urllib.request.urlopen", return_value=MockHTTPResponse(archive_data)):
        with pytest.raises(ValueError) as excinfo:
            download_and_extract_model(
                target_dir=str(target_dir),
                expected_sha256="0000000000000000000000000000000000000000000000000000000000000000"
            )

    assert "checksum mismatch" in str(excinfo.value).lower()
    assert not (target_dir / "model.onnx").exists()


# 4. Invalid or malicious archive paths rejected (anti-path-traversal)
def test_model_archive_malicious_path_traversal(tmp_path):
    target_dir = tmp_path / "secure_target"
    archive_data = _create_dummy_tar_archive(
        entries={"onnx/tokenizer.json": "{}"},
        malicious_entry=("../evil.sh", "echo 'pwned'")
    )

    import hashlib
    correct_sha256 = hashlib.sha256(archive_data).hexdigest()

    with patch("urllib.request.urlopen", return_value=MockHTTPResponse(archive_data)):
        with pytest.raises(ValueError) as excinfo:
            download_and_extract_model(
                target_dir=str(target_dir),
                expected_sha256=correct_sha256
            )

    assert "malicious" in str(excinfo.value).lower() or "insecure" in str(excinfo.value).lower()
    assert not (tmp_path / "evil.sh").exists()


# 5. Download timeout handling
def test_model_download_timeout(tmp_path):
    target_dir = tmp_path / "timeout_target"

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(socket.timeout("timed out"))):
        with pytest.raises(urllib.error.URLError):
            download_and_extract_model(target_dir=str(target_dir), timeout=1)

    assert not (target_dir / "model.onnx").exists()


# 6. Concurrent model initialization thread safety
def test_concurrent_model_initialization(tmp_path):
    target_dir = tmp_path / "concurrent_model"
    archive_data = _create_dummy_tar_archive(entries={
        "onnx/model.onnx": "concurrent safe model",
        "onnx/tokenizer.json": '{"type": "mock"}'
    })
    import hashlib
    correct_sha256 = hashlib.sha256(archive_data).hexdigest()

    call_count = [0]
    def counted_urlopen(*args, **kwargs):
        call_count[0] += 1
        return MockHTTPResponse(archive_data)

    errors = []
    def worker():
        try:
            download_and_extract_model(
                target_dir=str(target_dir),
                expected_sha256=correct_sha256
            )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    with patch("urllib.request.urlopen", side_effect=counted_urlopen):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(errors) == 0
    assert (target_dir / "model.onnx").exists()


# 7. ONNX session reuse for warm invocations
def test_onnx_session_reuse():
    RobustEmbeddingFunction.reset_cached_engine()
    ef = RobustEmbeddingFunction()
    engine_1 = ef._get_engine()
    engine_2 = ef._get_engine()
    assert engine_1 is engine_2


# 8. Correct 384-dimensional normalized embeddings
def test_correct_384_dimensional_embeddings():
    queries = [
        "Higher Education Financing undergraduate scholarship in Kenya",
        "Safaricom PLC industrial attachment 2026"
    ]
    vectors = embedding_function(queries)
    assert len(vectors) == 2
    for vec in vectors:
        assert len(vec) == 384
        # Verify L2 normalization (norm == 1.0)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.01


# 9. Vector retrieval success
def test_vector_retrieval_success():
    res = tool_search_opportunities(SearchOpportunitiesInput(
        query="scholarship undergraduate Kenya",
        top_k=3
    ))
    assert res["status"] == "success"
    assert res["retrieval_mode"] == "vector_semantic"
    assert len(res["results"]) > 0
    first = res["results"][0]
    assert "opportunity_id" in first
    assert "official_url" in first
    assert first["official_url"].startswith("http")


# 10. Vector retrieval failure followed by graceful relational fallback
def test_vector_retrieval_failure_relational_fallback():
    with patch("app.agent.tools.get_vector_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.search.side_effect = RuntimeError("pgvector: HNSW connection terminated unexpectedly")
        mock_store.return_value = mock_instance

        res = tool_search_opportunities(SearchOpportunitiesInput(
            query="Safaricom technology attachment",
            top_k=2
        ))

        assert res["status"] == "success"
        assert res["retrieval_mode"] == "relational_fallback"
        assert len(res["results"]) > 0
        safaricom_result = next((r for r in res["results"] if "safaricom" in r["title"].lower()), None)
        assert safaricom_result is not None
        assert safaricom_result["provider"] == "Safaricom PLC"
        assert safaricom_result["official_url"] == "https://www.safaricom.co.ke/careers"
        assert safaricom_result["verification_status"] == "verified"


# 11. Relational fallback returning no results when query doesn't match
def test_relational_fallback_no_results():
    with patch("app.agent.tools.get_vector_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.search.side_effect = RuntimeError("pgvector offline")
        mock_store.return_value = mock_instance

        res = tool_search_opportunities(SearchOpportunitiesInput(
            query="quantum_teleportation_astrophysics_xyz_nonexistent",
            category="NonExistentCategory",
            top_k=2
        ))

        assert res["status"] == "not_found"
        assert res["retrieval_mode"] == "relational_fallback"
        assert res["results"] == []


# 12. Preservation of official opportunity metadata during fallback
def test_preservation_of_official_opportunity_metadata():
    with patch("app.agent.tools.get_vector_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.search.side_effect = RuntimeError("Embedding engine unavailable")
        mock_store.return_value = mock_instance

        res = tool_search_opportunities(SearchOpportunitiesInput(
            query="HEF scholarship Kenya",
            top_k=1
        ))

        assert res["status"] == "success"
        assert res["retrieval_mode"] == "relational_fallback"
        assert len(res["results"]) >= 1

        opp = res["results"][0]
        # Verify required official fields are preserved
        assert opp["opportunity_id"] is not None
        assert len(opp["title"]) > 0
        assert len(opp["provider"]) > 0
        assert opp["official_url"].startswith("https://")
        assert opp["verification_status"] == "verified"
        assert opp["deadline"] is not None
        assert opp["similarity_score"] >= 0.50
        assert opp["retrieval_mode"] == "relational_fallback"
