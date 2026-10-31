# Opportunity Intelligence AI — Production Deployment Guide

This guide details the production architecture, PostgreSQL migration pipeline, persistent memory, vector database configuration, security policies, and startup instructions for **Opportunity Intelligence AI**.

---

## 1. Environment Architecture & Variables

Create a dedicated `.env` file in the `backend/` directory based on the following production specification:

```bash
# Application Environment
APP_NAME="Opportunity Intelligence AI"
APP_ENV=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Cryptographic Secrets (Minimum 32 characters for SECRET_KEY, 16 for ADMIN_SECRET)
SECRET_KEY=generate_cryptographically_secure_random_key_min_32_chars_long
ADMIN_REGISTRATION_SECRET=generate_strong_admin_secret_token_16_chars_min
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Database Configuration (PostgreSQL with Connection Pooling)
DATABASE_URL=postgresql://opportunity_user:secure_pg_password@localhost:5432/opportunity_db

# LLM Agent Configuration
GROQ_API_KEY=gsk_your_production_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# ChromaDB Vector Storage Configuration
CHROMA_PERSIST_DIRECTORY=/var/lib/opportunity-ai/chromadb_prod
CHROMA_COLLECTION_NAME=kenya_opportunities
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# API Security & Rate Limiting
RATE_LIMITING_ENABLED=true
ALLOWED_ORIGINS=https://opportunities.ac.ke,https://admin.opportunities.ac.ke
```

---

## 2. PostgreSQL Setup & Connection Pooling

### Database Provisioning
```bash
sudo -u postgres psql -c "CREATE USER opportunity_user WITH PASSWORD 'secure_pg_password';"
sudo -u postgres psql -c "CREATE DATABASE opportunity_db OWNER opportunity_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE opportunity_db TO opportunity_user;"
```

### Connection Pool Specification
When running with PostgreSQL (`DATABASE_URL=postgresql://...`), SQLAlchemy engine initializes with:
- **Pool Size:** `10` persistent connections
- **Max Overflow:** `20` burst connections
- **Pool Pre-Ping:** `True` (verifies connection health before checkout)
- **Pool Recycle:** `300` seconds (prevents stale database drops)

---

## 3. Alembic Database Migration Commands

Apply all schema versions up to head:

```bash
cd backend
source venv/bin/activate

# Check current revision status
alembic current

# Execute all pending migrations up to latest head
alembic upgrade head

# Rollback single migration if necessary
alembic downgrade -1
```

---

## 4. ChromaDB Vector Knowledge Ingestion & Backup

### Initial Ingestion / Re-indexing
```bash
cd backend
source venv/bin/activate

# Execute idempotent document chunking and vector indexing
python -m app.rag.reindex
```

### Snapshot & Backup Procedure
```bash
python -c "from app.rag.reindex import backup_chroma_db; print('Backup saved at:', backup_chroma_db('/var/backups/chromadb'))"
```

---

## 5. Frontend Production Build

```bash
cd frontend
npm install --frozen-lockfile
npm run build
```

The resulting `frontend/dist/` directory contains minified static bundles ready for reverse-proxy serving via NGINX or Caddy.

---

## 6. Service Supervision & Startup

### Backend Service (Systemd Configuration)
Create `/etc/systemd/system/opportunity-backend.service`:

```ini
[Unit]
Description=Opportunity Intelligence AI Backend Service
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/opportunity-ai/backend
Environment="PATH=/var/www/opportunity-ai/backend/venv/bin"
ExecStart=/var/www/opportunity-ai/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable opportunity-backend
sudo systemctl start opportunity-backend
```

---

## 7. Health Check, Monitoring & Log Audits

### Automated Health Verification
```bash
curl -f http://localhost:8000/api/v1/health
```
Expected output:
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

### Rate Limiting Limits
- **Authentication (`/api/v1/auth/login`, `/register`):** 5 requests / 60 seconds per IP.
- **Conversational AI (`/api/v1/chat`):** 20 requests / 60 seconds per user / IP.
- **Discovery (`/api/v1/opportunities`, `/matches`, `/tracker`):** 60 requests / 60 seconds.
