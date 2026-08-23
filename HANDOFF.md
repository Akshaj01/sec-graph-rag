# SEC GraphRAG — Handoff

## How context works across machines (read this)

Cursor chat history on the MacBook does **not** reliably transfer to the PC.
The new Cursor agent on your desktop only knows what is in:

1. **This repo on GitHub** (code + docs)
2. **`.agents/AGENTS.md`** — rules, ontology, Learning Protocol, Phase 1–5 roadmap
3. **`HANDOFF.md`** (this file) — current status + what to do next
4. **Whatever you paste** into the first desktop chat message

It will **not** magically remember our long MacBook conversation.
It does **not** need the BASWE PowerPoint/PDF in the repo — the curriculum steps that matter are already summarized in `.agents/AGENTS.md` (Phases 1–5).

Optional: keep the BASWE PDF on the PC for *your* reading (iCloud/Drive/USB), outside git.

---

## Project goal

Knowledge Graph RAG over SEC **10-K** filings (BASWE Project 1).
Phase 1 = extract closed-world graph → resolve entities → MERGE into Neo4j with chunk citations.

Repo: https://github.com/Akshaj01/sec-graph-rag (private)

## Phase 1 status

| Step | Status | Main files |
|------|--------|------------|
| A Environment & Docker | DONE | `docker-compose.yml`, `config.py`, `requirements.txt` |
| B Pydantic ontology | DONE | `schemas.py` |
| C Fetch / chunk / hash cache | DONE | `ingest.py` |
| D Claude structured extraction | DONE | `extractor.py` |
| E Entity resolution | DONE | `resolver.py` |
| F Idempotent Neo4j writes | DONE (code) | `graph_writer.py` — **live Neo4j smoke test still pending Docker** |

## What to do FIRST on the PC

1. Clone/pull the repo
2. Create `.venv` with **Python 3.12+**, `pip install -r requirements.txt`
3. Create `.env` locally (copy keys from Mac — never commit):
   - `USER_AGENT_EMAIL`
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
4. Install/start Docker Desktop
5. `docker compose up -d`
6. `.venv/bin/python graph_writer.py AAPL`
7. Verify in Neo4j Browser: http://localhost:7474 (user `neo4j` / password `password`)

Only after that works → start **Phase 2** (pgvector) using `.agents/AGENTS.md`, still Learning Protocol (plan → confirm → code).

## Locked decisions (do not silently change)

- Sections: Item **1 / 1A / 7** only
- Chunk ~**3000** tokens / ~**200** overlap
- Claude + Instructor → `KnowledgeGraphExtraction`
- Soft-match embeddings: OpenAI `text-embedding-3-small`, threshold **0.92**
- Neo4j: **MERGE**, constraints on `id`, `source_chunk_ids` on edges
- Learning Protocol: one step; explain WHY; wait for confirmation

## Closed-world ontology

**Entities:** Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive  
**Rels:** OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

## Pipeline

```text
ingest → extract (Claude) → resolve → graph_writer (Neo4j MERGE)
```

## Verified on MacBook

- AAPL filing `0000320193-25-000079`
- 5-chunk resolve: 53 → 49 entities; Apple Inc. → 1 node (`mention_count=5`)
- Soft-match ran with funded OpenAI key
- Docker was **not** available on the MacBook, so Neo4j write was not live-tested there

## Copy-paste into a NEW Cursor chat on the PC

```text
You are continuing the SEC GraphRAG project on a new machine.
This chat has NO prior MacBook history.

1) Read and follow `.agents/AGENTS.md` and `HANDOFF.md` completely.
2) Obey the Learning Protocol: one step at a time, explain WHY, wait for my confirmation before coding.
3) Do NOT need the BASWE PowerPoint — the phase roadmap is already in AGENTS.md.
4) Immediate task: get Docker Neo4j running and verify Step F with:
   docker compose up -d
   .venv/bin/python graph_writer.py AAPL
   Then help me confirm nodes/edges in Neo4j Browser.
5) After that succeeds, propose Phase 2 (pgvector + shared chunk ids) only — do not implement until I confirm.
```
