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
Phase 1 = extract closed-world graph → resolve entities → MERGE into Neo4j with chunk citations.

Repo: https://github.com/Akshaj01/sec-graph-rag (private)

## Phase 1 status — COMPLETE (live-verified on PC)

| Step | Status | Main files |
|------|--------|------------|
| A Environment & Docker | DONE | `docker-compose.yml`, `config.py`, `requirements.txt` |
| B Pydantic ontology | DONE | `schemas.py` |
| C Fetch / chunk / hash cache | DONE | `ingest.py` |
| D Claude structured extraction | DONE | `extractor.py` |
| E Entity resolution | DONE | `resolver.py` |
| F Idempotent Neo4j writes | DONE (live) | `graph_writer.py` |

## PC setup (completed 2026-08-23)

- [x] Clone/pull repo
- [x] `.venv` (Python 3.13) + `pip install -r requirements.txt`
- [x] `.env` locally (never commit): `USER_AGENT_EMAIL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- [x] Docker Desktop installed
- [x] `docker compose up -d` → Neo4j at http://localhost:7474
- [x] Smoke test: `.\.venv\Scripts\python.exe graph_writer.py AAPL`
- [x] Verified in Neo4j Browser (Company `APPLE`, edges with `source_chunk_ids`)

### PC smoke test results (AAPL, 5 chunks)

- Filing: `0000320193-25-000079`
- Extraction: 64 raw entities → **60 canonical** after resolution
- Neo4j: **60 nodes**, **59 relationships**
- Apple Inc. (`id: APPLE`): `mention_count=5`, cited across 5 chunks
- Soft-match enabled (OpenAI embeddings)

### Known config note

Apple's Item 1 chunk is dense. Default `EXTRACTION_MAX_TOKENS=4096` can hit `max_tokens` on first run.
**Workaround used on PC:** set `EXTRACTION_MAX_TOKENS=16384` in `.env` (or env var) before running `graph_writer.py`.

### Neo4j Browser login (local Docker — NOT Neo4j Aura / Google)

| Field | Value |
|-------|-------|
| Connect URL | `neo4j://localhost:7687` |
| Username | `neo4j` |
| Password | `password` |

Do **not** use your neo4j.com / Google Aura account for local Docker.

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

## What to do NEXT → Phase 2

Start **Phase 2** (pgvector + shared chunk ids) using `.agents/AGENTS.md`.
Learning Protocol still applies: plan → explain WHY → wait for confirmation → code.

## Locked decisions (do not silently change)

- Sections: Item **1 / 1A / 7** only
- Chunk ~**3000** tokens / ~**200** overlap
- Claude + Instructor → `KnowledgeGraphExtraction`
- Soft-match embeddings: OpenAI `text-embedding-3-small`, threshold **0.92**
- Neo4j: **MERGE**, constraints on `id`, `source_chunk_ids` on edges
- Learning Protocol: one step; explain WHY; wait for confirmation
- Recommended: `EXTRACTION_MAX_TOKENS=16384` for dense 10-K Item 1 chunks

## Closed-world ontology

**Entities:** Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive  
**Rels:** OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

## Pipeline

```text
ingest → extract (Claude) → resolve → graph_writer (Neo4j MERGE)
```

## Verified on MacBook (extraction + resolution only)

- AAPL filing `0000320193-25-000079`
- 5-chunk resolve: 53 → 49 entities; Apple Inc. → 1 node (`mention_count=5`)
- Soft-match ran with funded OpenAI key
- Docker was **not** available on the MacBook, so Neo4j write was not live-tested there

## Copy-paste into a NEW Cursor chat (Phase 2 start)

```text
You are continuing the SEC GraphRAG project.
Read `.agents/AGENTS.md` and `HANDOFF.md` completely.

Phase 1 is COMPLETE and live-verified on PC (Neo4j + AAPL smoke test).
Obey the Learning Protocol: one step at a time, explain WHY, wait for my confirmation before coding.

Immediate task: propose Phase 2 (pgvector + shared chunk ids) — plan only, do not implement until I confirm.
```

## Windows quick commands

```powershell
docker compose up -d
$env:EXTRACTION_MAX_TOKENS = "16384"
.\.venv\Scripts\python.exe graph_writer.py AAPL
```
