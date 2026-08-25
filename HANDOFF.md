# SEC GraphRAG — Handoff

**Last updated:** 2026-08-24 (end of Phase 3)  
**Repo:** https://github.com/Akshaj01/sec-graph-rag (private)  
**Latest relevant commit:** `c1bfedc` — Phase 3 router + graph/vector retrieval

Use this file + `.agents/AGENTS.md` to continue in a **new Cursor chat**. Chat history will not transfer.

---

## How context works

A new agent only knows:

1. This GitHub repo (code + docs)
2. **`.agents/AGENTS.md`** — Learning Protocol, ontology, Phases 1–5 roadmap
3. **`HANDOFF.md`** (this file) — current status, verified results, next step
4. Whatever you paste into the first message

Do **not** invent architecture. Follow BASWE Project 1 phases in order.

---

## Project goal

Hybrid **Knowledge Graph + Vector RAG** over SEC **10-K** filings.

**Done when (full Project 1):** FastAPI answers with validated citations; README opens with hybrid vs vector-only accuracy by hop count.

**Where we are now:** Phases **1–3 complete** (ingest → graph + vectors → route → retrieve). **No answer generation yet** — that is Phase 4.

---

## Status checklist

| Phase | Status | Notes |
|-------|--------|-------|
| 1 Graph extraction | **DONE** | Live AAPL Neo4j smoke test |
| 2 pgvector index | **DONE** | Shared `chunk_id`, HNSW, recall@3 = 1.0 (tiny labeled set) |
| 3 Route + retrieve | **DONE** | Router + graph templates + vector search + `retrieve.py` glue |
| 4 Grounded answer + citations | **NEXT** | Plan first, then implement |
| 5 Benchmark vs vector-only | TODO | After Phase 4 |

---

## Phase 1 — DONE (live-verified PC)

| Step | File(s) |
|------|---------|
| A Env / Docker | `docker-compose.yml`, `config.py`, `requirements.txt` |
| B Ontology | `schemas.py` |
| C Ingest / chunk cache | `ingest.py` → `./data/ingest_cache.db` |
| D Claude extract | `extractor.py` → `./data/extraction_cache.db` |
| E Resolve | `resolver.py` |
| F Neo4j MERGE | `graph_writer.py` |
| Budget gate | `budget.py` — estimate first; `--confirm` required for paid extract |

**AAPL smoke (5 chunks), filing `0000320193-25-000079`:**
- 64 → **60** canonical entities; Neo4j **60 nodes / 59 rels**
- Company id: **`APPLE`** (`mention_count=5`)
- Set `EXTRACTION_MAX_TOKENS=16384` in `.env` (4096 truncates dense Item 1)

---

## Phase 2 — DONE (live-verified PC)

| Step | File(s) |
|------|---------|
| G Postgres + pgvector | `docker-compose.yml`, `docker/postgres/init.sql`, `vector_db.py` |
| H Embed chunks | `embedder.py` (cache by `chunk_hash`) |
| I `entity_ids` on rows | `embedder.py --link-entities` (normalized to match Neo4j ids) |
| J HNSW + recall@k | `recall_eval.py` |

**AAPL vector smoke (same 5 chunks):**
- Table `chunk_embeddings`: 5 rows, all with `entity_ids`
- HNSW: `idx_chunk_embeddings_hnsw`
- `python recall_eval.py --k=3` → mean recall@3 **1.0** (5 hand-labeled queries — not a portfolio benchmark)

**Cross-link key:** `chunk_id` format `{accession}:{section}:{index}`  
Example: `0000320193-25-000079:Item1:0`

---

## Phase 3 — DONE (live-verified PC, 2026-08-24)

| Step | File(s) | What it does |
|------|---------|--------------|
| K Router | `router.py` | Haiku few-shot → `graph` \| `vector` \| `both`; confidence &lt; 0.75 → `both`; log `./data/route_log.db` |
| L Graph path | `graph_retriever.py` | Plan allowlisted template + resolve mentions → **parameterized Cypher only** (never model Cypher) |
| M Vector path | `vector_retriever.py` | Embed question → HNSW top-k; returns `chunk_id`, text, `entity_ids`, score |
| Glue | `retrieve.py` | `route_question` → run graph and/or vector |

**Router design notes (important for next agent):**
- Confidence is **LLM self-reported**, not a calibrated classifier
- Prompt includes **low-confidence few-shot examples** so Haiku can return scores below ~0.75
- `model_route` = what Haiku said; `effective_route` = after threshold fallback

**Graph templates (allowlist only):**  
`company_products`, `company_risks`, `company_competitors`, `company_suppliers`, `company_subsidiaries`, `entity_outgoing`

**Verified smoke:**
- `"What product lines does Apple produce?"` → template `company_products`, entity `APPLE`, many `PRODUCES_PRODUCT` facts with `source_chunk_ids`
- `"What is AppleCare?"` → router `vector` only → passages (Item1:0 has `APPLECARE` in `entity_ids`)

---

## Pipeline (as implemented)

