import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy import (
    Column, String, Integer, Text, Table, MetaData, select, func, or_, and_, text
)
from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings
from app.rag.embeddings import embedding_function
from app.rag.document_loader import OpportunityChunk

logger = logging.getLogger(__name__)

class PGVectorType(UserDefinedType):
    """
    SQLAlchemy Type for pgvector's vector(N) column.
    Translates Python float lists to vector syntax and back.
    In SQLite, serializes to/from JSON text transparently for local parity testing.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"VECTOR({self.dim})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, np.ndarray):
                value = value.tolist()
            if isinstance(value, (list, tuple)):
                if dialect.name == "sqlite":
                    return json.dumps([float(x) for x in value])
                return "[" + ",".join(str(float(x)) for x in value) + "]"
            return value
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned.startswith("[") and cleaned.endswith("]"):
                    items = cleaned[1:-1].split(",")
                    return [float(x.strip()) for x in items if x.strip()]
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, list):
                        return [float(x) for x in parsed]
                except Exception:
                    pass
            elif isinstance(value, (list, tuple)):
                return [float(x) for x in value]
            return value
        return process

PgBase = declarative_base()

class OpportunityChunkRecord(PgBase):
    __tablename__ = "opportunity_chunks"

    chunk_id = Column(String(150), primary_key=True)
    opportunity_id = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    provider = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    section_title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    official_url = Column(String(500), nullable=False)
    application_deadline = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="Active", index=True)
    verification_status = Column(String(50), nullable=False, default="UNVERIFIED")
    metadata_json = Column(Text, nullable=False)
    embedding = Column(PGVectorType(384), nullable=True)

class PgVectorStore:
    """
    Standalone pgvector-compatible Vector Store.
    Provides identical search, upsert, filtering, and scoring interfaces
    as ChromaDB, backed by SQLAlchemy.
    """
    def __init__(self, engine=None, session_factory=None):
        from app.db.session import engine as default_engine, SessionLocal as default_session_factory
        self.engine = engine or default_engine
        self.session_factory = session_factory or default_session_factory
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        if self.engine.dialect.name == "sqlite":
            PgBase.metadata.create_all(bind=self.engine)

    def upsert_chunks(self, chunks: List[OpportunityChunk]) -> int:
        if not chunks:
            return 0

        session = self.session_factory()
        try:
            texts_to_embed = []
            embed_indices = []
            for idx, chunk in enumerate(chunks):
                texts_to_embed.append(chunk.content)
                embed_indices.append(idx)

            embeddings = embedding_function(texts_to_embed)

            for idx, chunk in enumerate(chunks):
                emb = embeddings[idx]
                if isinstance(emb, np.ndarray):
                    emb = emb.tolist()

                existing = session.query(OpportunityChunkRecord).filter_by(chunk_id=chunk.chunk_id).first()
                meta_dict = chunk.metadata if isinstance(chunk.metadata, dict) else {}

                if existing:
                    existing.opportunity_id = chunk.opportunity_id
                    existing.title = chunk.title
                    existing.provider = chunk.provider
                    existing.category = chunk.category
                    existing.section_title = chunk.section_title
                    existing.content = chunk.content
                    existing.official_url = chunk.official_url
                    existing.application_deadline = chunk.application_deadline
                    existing.status = chunk.status
                    existing.verification_status = chunk.verification_status
                    existing.metadata_json = json.dumps(meta_dict)
                    existing.embedding = emb
                else:
                    record = OpportunityChunkRecord(
                        chunk_id=chunk.chunk_id,
                        opportunity_id=chunk.opportunity_id,
                        title=chunk.title,
                        provider=chunk.provider,
                        category=chunk.category,
                        section_title=chunk.section_title,
                        content=chunk.content,
                        official_url=chunk.official_url,
                        application_deadline=chunk.application_deadline,
                        status=chunk.status,
                        verification_status=chunk.verification_status,
                        metadata_json=json.dumps(meta_dict),
                        embedding=emb
                    )
                    session.add(record)

            session.commit()
            return len(chunks)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_raw_records(self, records: List[Dict[str, Any]]) -> int:
        """Upserts records from JSON export or dictionary directly."""
        if not records:
            return 0

        session = self.session_factory()
        try:
            for item in records:
                chunk_id = item["chunk_id"]
                document = item.get("document", item.get("content", ""))
                meta = item.get("metadata", {})
                emb = item.get("embedding")
                if emb is not None and isinstance(emb, np.ndarray):
                    emb = emb.tolist()

                existing = session.query(OpportunityChunkRecord).filter_by(chunk_id=chunk_id).first()
                if existing:
                    existing.opportunity_id = meta.get("opportunity_id", "")
                    existing.title = meta.get("title", "")
                    existing.provider = meta.get("provider", "")
                    existing.category = meta.get("category", "")
                    existing.section_title = meta.get("section_title", "")
                    existing.content = document
                    existing.official_url = meta.get("official_url", "")
                    existing.application_deadline = meta.get("application_deadline")
                    existing.status = meta.get("status", "Active")
                    existing.verification_status = meta.get("verification_status", "UNVERIFIED")
                    existing.metadata_json = json.dumps(meta)
                    if emb is not None:
                        existing.embedding = emb
                else:
                    record = OpportunityChunkRecord(
                        chunk_id=chunk_id,
                        opportunity_id=meta.get("opportunity_id", ""),
                        title=meta.get("title", ""),
                        provider=meta.get("provider", ""),
                        category=meta.get("category", ""),
                        section_title=meta.get("section_title", ""),
                        content=document,
                        official_url=meta.get("official_url", ""),
                        application_deadline=meta.get("application_deadline"),
                        status=meta.get("status", "Active"),
                        verification_status=meta.get("verification_status", "UNVERIFIED"),
                        metadata_json=json.dumps(meta),
                        embedding=emb
                    )
                    session.add(record)
            session.commit()
            return len(records)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def search(
        self,
        query: str,
        top_k: int = 4,
        category: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query_embed = embedding_function([query])
        if not query_embed or len(query_embed) == 0:
            return []

        if self.engine.dialect.name == "postgresql":
            session = self.session_factory()
            try:
                where_clauses = []
                params = {
                    "top_k": top_k,
                    "vec": "[" + ",".join(str(float(x)) for x in query_embed[0]) + "]"
                }
                if category:
                    where_clauses.append("category = :category")
                    params["category"] = category
                if status:
                    where_clauses.append("status = :status")
                    params["status"] = status

                where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                sql = f"""
                    SELECT chunk_id, content, metadata_json,
                           1.0 - (embedding <=> CAST(:vec AS vector)) AS cos_sim,
                           embedding <=> CAST(:vec AS vector) AS distance
                    FROM opportunity_chunks
                    {where_sql}
                    ORDER BY embedding <=> CAST(:vec AS vector)
                    LIMIT :top_k;
                """
                rows = session.execute(text(sql), params).fetchall()
                formatted = []
                for row in rows:
                    cid, content, meta_json, cos_sim, dist = row
                    meta = json.loads(meta_json) if meta_json else {}
                    if "source_url" not in meta and "official_url" in meta:
                        meta["source_url"] = meta["official_url"]
                    if "official_url" not in meta and "source_url" in meta:
                        meta["official_url"] = meta["source_url"]
                    similarity_score = max(0.0, float(cos_sim))
                    chroma_dist = max(0.0, 2.0 * float(dist))
                    formatted.append({
                        "chunk_id": cid,
                        "content": content,
                        "metadata": meta,
                        "similarity_score": round(similarity_score, 4),
                        "distance": round(chroma_dist, 4)
                    })
                return formatted
            finally:
                session.close()

        query_vec = np.array(query_embed[0], dtype=np.float32)

        session = self.session_factory()
        try:
            q = session.query(OpportunityChunkRecord)
            if category:
                q = q.filter(OpportunityChunkRecord.category == category)
            if status:
                q = q.filter(OpportunityChunkRecord.status == status)

            rows = q.all()
            if not rows:
                return []

            scored = []
            q_norm = np.linalg.norm(query_vec)

            for row in rows:
                if row.embedding is None:
                    continue
                row_vec = np.array(row.embedding, dtype=np.float32)
                r_norm = np.linalg.norm(row_vec)
                if q_norm == 0 or r_norm == 0:
                    cos_sim = 0.0
                else:
                    cos_sim = float(np.dot(query_vec, row_vec) / (q_norm * r_norm))

                # For unit-normalized vectors:
                # ChromaDB calculates squared L2 distance: dist_l2_sq = 2.0 * (1.0 - cos_sim)
                # ChromaDB similarity_score = 1.0 - (dist_l2_sq / 2.0) = cos_sim
                # pgvector cosine distance operator <=> yields: 1.0 - cos_sim
                chroma_compatible_distance = max(0.0, 2.0 * (1.0 - cos_sim))
                similarity_score = max(0.0, cos_sim)

                meta = {}
                if row.metadata_json:
                    try:
                        meta = json.loads(row.metadata_json)
                    except Exception:
                        pass

                scored.append({
                    "chunk_id": row.chunk_id,
                    "content": row.content,
                    "metadata": meta,
                    "similarity_score": round(similarity_score, 4),
                    "distance": round(chroma_compatible_distance, 4)
                })

            scored.sort(key=lambda x: x["similarity_score"], reverse=True)
            return scored[:top_k]
        finally:
            session.close()

    def get_stats(self) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            count = session.query(func.count(OpportunityChunkRecord.chunk_id)).scalar()
            return {
                "collection_name": "opportunity_chunks",
                "total_chunks": count or 0,
                "embedding_dimensions": 384,
                "backend": "pgvector_sqlalchemy"
            }
        finally:
            session.close()

    def clear(self):
        session = self.session_factory()
        try:
            session.query(OpportunityChunkRecord).delete()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

pgvector_store = PgVectorStore()
