# SEC GraphRAG Project Rules

## Learning Protocol (STRICT REQUIREMENT)
- Do NOT build the entire project or Phase 1 all at once.
- Move strictly STEP-BY-STEP based on the roadmap.
- After each step, you must:
  1. Explain the "WHY" behind the technical decision or design pattern.
  2. Ask if the user understands or has questions before moving to the next step.
  3. Pause and wait for explicit confirmation to proceed.

## Technical Stack & Dependencies
- Language & Framework: Python 3.11+, FastAPI, Pydantic v2
- Graph Database: Neo4j (via official Neo4j Python Driver & Cypher)
- Vector Store / Embeddings: OpenAI text-embedding-3-small (and pgvector compatible)
- Data Source: SEC EDGAR API via `edgartools`
- Agent/LLM Provider: Gemini Pro / Claude API (via Instructor/Pydantic structured outputs)
- Infrastructure: Docker Compose (Neo4j with APOC plugins)

## Closed-World Ontology (STRICT REQUIREMENT)
To prevent unqueryable node explosion, enforce this strict schema in all extraction prompts and Pydantic models:
- **Allowed Entity Types (6)**: Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive
- **Allowed Relationship Types (8)**: OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

## Phase 1 Build Roadmap (COMPLETE — live-verified on PC)
- Step A: Environment & Docker Setup (`docker-compose.yml`, `config.py`, `requirements.txt`) [COMPLETED]
- Step B: Pydantic Schemas & Ontology Definitions (`schemas.py`) [COMPLETED]
- Step C: SEC 10-K Fetching, Chunking & Hash Caching (`ingest.py` / SQLite) [COMPLETED]
- Step D: Schema Extraction with Gemini/Claude (`extractor.py`) [COMPLETED]
- Step E: Entity Resolution & Canonical Mapping (`resolver.py`) [COMPLETED]
- Step F: Idempotent Neo4j Cypher Writes (`graph_writer.py`) [COMPLETED + live smoke test on PC]

PC verification (2026-08-23): AAPL 5-chunk run → 60 nodes, 59 relationships in Neo4j; Company `APPLE` with `mention_count=5`. See `HANDOFF.md` for setup notes (Docker Desktop, `EXTRACTION_MAX_TOKENS=16384` for dense Item 1 chunks).

## Immediate next → Phase 2
- Step G: Postgres + pgvector in Docker [COMPLETED — `docker-compose.yml`, `vector_db.py`, `config.py`]
- Step H: Embed chunks + store in pgvector (shared `chunk_id`) [COMPLETED — `embedder.py`]
- Step I: Entity cross-links in vector metadata [COMPLETED — `entity_ids` TEXT[] + `--link-entities`]
- Step J: HNSW index + recall@k smoke test [COMPLETED — `recall_eval.py`]

**Phase 2 COMPLETE.**

## Phase 3 — Route questions to graph vs vectors
- Step K: Router schema + classifier (`router.py`) [COMPLETED — Haiku few-shot, confidence → BOTH, SQLite log]
- Step L: Graph retrieval path (parameterized Cypher templates) [COMPLETED — `graph_retriever.py`]
- Step M: Vector retrieval path (wire to existing pgvector search) [COMPLETED — `vector_retriever.py`, `retrieve.py`]

**Phase 3 COMPLETE (retrieval only).**

## Phase 4 — Merge into one grounded answer [COMPLETED — live AAPL smoke 2026-08-24]
- Step N: Format evidence + structured draft answer (`answer.py`) [COMPLETED]
- Step O: Citation validator (cite ∈ retrieved chunk ids; reject/regenerate) [COMPLETED]
- Step P: CLI smoke [COMPLETED] — FastAPI deferred to Phase 5 wrap

**Phase 4 COMPLETE.**

## Phase 5 — Benchmark vs plain vector RAG [COMPLETED]
- Step Q: Labeled suite + schemas [COMPLETED]
- Step R: Hybrid vs vector-only runner [COMPLETED]
- Step S: README accuracy table [COMPLETED]
- Step T: FastAPI `/ask` (`api.py`) [COMPLETED]

**Phase 5 COMPLETE.** Project 1 curriculum done on AAPL smoke scale.

Do not skip Learning Protocol.
See `HANDOFF.md` for full PC verification notes, credentials, CLI commands, and the copy-paste prompt for a new chat.

## BASWE Project 1 — remaining phases (follow in order)
Do **not** invent a different architecture. These are the curriculum phases after graph extraction:

### Phase 2 — Vector index alongside the graph
- Embed the **same chunks** into pgvector
- Metadata: document id, section path, date, entity ids mentioned
- **Shared chunk ids** between Neo4j and vectors (this is the cross-link key)
- Index with HNSW; measure recall@k on a small labeled set before building a router

### Phase 3 — Route questions to graph vs vectors
- Cheap router (small model / few-shot) returning an enum; low-confidence → run both
- Graph path: connection / multi-hop / comparison / aggregation questions
- Vector path: definitions / single-fact / policy-style questions
- Graph path: extract entities → resolve to node ids → **parameterized Cypher templates only** (never let the model emit raw Cypher)
- Log every routing decision

### Phase 4 — Merge into one grounded answer
- Convert graph paths to readable statements; keep vector passages
- Deduplicate; label graph-derived vs retrieved text in the prompt
- Require a citation per claim; validate citation resolves to a retrieved chunk id; reject/regenerate if not

### Phase 5 — Benchmark vs plain vector RAG
- 50–100 questions stratified by hop count + out-of-scope refusals
- Report accuracy by hop count, latency, cost/query, one-time graph ingest cost
- Put the benchmark table at the top of the README (portfolio artifact)

### Done when (Project 1)
FastAPI answers with validated citations; README opens with hybrid vs vector-only accuracy by hop count.

### Common failure modes to avoid
- Open-ended ontology
- Skipping entity resolution
- Model-written raw Cypher
- Corpus with no real relationships
