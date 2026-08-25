# SEC GraphRAG — Handoff

## How context works across machines (read this)

Cursor chat history does **not** reliably transfer between machines.
A new Cursor agent only knows what is in:

1. **This repo on GitHub** (code + docs)
2. **`.agents/AGENTS.md`** — rules, ontology, Learning Protocol, Phase 1–5 roadmap
3. **`HANDOFF.md`** (this file) — current status + what to do next
4. **Whatever you paste** into the first chat message

It does **not** need the BASWE PowerPoint/PDF in the repo — the curriculum steps that matter are already summarized in `.agents/AGENTS.md` (Phases 1–5).

Optional: keep the BASWE PDF locally for *your* reading (iCloud/Drive/USB), outside git.

---

## Project goal

Knowledge Graph RAG over SEC **10-K** filings (BASWE Project 1).
Extract a closed-world graph, resolve entities, MERGE into Neo4j, and index the **same chunks** in pgvector with shared `chunk_id`s.

Repo: https://github.com/Akshaj01/sec-graph-rag (private)

## Status — Phase 1 + Phase 2 COMPLETE (live-verified on PC, 2026-08-23)

### Phase 1 — graph extraction

| Step | Status | Main files |
|------|--------|------------|
| A Environment & Docker | DONE | `docker-compose.yml`, `config.py`, `requirements.txt` |
| B Pydantic ontology | DONE | `schemas.py` |
| C Fetch / chunk / hash cache | DONE | `ingest.py` |
| D Claude structured extraction | DONE | `extractor.py` |
| E Entity resolution | DONE | `resolver.py` |
| F Idempotent Neo4j writes | DONE (live) | `graph_writer.py` |
| Budget / confirm gate | DONE | `budget.py` |

### Phase 2 — vector index alongside the graph

| Step | Status | Main files |
|------|--------|------------|
| G Postgres + pgvector | DONE | `docker-compose.yml`, `vector_db.py`, `docker/postgres/init.sql` |
| H Embed chunks (shared `chunk_id`) | DONE | `embedder.py` |
| I Entity cross-links (`entity_ids`) | DONE | `embedder.py --link-entities` |
| J HNSW + recall@k | DONE | `recall_eval.py` |

## PC setup (completed 2026-08-23)

- [x] `.venv` (Python 3.13) + `pip install -r requirements.txt`
- [x] `.env` locally (never commit): `USER_AGENT_EMAIL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- [x] Docker Desktop + `docker compose up -d` (Neo4j **and** Postgres)
- [x] AAPL graph smoke test + Neo4j Browser verification
- [x] AAPL embeddings + entity_ids + HNSW recall@3 = **1.0** on 5 labeled queries

### Graph smoke test (AAPL, 5 chunks)

- Filing: `0000320193-25-000079`
- Extraction: 64 raw entities → **60 canonical** after resolution
- Neo4j: **60 nodes**, **59 relationships**
- Apple Inc. (`id: APPLE`): `mention_count=5`
- Soft-match enabled (OpenAI embeddings)

### Vector smoke test (same 5 chunks)

- pgvector `0.8.6` / Postgres 16
- 5 rows in `chunk_embeddings`, all with `entity_ids`
- HNSW index: `idx_chunk_embeddings_hnsw`
- `python recall_eval.py --k=3` → mean recall@3 **1.0**

### Known config notes

- Dense Item 1: set `EXTRACTION_MAX_TOKENS=16384` in `.env` (default 4096 can truncate).
- Paid extraction requires `--confirm`; estimate first with `python budget.py AAPL`.
- Local Neo4j is **not** Neo4j Aura / Google login. Browser: `neo4j://localhost:7687` / `neo4j` / `password`.
- Postgres: `secgraph` / `password` on `localhost:5432`.

### Useful Cypher (Neo4j Browser)

```cypher
MATCH (n) RETURN count(n) AS nodes
```

```cypher
MATCH (c:Company {id: 'APPLE'})-[r]->(n) RETURN c, r, n LIMIT 25
```

```cypher
MATCH (n) RETURN labels(n)[0] AS type, count(*) AS count ORDER BY count DESC
```

## What to do NEXT → Phase 3

**Step K done:** `router.py` — classify questions → `graph` | `vector` | `both` (low confidence → both); logs to `./data/route_log.db`.

**Step L done:** `graph_retriever.py` — plan template + resolve entities → run allowlisted parameterized Cypher only.

**Step M done:** `vector_retriever.py` + `retrieve.py` — embed question → HNSW top-k passages; glue runs graph/vector/both from router.

**Phase 3 COMPLETE (retrieval only).** Next: Phase 4 — merge into one grounded answer with citation validation.

Learning Protocol: plan → explain WHY → wait for confirmation → code.

### Try Phase 3

```powershell
.\.venv\Scripts\python.exe router.py "What products does Apple produce?"
.\.venv\Scripts\python.exe graph_retriever.py "What product lines does Apple produce?"
.\.venv\Scripts\python.exe vector_retriever.py "What is AppleCare?"
.\.venv\Scripts\python.exe retrieve.py "How is Apple exposed to China trade risks?"
```

## Locked decisions (do not silently change)

- Sections: Item **1 / 1A / 7** only
- Chunk ~**3000** tokens / ~**200** overlap
- Claude + Instructor → `KnowledgeGraphExtraction`
- Soft-match + chunk embeddings: OpenAI `text-embedding-3-small`, threshold **0.92**
- Neo4j: **MERGE**, constraints on `id`, `source_chunk_ids` on edges
- Cross-link key: **`chunk_id`** (same in Neo4j citations and pgvector rows)
- Learning Protocol: one step; explain WHY; wait for confirmation
- Recommended: `EXTRACTION_MAX_TOKENS=16384` for dense 10-K Item 1 chunks

## Closed-world ontology

**Entities:** Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive  
**Rels:** OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

## Pipeline

```text
ingest → extract (Claude) → resolve → graph_writer (Neo4j MERGE)
       ↘ embed (OpenAI) → pgvector (HNSW, entity_ids, shared chunk_id)
```

## Verified on MacBook (extraction + resolution only)

- AAPL filing `0000320193-25-000079`
- 5-chunk resolve: 53 → 49 entities; Apple Inc. → 1 node (`mention_count=5`)
- Docker was **not** available on the MacBook; Neo4j + pgvector were live-tested on PC

## Copy-paste into a NEW Cursor chat (Phase 3 start)

```text
You are continuing the SEC GraphRAG project.
Read `.agents/AGENTS.md` and `HANDOFF.md` completely.

Phase 1 and Phase 2 are COMPLETE (Neo4j graph + pgvector HNSW, AAPL recall@3 = 1.0).
Obey the Learning Protocol: one step at a time, explain WHY, wait for my confirmation before coding.

Immediate task: propose Phase 3 (route questions to graph vs vectors) — plan only, do not implement until I confirm.
```

## Windows quick commands

```powershell
docker compose up -d
$env:EXTRACTION_MAX_TOKENS = "16384"
.\.venv\Scripts\python.exe budget.py AAPL
.\.venv\Scripts\python.exe graph_writer.py AAPL --confirm
.\.venv\Scripts\python.exe embedder.py AAPL --link-entities
.\.venv\Scripts\python.exe recall_eval.py --k=3
```
