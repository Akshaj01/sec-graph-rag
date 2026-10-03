# SEC GraphRAG

Hybrid **Knowledge Graph + Vector RAG** over SEC **10-K** filings (closed-world ontology, shared `chunk_id` citations).

## Benchmark (hybrid vs vector-only)

### Multi-company smoke (current)

Suite: `multi_company_smoke` v1 — **24** hand-labeled questions over the local **10-ticker** Item 1/1A/7 corpus (`AAPL AMZN GOOGL JNJ JPM META MSFT NFLX NVDA XOM`).  
Metric: keyword recall on answer text (OOS = correct refuse). **Not** a 50–100 Q portfolio eval.

| Hop / bucket | Hybrid score | Vector-only score | n |
|--------------|-------------:|------------------:|--:|
| Hop 0 (definitions) | 0.47 | 0.47 | 6 |
| Hop 1 (single edge) | **0.94** | 0.69 | 8 |
| Hop 2 (compare / multi-rel) | **1.00** | 0.78 | 6 |
| OOS (must refuse) | **1.00** | **1.00** | 4 |
| **Overall mean** | **0.85** | 0.71 | 24 |

| Mode | Mean latency | Notes |
|------|-------------:|-------|
| Hybrid | ~9.7 s | Multi-template graph plans + evidence caps; hop-2 no longer refuses/errors |
| Vector-only | ~7.2 s | Same hop-0 misses; weaker on graph-style hop 1–2 |

Source report: `benchmarks/results/multi_company_smoke_full_rebench.json`  
Suite: `benchmarks/multi_company_smoke.json`  
Re-run (paid): `python benchmark_runner.py --suite benchmarks/multi_company_smoke.json --confirm`

**How to read this table:** After hop-2 packing / multi-template / false-refuse fixes, **hybrid leads overall and on hop 1–2**. Hop 0 dipped (some definition asks refused or missed keywords) — still keyword recall, not human accuracy. OOS refuse is clean on this run.

### AAPL 5-chunk smoke (historical)

Suite: `aapl_smoke` v1 — **20** questions on an **AAPL 5-chunk** smoke corpus (accession `0000320193-25-000079`).

| Hop / bucket | Hybrid score | Vector-only score | n |
|--------------|-------------:|------------------:|--:|
| Hop 0 (definitions) | **1.00** | **1.00** | 4 |
| Hop 1 (single edge) | **1.00** | 0.88 | 8 |
| Hop 2 (compare / multi-rel) | 0.50 | **1.00** | 4 |
| OOS (must refuse) | **1.00** | **1.00** | 4 |
| **Overall mean** | 0.90 | **0.95** | 20 |

Source report: `benchmarks/results/aapl_smoke_20260825T070159Z.json`

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

## Growing the corpus

`grow_corpus.py` batches ingest → extract → resolve → Neo4j write → pgvector
embed across multiple tickers, with an aggregate cost estimate gated behind
`--confirm`:

```powershell
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM XOM PFE --budget    # estimate only
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM XOM PFE --confirm   # full filings
```

See `HANDOFF.md` → "Growing the corpus" for usage, a suggested starter
ticker list, and two id/routing fixes that only matter once a second company
is in the corpus.

## Phase status

| Phase | Status |
|-------|--------|
| 1 Graph extraction | Done |
| 2 pgvector + recall@k | Done |
| 3 Route + retrieve | Done |
| 4 Grounded answer + citation validation | Done |
| 5 Benchmark vs vector-only | Done |

See `HANDOFF.md` and `.agents/AGENTS.md` for the full build log and Learning Protocol.
