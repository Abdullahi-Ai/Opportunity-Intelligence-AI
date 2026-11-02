"""
Embedding generator module for Opportunity Intelligence AI.
Provides high-performance, local 384-dimensional embeddings using all-MiniLM-L6-v2.
Decoupled from ChromaDB-specific types to support both Neon pgvector and local ChromaDB.

Includes robust serverless cold-start caching, on-demand streaming download with
trusted SHA-256 integrity verification, path-traversal-safe extraction, and in-memory
session reuse for warm Vercel/Lambda invocations.
"""

import hashlib
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from typing import List, Optional

import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

# Standard Python type aliases replacing chromadb.api.types
Documents = List[str]
Embeddings = List[List[float]]

# Official, independently established all-MiniLM-L6-v2 ONNX model distribution
MODEL_DOWNLOAD_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
EXPECTED_ARCHIVE_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
DOWNLOAD_TIMEOUT_SECONDS = 45
REQUIRED_ONNX_FILES = ["model.onnx", "tokenizer.json"]

# Global synchronization and in-memory engine cache for warm serverless execution
_ENGINE_LOCK = threading.Lock()
_DOWNLOAD_LOCK = threading.Lock()
_CACHED_ENGINE = None


def is_serverless_environment() -> bool:
    """Detects if the application is running inside Vercel or AWS Lambda serverless runtime."""
    return bool(
        os.environ.get("VERCEL")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("LAMBDA_TASK_ROOT")
    )


def get_model_cache_dir() -> str:
    """
    Resolves the active ONNX model directory.
    - Honors explicit OI_ONNX_CACHE_DIR environment variable if provided.
    - Checks standard local development path (~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx).
    - In serverless environments (or when home is read-only), uses /tmp for ephemeral caching.
    """
    env_dir = os.environ.get("OI_ONNX_CACHE_DIR")
    if env_dir:
        return env_dir

    local_dev_dir = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx")
    if os.path.exists(os.path.join(local_dev_dir, "model.onnx")) and os.path.exists(os.path.join(local_dev_dir, "tokenizer.json")):
        return local_dev_dir

    serverless_tmp_dir = os.path.join(tempfile.gettempdir(), "oi_cache", "onnx_models", "all-MiniLM-L6-v2", "onnx")
    if os.path.exists(os.path.join(serverless_tmp_dir, "model.onnx")) and os.path.exists(os.path.join(serverless_tmp_dir, "tokenizer.json")):
        return serverless_tmp_dir

    if is_serverless_environment():
        return serverless_tmp_dir

    # In local environments, attempt creating local_dev_dir if writable
    try:
        os.makedirs(local_dev_dir, exist_ok=True)
        return local_dev_dir
    except (OSError, PermissionError):
        return serverless_tmp_dir


def _is_safe_tar_member(member: tarfile.TarInfo, dest_dir: str) -> bool:
    """
    Validates that an archive member does not execute directory traversal
    or exploit insecure links outside the intended destination directory.
    """
    if member.islnk() or member.issym():
        return False
    name = member.name.replace("\\", "/")
    if os.path.isabs(name) or name.startswith("/") or name.startswith("../") or "/../" in name or name == "..":
        return False
    dest_abs = os.path.abspath(dest_dir)
    target_abs = os.path.abspath(os.path.join(dest_dir, member.name))
    if not (target_abs == dest_abs or target_abs.startswith(dest_abs + os.sep)):
        return False
    return True


def download_and_extract_model(
    target_dir: str,
    download_url: str = MODEL_DOWNLOAD_URL,
    expected_sha256: str = EXPECTED_ARCHIVE_SHA256,
    timeout: int = DOWNLOAD_TIMEOUT_SECONDS
) -> None:
    """
    Downloads and extracts the official ONNX model archive.
    - Synchronized via _DOWNLOAD_LOCK to prevent concurrent downloads/extractions.
    - Streams download in 64KB chunks to minimize memory consumption.
    - Verifies archive integrity using independent SHA-256 checksum.
    - Inspects archive members to prevent path traversal attacks.
    - Extracts atomically to staging directory before placing files in target_dir.
    - Deletes intermediate archive to preserve ephemeral disk space.
    """
    with _DOWNLOAD_LOCK:
        if all(os.path.exists(os.path.join(target_dir, f)) for f in REQUIRED_ONNX_FILES):
            return

        temp_dir = tempfile.gettempdir()
        os.makedirs(target_dir, exist_ok=True)
        temp_archive_path = os.path.join(
            temp_dir, f"oi_model_{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}.tar.gz.tmp"
        )
        staging_dir = os.path.join(
            temp_dir, f"oi_staging_{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}"
        )

        try:
            logger.info("Streaming official ONNX model archive from %s...", download_url)
            sha256_hasher = hashlib.sha256()

            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "OpportunityIntelligenceAI/1.0"}
            )

            with urllib.request.urlopen(req, timeout=timeout) as response, open(temp_archive_path, "wb") as out_file:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    sha256_hasher.update(chunk)
                    out_file.write(chunk)

            computed_sha256 = sha256_hasher.hexdigest().lower()
            if computed_sha256 != expected_sha256.lower():
                raise ValueError(
                    f"Model archive checksum mismatch: expected {expected_sha256}, got {computed_sha256}."
                )

            logger.info("Model archive checksum verified successfully. Extracting safely...")
            os.makedirs(staging_dir, exist_ok=True)

            with tarfile.open(temp_archive_path, mode="r:gz") as tar:
                for member in tar.getmembers():
                    if not _is_safe_tar_member(member, staging_dir):
                        raise ValueError(f"Malicious or insecure path detected in archive: {member.name}")

                if sys.version_info >= (3, 12):
                    tar.extractall(path=staging_dir, filter="data")
                else:
                    tar.extractall(path=staging_dir)

            source_dir = os.path.join(staging_dir, "onnx")
            if not (os.path.exists(source_dir) and os.path.isdir(source_dir)):
                source_dir = staging_dir

            for req_file in REQUIRED_ONNX_FILES:
                if not os.path.exists(os.path.join(source_dir, req_file)):
                    raise FileNotFoundError(f"Extracted archive missing required model file: {req_file}")

            for item in os.listdir(source_dir):
                src_path = os.path.join(source_dir, item)
                dst_path = os.path.join(target_dir, item)
                if os.path.isfile(src_path):
                    tmp_dst = dst_path + f".tmp_{os.getpid()}_{threading.get_ident()}"
                    shutil.copy2(src_path, tmp_dst)
                    os.replace(tmp_dst, dst_path)

            logger.info("ONNX model ready in %s.", target_dir)
        finally:
            if os.path.exists(temp_archive_path):
                try:
                    os.remove(temp_archive_path)
                except OSError:
                    pass
            if os.path.exists(staging_dir):
                try:
                    shutil.rmtree(staging_dir)
                except OSError:
                    pass


