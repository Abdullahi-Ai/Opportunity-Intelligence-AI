# Opportunity Intelligence AI
> **Full-Stack Agentic AI Platform for University Students in Kenya**

Opportunity Intelligence AI is a production-minded AI platform designed to help university students in Kenya discover verified educational and career opportunities, understand complex eligibility criteria, calculate deadline countdowns deterministically, and organize applications using structured preparation checklists.

---

## 🎯 Project Mission & Problem Statement
Kenyan university students face critical challenges when navigating early-career opportunities:
1. **Information Fragmentation:** Opportunities are scattered across unorganized WhatsApp/Telegram groups, government gazettes, and ad-cluttered blogs.
2. **Scam Prevention:** High prevalence of fake job/internship listings charging "application" or "medical" fees.
3. **Complex Eligibility:** Strict terms (e.g., minimum KCSE grades, year of study, county quotas, statutory documents like KRA PIN, HELB clearance, NITA accreditation) lead to high abandonment.
4. **Deadline Blindness:** Deadlines pass unnoticed because students lack centralized tracking aligned with Kenyan semester/trimester academic calendars.

---

## 🏗️ Architecture & Technology Stack

```
Opportunity-Intelligence-AI/
├── backend/
│   ├── app/
│   │   ├── agent/            # Deterministic agent tools (Search, Eligibility, Countdown, Checklist)
│   │   ├── rag/              # Document loader, ChromaDB vector store, ONNX embeddings, ingestion pipeline
│   │   ├── config.py         # Pydantic v2 application settings & environment management
│   │   └── main.py           # FastAPI REST API gateway & CORS configuration
│   ├── data/
│   │   ├── raw_opportunities/# Curated markdown documents with YAML frontmatter
│   │   └── chromadb/         # Local persistent vector database
│   ├── tests/
│   │   ├── data/             # Golden Evaluation Dataset (in-domain & boundary queries)
│   │   ├── test_document_loader.py
│   │   ├── test_rag_pipeline.py
│   │   └── test_evaluation.py# Automated Hit Rate@k, MRR & Attribution evaluation
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # React.js + Vite + Tailwind CSS (Phase 6)
└── docs/                     # System architecture & evaluation reports
```

### Core Technologies
- **Backend:** Python 3.10+, FastAPI, Pydantic v2.
- **RAG & Vector Storage:** ChromaDB with ONNX runtime embedding engine (`sentence-transformers/all-MiniLM-L6-v2`).
- **AI / LLM Integration:** Groq Cloud API (`llama-3.3-70b-versatile`).
- **Relational Persistence:** PostgreSQL (SQLite fallback for rapid local testing).
- **Deterministic Tools:** Python calendar date arithmetic for deadline calculations (zero LLM math hallucinations).

---

## 🛡️ Grounding & Anti-Hallucination Guarantees
- **Verified Source Whitelist:** Every ingested opportunity document is sourced from official portals (HEF, Safaricom, KRA, PSC, Chevening, DAAD, Mastercard Foundation, etc.).
- **Deterministic Date Arithmetic:** Days remaining and expired status are computed strictly via Python's standard library `datetime.date`, never by LLM arithmetic.
- **Explicit Uncertainty Communicator:** When vector similarity falls below threshold, the system communicates lack of evidence rather than generating fabricated criteria.

---

## 🧪 Testing & Evaluation
Run the automated test suite and RAG evaluation against the Golden Benchmark Dataset:

```bash
cd backend
source venv/bin/activate
pytest tests/ -v -s
```

The evaluation suite automatically measures:
- **Hit Rate @ 1 & Hit Rate @ 3**
- **Mean Reciprocal Rank (MRR)**
- **Source Attribution Rate** (URL verification)
- **Out-of-Domain Safe Fallback**

---

## 🚀 Quickstart Guide

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Ingest Verified Opportunities
```bash
python -m app.rag.ingest
```

### 3. Start API Server
```bash
uvicorn app.main:app --reload --port 8000
```
Visit the interactive Swagger API documentation at: `http://localhost:8000/docs`