```text
ingest → extract (Claude) → resolve → graph_writer (Neo4j MERGE)
       ↘ embed (OpenAI) → pgvector (HNSW, entity_ids, shared chunk_id)

question → router (K)
            ├─ graph (L)  → Neo4j facts + source_chunk_ids
            └─ vector (M) → passages + chunk_ids
            (Phase 4 will merge these into a cited answer)
```

---

## Local credentials (Docker — not Neo4j Aura)

| Service | Connect |
|---------|---------|
| Neo4j Browser | http://localhost:7474 — user `neo4j` / password `password` — bolt `neo4j://localhost:7687` |
| Postgres | `localhost:5432` — db/user `secgraph` / password `password` |

Do **not** use neo4j.com Google/Aura login for this project.

---

## Locked decisions (do not silently change)

- Sections: Item **1 / 1A / 7** only
- Chunk ~**3000** tokens / ~**200** overlap
- Claude + Instructor for structured extraction; Haiku for router / graph plan
- Embeddings: OpenAI `text-embedding-3-small`, soft-match threshold **0.92**
- Neo4j: **MERGE**, uniqueness on `id`, `source_chunk_ids` on edges
- Cross-link: shared **`chunk_id`**
- Graph queries: **parameterized Cypher templates only** — never LLM-emitted Cypher
- Learning Protocol: one step; explain WHY; wait for confirmation before coding
- `EXTRACTION_MAX_TOKENS=16384` recommended in `.env`
- Paid extraction: `budget.py` first, then `--confirm`

## Closed-world ontology

**Entities:** Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive  

**Rels:** OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

---

## What is NOT done (do not claim on resume yet)

- FastAPI Q&A endpoint
- Final natural-language answer with citation validation
- Hybrid vs vector-only accuracy by hop count (Phase 5 table)
- Multi-company corpus at scale
- Public README portfolio artifact

---

## NEXT → Phase 4 (plan first)

Curriculum requirements:

1. Convert graph paths to readable statements; keep vector passages
2. Deduplicate; label graph-derived vs retrieved text in the prompt
3. Require a **citation per claim**
4. Validate each citation resolves to a **retrieved** `chunk_id`; reject/regenerate if not

Suggested step breakdown (propose, then wait for user confirm):

- **Step N:** Answer schema (`claims[]` + `citation_chunk_ids[]`) + prompt that consumes `retrieve.py` output
- **Step O:** Citation validator (every cite ∈ retrieved graph chunk ids ∪ vector chunk ids)
- **Step P:** CLI/smoke: ask AAPL questions → printed answer + citations
- Later: FastAPI wrapper (can be Phase 4 end or early Phase 5)

---

## Copy-paste into a NEW Cursor chat

```text
You are continuing the SEC GraphRAG project on PC.
Read `.agents/AGENTS.md` and `HANDOFF.md` completely. Obey the Learning Protocol:
one step at a time, explain WHY, wait for my confirmation before coding.

Phases 1–3 are COMPLETE and live-verified:
- Phase 1: Neo4j graph (AAPL 60 nodes / 59 rels, Company id APPLE)
- Phase 2: pgvector HNSW + entity_ids + shared chunk_id (recall@3=1.0 on tiny set)
- Phase 3: router.py + graph_retriever.py + vector_retriever.py + retrieve.py

Immediate task: propose Phase 4 (merge graph+vector evidence into a grounded answer
with per-claim citation validation) — plan only, do not implement until I confirm.

Do NOT invent architecture. Do NOT emit model-written Cypher. Do NOT commit My Resume/.
```

---

## Windows quick commands

```powershell
# Infra
docker compose up -d

# Phase 1–2 (usually cached / free after first run)
$env:EXTRACTION_MAX_TOKENS = "16384"
.\.venv\Scripts\python.exe budget.py AAPL
.\.venv\Scripts\python.exe graph_writer.py AAPL --confirm
.\.venv\Scripts\python.exe embedder.py AAPL --link-entities
.\.venv\Scripts\python.exe recall_eval.py --k=3

# Phase 3
.\.venv\Scripts\python.exe router.py --demo
.\.venv\Scripts\python.exe graph_retriever.py "What product lines does Apple produce?"
.\.venv\Scripts\python.exe vector_retriever.py "What is AppleCare?"
.\.venv\Scripts\python.exe retrieve.py "How is Apple exposed to China trade risks?"
```

---

## File map (high signal)

| Area | Files |
|------|-------|
| Config | `config.py`, `.env` (local only) |
| Ingest / extract / resolve / write | `ingest.py`, `extractor.py`, `resolver.py`, `graph_writer.py`, `schemas.py` |
| Cost | `budget.py` |
| Vectors | `vector_db.py`, `embedder.py`, `recall_eval.py` |
| Route / retrieve | `router.py`, `graph_retriever.py`, `vector_retriever.py`, `retrieve.py` |
| Docs | `HANDOFF.md`, `.agents/AGENTS.md` |

**Do not commit:** `.env`, `./data/*.db`, `My Resume/`
