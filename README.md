# SEC GraphRAG

Hybrid **Knowledge Graph + Vector RAG** over SEC **10-K** filings (closed-world ontology, shared `chunk_id` citations).

## Benchmark (hybrid vs vector-only)

Suite: `aapl_smoke` v1 — **20** hand-labeled questions on an **AAPL 5-chunk** smoke corpus (accession `0000320193-25-000079`).  
Metric: keyword recall on answer text (OOS = correct refuse). Not a 50–100 Q portfolio eval.

| Hop / bucket | Hybrid score | Vector-only score | n |
|--------------|-------------:|------------------:|--:|
| Hop 0 (definitions) | **1.00** | **1.00** | 4 |
| Hop 1 (single edge) | **1.00** | 0.88 | 8 |
| Hop 2 (compare / multi-rel) | 0.50 | **1.00** | 4 |
| OOS (must refuse) | **1.00** | **1.00** | 4 |
| **Overall mean** | 0.90 | **0.95** | 20 |

| Mode | Mean latency | Est. cost / query | Est. total (20 Q) |
|------|-------------:|------------------:|------------------:|
| Hybrid | **11.0 s** | **~$0.029** | ~$0.55 |
| Vector-only | 12.4 s | ~$0.046 | ~$0.93 |

Source report: `benchmarks/results/aapl_smoke_20260825T070159Z.json`  
Re-run: `python benchmark_runner.py --confirm`

**How to read this table:** On this tiny corpus, product/risk names often appear in the same vector chunks the graph was extracted from, so vector-only keyword scores stay high — including hop 2. Hybrid hop 2 dropped because two compare questions hit answer-generation failures / forced refuse (not because retrieval found nothing). Expand the corpus and question set before treating these numbers as a portfolio claim.

One-time graph ingest cost: run `python budget.py AAPL` before `--confirm` extraction (smoke extract is cached after the first paid run).

---

## What this is

```text
ingest → extract (Claude) → resolve → Neo4j MERGE
       ↘ embed (OpenAI) → pgvector (HNSW, entity_ids, shared chunk_id)

question → router (Haiku)
            ├─ graph → parameterized Cypher templates only
            └─ vector → top-k passages
         → grounded answer + citation allowlist validation
```

**Locked rules:** Item 1 / 1A / 7 only · no model-written Cypher · citations must be retrieved `chunk_id`s · closed ontology (6 entity types, 8 rels).

## Quick start (local Docker)

```powershell
docker compose up -d
# .env: ANTHROPIC_API_KEY, OPENAI_API_KEY, EXTRACTION_MAX_TOKENS=16384

.\.venv\Scripts\python.exe answer.py "What product lines does Apple produce?"
.\.venv\Scripts\python.exe answer.py "What is AppleCare?"
.\.venv\Scripts\python.exe benchmark.py
.\.venv\Scripts\python.exe benchmark_runner.py --ids hop0_applecare,hop1_products
```

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

- `GET /health` — liveness
- `POST /ask` — body: `{"question": "...", "ticker": "AAPL", "vector_only": false}`
- Interactive docs: http://127.0.0.1:8000/docs

Neo4j Browser: http://localhost:7474 (`neo4j` / `password`)  
Postgres: `localhost:5432` / `secgraph` / `password`

## Phase status

| Phase | Status |
|-------|--------|
| 1 Graph extraction | Done |
| 2 pgvector + recall@k | Done |
| 3 Route + retrieve | Done |
| 4 Grounded answer + citation validation | Done |
| 5 Benchmark vs vector-only | Done |

See `HANDOFF.md` and `.agents/AGENTS.md` for the full build log and Learning Protocol.
