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

## Phase 1 Build Roadmap (COMPLETE — code written)
- Step A: Environment & Docker Setup (`docker-compose.yml`, `config.py`, `requirements.txt`) [COMPLETED]
- Step B: Pydantic Schemas & Ontology Definitions (`schemas.py`) [COMPLETED]
- Step C: SEC 10-K Fetching, Chunking & Hash Caching (`ingest.py` / SQLite) [COMPLETED]
- Step D: Schema Extraction with Gemini/Claude (`extractor.py`) [COMPLETED]
- Step E: Entity Resolution & Canonical Mapping (`resolver.py`) [COMPLETED]
- Step F: Idempotent Neo4j Cypher Writes (`graph_writer.py`) [COMPLETED]

## Immediate next (before Phase 2)
1. Start Neo4j: `docker compose up -d`
2. Run: `.venv/bin/python graph_writer.py AAPL`
3. Verify in Neo4j Browser (`http://localhost:7474`) that Company `APPLE` exists and edges carry `source_chunk_ids`
4. Re-run writer once to confirm idempotent MERGE (counts stay flat)

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
