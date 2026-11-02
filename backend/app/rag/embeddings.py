"""
Embedding generator module for Opportunity Intelligence AI.
Provides high-performance, local 384-dimensional embeddings using all-MiniLM-L6-v2.
Decoupled from ChromaDB-specific types to support both Neon pgvector and local ChromaDB.
"""

import logging
from typing import List
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

# Standard Python type aliases replacing chromadb.api.types
Documents = List[str]
Embeddings = List[List[float]]

class RobustEmbeddingFunction:
    """
    High-performance embedding function for all-MiniLM-L6-v2.
    Decoupled from ChromaDB types. Uses ONNX or SentenceTransformers
    to compute normalized 384-dimensional float embeddings.
    """
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            # 1. Try lightweight ONNX DefaultEmbeddingFunction from Chroma if installed
            try:
                from chromadb.utils import embedding_functions
                logger.info("Initializing ONNX all-MiniLM-L6-v2 embedding function via chromadb.utils...")
                self._engine = embedding_functions.DefaultEmbeddingFunction()
                return self._engine
            except Exception as e:
                logger.debug(f"chromadb.utils.embedding_functions unavailable: {e}")

            # 2. Try SentenceTransformers
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Initializing SentenceTransformer embedding function...")
                self._engine = SentenceTransformer(self.model_name)
                return self._engine
            except Exception as e:
                logger.debug(f"SentenceTransformer unavailable: {e}")

            # 3. Direct ONNX Runtime fallback
            try:
                import os
                import onnxruntime as ort
                from tokenizers import Tokenizer

                cache_dir = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx")
                model_path = os.path.join(cache_dir, "model.onnx")
                tok_path = os.path.join(cache_dir, "tokenizer.json")
                if os.path.exists(model_path) and os.path.exists(tok_path):
                    logger.info("Initializing standalone ONNX runtime embedding engine...")
                    class StandaloneONNXEngine:
                        def __init__(self, m_path, t_path):
                            self.tokenizer = Tokenizer.from_file(t_path)
                            self.session = ort.InferenceSession(m_path)

                        def __call__(self, texts: List[str]) -> List[List[float]]:
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

                    self._engine = StandaloneONNXEngine(model_path, tok_path)
                    return self._engine
            except Exception as e:
                logger.debug(f"Standalone ONNX fallback unavailable: {e}")

            raise RuntimeError("No compatible embedding engine found (onnx / sentence-transformers).")

        return self._engine

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
