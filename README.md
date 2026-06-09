# LIVE LINK: https://b2b-saas-sales-agent-production.up.railway.app

## loom link: https://www.loom.com/share/f45b7ba57fca46378a0e99487b9d6a66

# Persistent Sales Assistant Agent

A production-grade, stateful AI Sales Assistant API built with **FastAPI** and **SQLAlchemy**. Features cross-session memory persistence, autonomous catalog tool execution, and real-time LLM self-evaluation scoring on every response.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Memory Design Decision](#3-memory-design-decision)
4. [Eval Design](#4-eval-design)
5. [API Endpoints](#5-api-endpoints)
6. [Cross-Session Memory Demo](#6-cross-session-memory-demo)
7. [Live URL](#7-live-url)
8. [Local Setup](#8-local-setup)
9. [Environment Variables](#9-environment-variables)
10. [Product Catalog](#10-product-catalog)

---

## 1. Architecture Overview

Every user message travels through a layered pipeline before a response is returned:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          POST /chat/{user_id}                           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │   API Route      │  (app/api/)
                          │  (FastAPI)       │  Validates request,
                          │                  │  resolves user_id
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  Chat Service    │  (app/services/)
                          │                  │  Orchestrates the full
                          │                  │  agent loop per request
                          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │ search_      │ │ get_user_    │ │ flag_for_    │
           │ catalog()    │ │ memory()     │ │ human()      │
           │              │ │              │ │  (bonus)     │
           └──────┬───────┘ └──────┬───────┘ └──────────────┘
                  │                │
                  └───────┬────────┘
                          │  Tool results injected into context
                          ▼
                 ┌─────────────────┐
                 │   LLM (Claude)  │  Generates grounded response
                 │                 │  using tool outputs + memory
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Eval Service   │  (app/services/)
                 │                 │  LLM self-scores the response:
                 │                 │  groundedness, relevance,
                 │                 │  confidence, flagged
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Memory Write   │  (app/memory/)
                 │                 │  Persists message + eval to DB
                 └────────┬────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  Structured Response   │
              │  { response, eval,     │
              │    tools_called,       │
              │    session_id }        │
              └────────────────────────┘
```

**Key design principle:** the agent never answers from raw LLM knowledge alone. Every response is grounded by real tool calls — `search_catalog` reads the catalog JSON, and `get_user_memory` queries the database — before the LLM generates text.

---

## 2. Project Structure

```
backend/
├── app/
│   ├── api/              # Route handlers only — no business logic
│   │   └── routes.py
│   ├── agents/           # Agent loop, tool definitions, eval logic
│   │   └── sales_agent.py
│   ├── memory/           # Abstracted memory read/write layer
│   │   ├── base.py       # Abstract interface (MemoryBackend)
│   │   └── sqlite.py     # SQLite implementation (swap here for Postgres/Mem0)
│   ├── tools/            # Callable tool functions
│   │   ├── search_catalog.py
│   │   ├── get_user_memory.py
│   │   └── flag_for_human.py
│   ├── services/         # Chat orchestration + eval scoring
│   │   ├── chat_service.py
│   │   └── eval_service.py
│   ├── models/           # Pydantic request/response schemas
│   │   └── schemas.py
│   └── db/               # SQLAlchemy models + Alembic migrations
│       ├── models.py
│       └── migrations/
├── catalog.json          # Mock product/pricing catalog
├── main.py               # FastAPI app entry point
├── requirements.txt
└── .env.example
```

---

## 3. Memory Design Decision

### Current approach — SQLite via SQLAlchemy

All conversation turns are persisted to a SQLite database via SQLAlchemy ORM. Each row stores the `user_id`, `session_id`, message role (user/assistant), message content, and the eval block for that turn.

The memory layer is deliberately abstracted behind a `MemoryBackend` interface in `app/memory/base.py`. The SQLite implementation lives entirely in `app/memory/sqlite.py`. To swap the backend, you change **one file** — nothing else in the codebase needs to change.

`get_user_memory(user_id)` queries this table and returns the most recent N turns for that user, injecting them into the LLM context before generation. This is what enables cross-session continuity — the model sees prior conversation history without the client needing to re-send it.

### What we'd use at scale

| Scale | Memory Backend | Reason |
|---|---|---|
| Current (MVP) | SQLite | Zero-config, single-file, sufficient for demo |
| Production (thousands of users) | PostgreSQL | Concurrent writes, proper indexing, Railway-native |
| Large-scale (millions of turns) | Mem0 or Zep | Automatic summarization, semantic retrieval, TTL |
| RAG-augmented memory | LanceDB / Pinecone | Vector search over past turns for relevance-based recall |

The key tradeoff at scale is verbosity vs. compression. Storing every raw message becomes expensive and noisy. A memory summarization job (see bonus section) compresses older turns into a rolling summary, keeping the context window lean.

---

## 4. Eval Design

### Implementation

After every LLM generation, the response is passed back to the model (same or smaller Claude model) with a structured prompt asking it to rate itself across three dimensions:

- **Groundedness** — Is the response traceable to catalog data or retrieved memory? Did it avoid adding claims not present in those sources?
- **Relevance** — Does the response actually answer what the user asked?
- **Confidence** — How certain is the model that the response is accurate and complete?

The eval prompt enforces JSON-only output. Scores are floats in `[0, 1]`. A `flagged: true` is set if `confidence < 0.70`, and `flag_for_human()` is called to log a human-review entry.

Every eval block is stored alongside the message in the database, enabling the bonus `/evals` aggregation endpoint.

### Example response shape

```json
{
  "response": "Our Enterprise plan is $499/month and includes SSO, audit logs, and an SLA.",
  "eval": {
    "groundedness": 0.94,
    "relevance": 0.91,
    "confidence": 0.88,
    "flagged": false,
    "reasoning": "Response sourced directly from catalog. User's prior team-size context applied. No hallucination risk detected."
  },
  "tools_called": ["search_catalog", "get_user_memory"],
  "session_id": "3f7a1c2d-88b4-4e9a-bc3d-0f1e2a3b4c5d"
}
```

### Limitations

- **Self-scoring bias:** The model that generated the response is also scoring it. A model with high confidence in a wrong answer will score itself highly. This is a known limitation of LLM self-evaluation.
- **No ground truth:** Without a labeled eval dataset, there is no external baseline to calibrate scores against.
- **Score drift:** Scores are not calibrated across sessions, so a 0.88 today may not mean the same as a 0.88 in a different context.

### What we'd replace it with

In production, we would add a separate, smaller judge model (e.g., a fine-tuned Claude Haiku or a dedicated classifier) that scores responses independently, with access to the catalog JSON as the ground truth. Scores from the judge would be logged separately and compared against the self-eval scores to detect calibration drift over time.

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat/{user_id}` | Send a message; returns response + eval block |
| `GET` | `/chat/{user_id}/history` | Full conversation history across all sessions |
| `DELETE` | `/chat/{user_id}/memory` | Wipe all memory for a user (GDPR reset) |
| `GET` | `/catalog` | Returns the product/pricing catalog |
| `GET` | `/health` | Service health check |
| `GET` | `/chat/{user_id}/evals` | *(Bonus)* Aggregated eval scores across all sessions |

### Request body for `POST /chat/{user_id}`

```json
{
  "message": "What does the Enterprise plan include?",
  "session_id": "optional-uuid-or-omit-to-auto-generate"
}
```

---

## 6. Cross-Session Memory Demo

These two `curl` commands demonstrate that the agent carries context across completely separate sessions. **No prior context is sent in the second request body** — it is retrieved from the database via `get_user_memory`.

### Call 1 — Establish context (Session A)

```bash
curl -X POST "https://b2b-saas-sales-agent-production.up.railway.app/chat/user_demo_01" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "We have an engineering team of 45 people and we absolutely need SAML SSO and audit logs.",
    "session_id": "session-alpha-001"
  }'
```

Expected: The agent calls `search_catalog` to find plans with SSO + audit logs, identifies the Enterprise plan, and responds with pricing. The turn is stored in the database.

### Call 2 — Recall context (Session B, different session_id)

```bash
curl -X POST "https://b2b-saas-sales-agent-production.up.railway.app/chat/user_demo_01" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Does that plan also cover our compliance needs if we scale to 200 people?",
    "session_id": "session-beta-002"
  }'
```

Expected: The agent calls `get_user_memory` and retrieves the prior session's context (45-person team, SSO requirement, Enterprise plan already discussed). It answers about compliance and scalability without the user re-explaining their situation.

---

## 7. Live URL

**Base URL:** `https://b2b-saas-sales-agent-production.up.railway.app`

**Health check:** `https://b2b-saas-sales-agent-production.up.railway.app/health`

**Interactive docs:** `https://b2b-saas-sales-agent-production.up.railway.app/docs`

> Deployed on [Railway](https://railway.app). The SQLite database is persisted via a Railway volume mount so memory survives redeploys.

---

## 8. Local Setup

```bash
# Clone and enter the backend directory
git clone https://github.com/Nakul443/b2b-saas-sales-agent.git
cd b2b-saas-sales-agent/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and add your API key
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --port 8000
```

API will be available at `http://localhost:8000`. Interactive Swagger docs at `http://localhost:8000/docs`.

---

## 9. Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `DATABASE_URL` | SQLite path or Postgres connection string (default: `sqlite:///./sales_agent.db`) |
| `MEMORY_BACKEND` | `sqlite` or `postgres` (controls which memory implementation is loaded) |
| `CONFIDENCE_THRESHOLD` | Float below which responses are flagged for human review (default: `0.70`) |
| `MAX_MEMORY_TURNS` | How many past turns `get_user_memory` injects into context (default: `10`) |

---

## 10. Product Catalog

The agent uses `catalog.json` as its ground-truth knowledge base. `search_catalog` performs keyword search over this file — the agent cannot invent plan features that aren't present here.

```json
{
  "plans": [
    {
      "name": "Starter",
      "price": "$49/mo",
      "features": ["5 users", "API access", "email support"]
    },
    {
      "name": "Growth",
      "price": "$199/mo",
      "features": ["25 users", "webhooks", "priority support"]
    },
    {
      "name": "Enterprise",
      "price": "$499/mo",
      "features": ["unlimited users", "SSO", "audit logs", "SLA"]
    }
  ]
}
```

---

## Bonus Features

- **`GET /chat/{user_id}/evals`** — Returns aggregated eval statistics across all sessions: mean groundedness, mean confidence, % of responses flagged, and total response count.
- **`flagged: true` logging** — Any response where `confidence < CONFIDENCE_THRESHOLD` triggers `flag_for_human()`, which writes a flagged entry to the database. A reviewer can query all flagged entries to audit low-confidence answers before they reach customers.
- **Memory summarization** — Older turns beyond `MAX_MEMORY_TURNS` are periodically compressed into a rolling summary by the LLM, keeping context injection lean without losing long-term facts about the user.