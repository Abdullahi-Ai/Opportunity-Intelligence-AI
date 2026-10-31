# Opportunity Intelligence AI — Production Deployment Guide

This guide details the complete production architecture, deployment workflows, database migrations, and operational maintenance for **Opportunity Intelligence AI**.

---

## 1. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Client["Frontend Layer (Vercel)"]
        UI["React 18 + Vite SPA"]
        Tailwind["TailwindCSS + Lucide Icons"]
    end

    subgraph Hosting["Backend Layer (Railway)"]
        FastAPI["FastAPI Gateway (Uvicorn - 1 Worker)"]
        RateLimiter["In-Memory Rate Limiter"]
        Orchestrator["Agentic Orchestrator & Tool Dispatcher"]
        Chroma["ChromaDB Vector Store (Persistent Volume /data)"]
    end

    subgraph DataLayer["Managed Data & Cloud AI"]
        Neon["Neon Managed PostgreSQL (Pooled & Direct Connection)"]
        Groq["Groq Cloud API (Llama 3.3 70B Versatile)"]
    end

    UI -->|"HTTPS REST API / JSON"| FastAPI
    FastAPI --> RateLimiter
    RateLimiter --> Orchestrator
    Orchestrator -->|"Semantic Search / Embeddings"| Chroma
    Orchestrator -->|"Function / Tool Calling"| Groq
    FastAPI -->|"SQLAlchemy ORM (Pooled Port 5432)"| Neon
    FastAPI -->|"Alembic Migrations (Direct Endpoint)"| Neon
```

---

## 2. Environment Variables Specification

### Backend (Railway Secret Management)
| Variable | Value / Description | Sensitive |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | No |
| `DEBUG` | `false` | No |
| `HOST` | `0.0.0.0` | No |
| `PORT` | `8000` (Assigned by Railway) | No |
| `SECRET_KEY` | Dedicated 64-character hex cryptographic string | **YES** |
| `ADMIN_REGISTRATION_SECRET` | Dedicated 32-character token for admin account creation | **YES** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | No |
| `DATABASE_URL` | Neon pooled URL: `postgresql://user:password@ep-xyz-pooler.region.neon.tech/neondb?sslmode=require` | **YES** |
| `GROQ_API_KEY` | Production Groq API key: `gsk_...` | **YES** |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | No |
| `CHROMA_PERSIST_DIRECTORY` | `/data/chromadb` (Mounted persistent volume) | No |
| `CHROMA_COLLECTION_NAME` | `kenya_opportunities` | No |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | No |
| `RATE_LIMITING_ENABLED` | `true` | No |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app,https://opportunities.ac.ke` | No |

### Frontend (Vercel Project Settings)
| Variable | Value / Description |
| :--- | :--- |
| `VITE_API_URL` | Railway backend public URL: `https://your-backend.up.railway.app` |

---

## 3. Neon PostgreSQL Configuration

### Dual-Endpoint Strategy
Neon provides two connection strings:
1. **Application Connection (Pooled):**
   - Format: `postgresql://[user]:[password]@ep-[name]-pooler.[region].neon.tech/neondb?sslmode=require`
   - Purpose: Used by FastAPI runtime for low-latency, pooled database queries.
2. **Migration Connection (Direct):**
   - Format: `postgresql://[user]:[password]@ep-[name].[region].neon.tech/neondb?sslmode=require`
   - Purpose: Used by Alembic for DDL operations (`05a08e706193`).
   - The Alembic configuration in `backend/alembic/env.py` automatically normalizes `-pooler.` URLs to direct endpoints during migration runs.

### Connection Pool Specification
When running with PostgreSQL:
- **Pool Size:** `10`
- **Max Overflow:** `20`
- **Pool Pre-Ping:** `True` (verifies connection validity before each checkout)
- **Pool Recycle:** `300` seconds (avoids silent disconnections from cloud proxies)

---

## 4. Railway Backend Deployment

### Configuration Files
- **[`railway.json`](file:///home/osama/Opportunity-Intelligence-AI/railway.json):**
  Defines buildpack (`NIXPACKS`), health check (`/api/v1/health`), and production startup command:
  ```bash
  cd backend && alembic upgrade head && python -m app.rag.reindex && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
  ```
- **[`backend/Procfile`](file:///home/osama/Opportunity-Intelligence-AI/backend/Procfile):**
  ```bash
  web: alembic upgrade head && python -m app.rag.reindex && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
  ```

### Storage Volume Mount
Attach a Railway persistent volume mounted at `/data` to preserve indexed ChromaDB embeddings and prevent index loss on deploy restarts.

---

## 5. Vercel Frontend Deployment

### Configuration File ([`frontend/vercel.json`](file:///home/osama/Opportunity-Intelligence-AI/frontend/vercel.json))
```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

### Build Verification
```bash
cd frontend
npm install --frozen-lockfile
npm run build
```

---

## 6. Migration, Backup & Health Monitoring

### Alembic Migration Command
```bash
cd backend
venv/bin/alembic upgrade head
```

### ChromaDB Backup & Ingestion
```bash
# Force fresh re-indexing of raw opportunities:
cd backend && python -m app.rag.reindex

# Generate snapshot backup:
python -c "from app.rag.reindex import backup_chroma_db; print(backup_chroma_db('/data/backups'))"
```

### Health Check Verification
```bash
curl -f https://your-backend.up.railway.app/api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "chromadb": {
    "collection_name": "kenya_opportunities",
    "total_chunks_indexed": 140
  },
  "llm_provider": "Groq",
  "model": "llama-3.3-70b-versatile"
}
```
