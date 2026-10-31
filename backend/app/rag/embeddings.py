"""
Embedding generator module for Opportunity Intelligence AI.
Provides high-performance, local 384-dimensional embeddings using all-MiniLM-L6-v2.
Supports both ChromaDB's lightweight ONNX DefaultEmbeddingFunction and SentenceTransformers.
"""

import logging
from typing import List
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from app.config import settings

logger = logging.getLogger(__name__)

class RobustEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    High-performance embedding function for all-MiniLM-L6-v2.
    Prefers ChromaDB's ONNX-based DefaultEmbeddingFunction (low memory, no heavy PyTorch GPU overhead),
    falling back to SentenceTransformers if desired.
    """
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from chromadb.utils import embedding_functions
                logger.info("Initializing ONNX all-MiniLM-L6-v2 embedding function...")
                self._engine = embedding_functions.DefaultEmbeddingFunction()
            except Exception as e:
                logger.warning(f"DefaultEmbeddingFunction unavailable ({e}), falling back to SentenceTransformer.")
                from sentence_transformers import SentenceTransformer
                self._engine = SentenceTransformer(self.model_name)
        return self._engine

    def __call__(self, input: Documents) -> Embeddings:
        """Computes normalized embeddings for document chunks."""
        if not input:
            return []
        engine = self._get_engine()
        if hasattr(engine, "__call__") and not hasattr(engine, "encode"):
            return engine(input)
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

embedding_function = RobustEmbeddingFunction()