class StandaloneONNXEngine:
    """
    Direct ONNX Runtime embedding engine for all-MiniLM-L6-v2.
    Computes normalized 384-dimensional dense vectors with zero torch/transformers dependencies.
    """
    def __init__(self, m_path: str, t_path: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(t_path)
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(m_path, sess_options=opts)

    def __call__(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        encoded = [self.tokenizer.encode(t) for t in texts]
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        out = self.session.run(None, {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids
        })[0]

        mask_exp = np.broadcast_to(np.expand_dims(attention_mask, -1), out.shape)
        emb = np.sum(out * mask_exp, 1) / np.clip(mask_exp.sum(1), a_min=1e-9, a_max=None)
        norm = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / np.clip(norm, a_min=1e-9, a_max=None)
        return emb.tolist()


class RobustEmbeddingFunction:
    """
    High-performance embedding function for all-MiniLM-L6-v2.
    Decoupled from ChromaDB types. Uses ONNX or SentenceTransformers
    to compute normalized 384-dimensional float embeddings.
    """
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._engine = None

    @classmethod
    def reset_cached_engine(cls):
        """Clears the global cached engine (used for testing and lifecycle management)."""
        global _CACHED_ENGINE
        with _ENGINE_LOCK:
            _CACHED_ENGINE = None

    def _get_engine(self):
        global _CACHED_ENGINE
        if _CACHED_ENGINE is not None:
            return _CACHED_ENGINE

        with _ENGINE_LOCK:
            if _CACHED_ENGINE is not None:
                return _CACHED_ENGINE

            # 1. Try lightweight ONNX DefaultEmbeddingFunction from Chroma if installed
            try:
                from chromadb.utils import embedding_functions
                logger.info("Initializing ONNX all-MiniLM-L6-v2 embedding function via chromadb.utils...")
                _CACHED_ENGINE = embedding_functions.DefaultEmbeddingFunction()
                return _CACHED_ENGINE
            except Exception as e:
                logger.debug(f"chromadb.utils.embedding_functions unavailable: {e}")

            # 2. Try SentenceTransformers
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Initializing SentenceTransformer embedding function...")
                _CACHED_ENGINE = SentenceTransformer(self.model_name)
                return _CACHED_ENGINE
            except Exception as e:
                logger.debug(f"SentenceTransformer unavailable: {e}")

            # 3. Direct standalone ONNX Runtime fallback
            try:
                target_cache_dir = get_model_cache_dir()
                model_path = os.path.join(target_cache_dir, "model.onnx")
                tok_path = os.path.join(target_cache_dir, "tokenizer.json")

                if not (os.path.exists(model_path) and os.path.exists(tok_path)):
                    with _DOWNLOAD_LOCK:
                        # Double-check inside lock
                        if not (os.path.exists(model_path) and os.path.exists(tok_path)):
                            logger.info("Model files missing at %s; initiating download...", target_cache_dir)
                            download_and_extract_model(target_cache_dir)

                if os.path.exists(model_path) and os.path.exists(tok_path):
                    logger.info("Initializing standalone ONNX runtime embedding engine from %s...", target_cache_dir)
                    _CACHED_ENGINE = StandaloneONNXEngine(model_path, tok_path)
                    return _CACHED_ENGINE
            except Exception as e:
                logger.error(f"Standalone ONNX fallback initialization failed: {e}")
                raise

            raise RuntimeError("No compatible embedding engine found (onnx / sentence-transformers).")

    def __call__(self, input: Documents) -> Embeddings:
        """Computes normalized embeddings for document chunks."""
        if not input:
            return []
        engine = self._get_engine()
        if hasattr(engine, "__call__") and not hasattr(engine, "encode"):
            result = engine(input)
            if isinstance(result, np.ndarray):
                return result.tolist()
            return result
        elif hasattr(engine, "encode"):
            embeddings = engine.encode(
                input,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True
            )
            return embeddings.tolist()
        else:
            raise RuntimeError("No compatible embedding engine found.")

    def embed_query(self, input: Documents) -> Embeddings:
        """ChromaDB backward compatibility interface for querying."""
        return self(input)

    def embed_with_retries(self, input: Documents, **kwargs) -> Embeddings:
        """ChromaDB backward compatibility interface with retries."""
        return self(input)

    def name(self) -> str:
        return "all-MiniLM-L6-v2"


embedding_function = RobustEmbeddingFunction()
