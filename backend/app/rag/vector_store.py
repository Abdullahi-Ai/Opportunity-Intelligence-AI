"""
ChromaDB Persistent Vector Store interface for Opportunity Intelligence AI.
Provides vector upserts, semantic similarity search, metadata filtering, and collection stats.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.rag.embeddings import embedding_function
from app.rag.document_loader import OpportunityChunk

class VectorStore:
    def __init__(
        self,
        persist_dir: str = settings.CHROMA_PERSIST_DIRECTORY,
        collection_name: str = settings.CHROMA_COLLECTION_NAME
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize persistent chroma client
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_function,
            metadata={"description": "Verified Kenya educational and career opportunities"}
        )

    def upsert_chunks(self, chunks: List[OpportunityChunk]) -> int:
        """
        Upserts opportunity chunks into ChromaDB to prevent duplication.
        Returns the number of chunks added/updated.
        """
        if not chunks:
            return 0

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        # ChromaDB upsert handles both insertion and updates idempotently
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 4,
        category: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity search with optional metadata filtering.
        Calculates cosine similarity score from ChromaDB distances.
        """
        where_filter = {}
        if category:
            where_filter["category"] = category
        if status:
            where_filter["status"] = status

        kwargs = {
            "query_texts": [query],
            "n_results": min(top_k, max(1, self.collection.count()))
        }
        if where_filter:
            # If multiple filters, use $and
            if len(where_filter) > 1:
                kwargs["where"] = {"$and": [{k: v} for k, v in where_filter.items()]}
            else:
                kwargs["where"] = where_filter

        if self.collection.count() == 0:
            return []

        results = self.collection.query(**kwargs)

        formatted_results = []
        if results and results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                doc_text = results["documents"][0][i]
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                chunk_id = results["ids"][0][i] if results["ids"] else ""
                distance = results["distances"][0][i] if results.get("distances") else 0.0

                # Cosine distance to similarity score conversion
                similarity_score = max(0.0, 1.0 - (distance / 2.0))

                formatted_results.append({
                    "chunk_id": chunk_id,
                    "content": doc_text,
                    "metadata": metadata,
                    "similarity_score": round(similarity_score, 4),
                    "distance": round(distance, 4)
                })

        return formatted_results

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about the vector collection."""
        return {
            "collection_name": self.collection_name,
            "total_chunks": self.collection.count(),
            "persist_directory": self.persist_dir
        }

    def clear(self):
        """Clears the collection for re-indexing."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_function,
            metadata={"description": "Verified Kenya educational and career opportunities"}
        )

# Module-level vector store singleton
vector_store = VectorStore()
