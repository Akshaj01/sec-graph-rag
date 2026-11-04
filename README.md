# SEC GraphRAG

Hybrid **knowledge-graph + vector RAG** over SEC **10-K** filings: extract a closed financial ontology into Neo4j, embed the same chunks into pgvector, route each question to graph and/or vectors, and answer only with **validated chunk citations**.

Built as an end-to-end systems project (not a ChatGPT wrapper): closed-world schema, **no model-written Cypher**, citation allowlists, cost-gated corpus growth, and a hop-stratified hybrid vs vector-only benchmark.

---

## Why this exists

| Problem | Approach here |
|---------|----------------|
| Embeddings alone blur *relationships* (who competes with whom, what risks attach to which issuer) | Graph path over a fixed ontology + parameterized Cypher templates |
| LLMs invent citations | Every claim’s `chunk_id` must appear in *this* retrieval’s allowlist (else reject / regenerate) |
| Multi-company graphs silently merge the wrong nodes | Ticker-scoped risks/products/execs; shared companies keep `home_ticker` + `tickers[]` |
| Cross-filing extract invents edges on global companies (e.g. Meta→`APPLE` products) | Issuer-owned write gate + retrieve-time chunk ticker filter on graph evidence |
| “RAG demos” skip measurement | Hop-stratified **hybrid vs vector-only** suite with LLM-as-judge (keyword secondary) |

---

## Architecture

```text
10-K Items 1 / 1A / 7
  → chunk + content-hash cache
  → Claude + Instructor → closed ontology JSON
  → entity resolution → Neo4j MERGE (edges carry source_chunk_ids)
  → same chunks → OpenAI embeddings → pgvector (shared chunk_id)

Question → Haiku router (graph | vector | both)
  → graph: allowlisted Cypher templates only (multi-template for hop-2)
  → vector: HNSW top-k
  → grounded answer + citation validation → FastAPI POST /ask
```

**Ontology (6 / 8):** Company, Subsidiary, Supplier, ProductLine, RiskFactor, Executive · OWNS_SUBSIDIARY, SUPPLIED_BY, COMPETES_WITH, EXPOSED_TO_RISK, PRODUCES_PRODUCT, DEPENDS_ON, LED_BY, OPERATES_IN_SEGMENT

<p align="center">
  <img src="docs/images/neo4j-graph.png" alt="Neo4j: Apple PRODUCES_PRODUCT graph" width="48%" />
  <img src="docs/images/neo4j-risks.png" alt="Neo4j: Apple EXPOSED_TO_RISK graph" width="48%" />
</p>
<p align="center">
  <img src="docs/images/ask-api.png" alt="POST /ask successful response with citations" width="80%" />
</p>


---

## Benchmark (hybrid vs vector-only)

Suite: `multi_company_smoke` v4 — **44** hand-labeled questions on a local **10-ticker** corpus (`AAPL AMZN GOOGL JNJ JPM META MSFT NFLX NVDA XOM`, full Item 1/1A/7). v4 adds `gold_chunk_ids` on the same questions; the generation numbers below are the v3 judged run. Includes harder author-written items and more out-of-scope refuses.

**Primary metric:** LLM-as-judge (Haiku + Instructor) vs `required_facts` / `gold_answer`.  
OOS = correct refuse. Keyword recall secondary. Not a human panel.

**Judge calibration (rubric v1):** held-out linear weighted κ vs human is **0.00** (raw agreement 17/20). Self-agreement on a later re-label of 15 items is κ **0.42** (13/15). The older 24/24 sheet is history, not κ. Write-up: `benchmarks/calibration/RESULTS.md`.

| Hop / bucket | Hybrid | Vector-only | n |
|--------------|-------:|------------:|--:|
| Hop 0 (definitions) | **0.94** | 0.92 | 8 |
| Hop 1 (single edge) | **0.88** | 0.79 | 16 |
| Hop 2 (compare / multi-rel) | **0.96** | 0.88 | 8 |
| OOS (must refuse) | **1.00** | **1.00** | 12 |
| **Overall mean** | **0.94** | 0.89 | 44 |

Report: [`benchmarks/results/multi_company_smoke_judged.json`](benchmarks/results/multi_company_smoke_judged.json)  
(full v3 rebench 2026-10-28; `hop2_jpm_credit_vs_market` hybrid patched from targeted resmoke — full-run flake 0.375→1.0; also `multi_company_smoke_v3_full.json` / `…_jpm_hop2_resmoke.json`)

**How to read it:** After fixing false-refuse / bad graph dumps / planner crashes, **hybrid leads overall** on the harder n=44 suite (**0.94 vs 0.89**). **Hop 2 is again the clearest structural win** (0.96 vs 0.88). OOS is clean on both. The older curated **n=24** sync was hybrid **0.98** / vector **0.92** (`multi_company_smoke_full_sync.json`). Remaining soft spots are mostly Meta product/apps wording — not systemic hybrid loss.

**Uncertainty (paired bootstrap, 10,000 draws, seed 0):** the gap is hybrid minus vector-only. A 95% interval that includes values below zero means a resample of this suite can wipe out the lead.

| Slice | n | Gap | 95% CI |
|-------|--:|----:|--------|
| Overall | 44 | 0.052 | −0.026 to 0.136 |
| Hop 2 | 8 | 0.083 | 0.000 to 0.250 |

Full slice table: [`benchmarks/results/ablation_bootstrap.md`](benchmarks/results/ablation_bootstrap.md).

**Recommendation:** Hybrid scores higher on average (0.052 overall, 0.083 on hop 2), and neither 95% interval sits entirely above zero, so the lead is not stable on this suite.

### Retrieval (separate from the answer score)

Retrieve-only, scored against v4 `gold_chunk_ids`. Macro-average over the 32 answerable items. Out-of-scope items are skipped. **recall@k** is the fraction of gold chunks in the top k. **MRR** is 1 / rank of the first gold chunk.

| Hop | n | System | Recall@5 | Recall@10 | MRR |
|-----|--:|--------|--------:|----------:|----:|
| Hop 0 | 8 | graph | 0.44 | 0.44 | 0.31 |
| Hop 0 | 8 | vector | **1.00** | **1.00** | **0.71** |
| Hop 0 | 8 | hybrid | **1.00** | **1.00** | 0.61 |
| Hop 1 | 16 | graph | 0.36 | 0.47 | 0.29 |
| Hop 1 | 16 | vector | **0.73** | **0.85** | **0.59** |
| Hop 1 | 16 | hybrid | 0.46 | 0.65 | 0.39 |
| Hop 2 | 8 | graph | 0.50 | 0.67 | 0.57 |
| Hop 2 | 8 | vector | **0.81** | **1.00** | **0.79** |
| Hop 2 | 8 | hybrid | 0.75 | 0.92 | 0.62 |
| **Overall** | 32 | graph | 0.42 | 0.51 | 0.37 |
| **Overall** | 32 | vector | **0.82** | **0.93** | **0.67** |
| **Overall** | 32 | hybrid | 0.67 | 0.80 | 0.51 |

Report: [`benchmarks/results/retrieval_v4.md`](benchmarks/results/retrieval_v4.md).

Vector leads retrieval. Hybrid leads generation. Hybrid ranks graph chunks before vector passages, and those graph chunks are often a different passage than the gold prose chunk, so they push the gold id down the list. The answer can still be right because the graph statement carries the fact.

**Systems fixes from eval:** issuer write gate + chunk ticker filter; `COMPETES_WITH` provenance exempt; MedTech `both` + drop unmatched products; OOS topic-gated refuse; Apple supply/China query-centered windows; topic-gate open product/competition asks; AWS supplier templates + ranking; planner template coerce; narrative/SKU → `both`.

---

## Example answers (from the hybrid rebench)

**Q:** What product lines does Apple produce? · route `graph` · `citations_valid`

> Apple produces hardware (iPhone, iPad, Mac, Wearables…), OSes, and services (AppleCare, Cloud Services, …).

Cites include `0000320193-25-000079:Item1:0`, `…:Item7:0`.

**Q:** What compute products does NVIDIA produce, and what geopolitical risks is it exposed to? · route `both`

> NVIDIA produces data-center / gaming GPUs (A100, H100, …) and faces geopolitical / export-control risk (e.g. China-related controls) among other exposures.

Cites include `0001045810-26-000021:Item1:0`, `…:Item1A:3`, …

---

## Quick start

```bash
docker compose up -d
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY + OPENAI_API_KEY
```

**Ask (needs a built local corpus — your Docker volumes + `data/` caches):**

```bash
python answer.py "What product lines does Apple produce?" --ticker AAPL
python answer.py "What is AppleCare?" --ticker AAPL

python -m uvicorn api:app --host 127.0.0.1 --port 8000
# POST http://127.0.0.1:8000/ask
# {"question":"What product lines does Apple produce?","ticker":"AAPL"}
```

**Grow corpus (paid — always budget first):**

```bash
python grow_corpus.py MSFT JPM --budget
python grow_corpus.py MSFT JPM --confirm --max-chunks 5   # cheap smoke
```

**Benchmark (paid answer run; judge is cheaper Haiku):**

```bash
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json --limit 2
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json --confirm
# Re-score saved answers with LLM judge (no answer re-run):
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json \
  --rejudge benchmarks/results/multi_company_smoke_full_rebench.json --confirm
```

Neo4j Browser: http://localhost:7474 (`neo4j` / `password` by default) · API docs: http://127.0.0.1:8000/docs

---

## Repo map

| Area | Files |
|------|--------|
| Ingest / extract / resolve / write | `ingest.py`, `extractor.py`, `resolver.py`, `graph_writer.py` |
| Vectors | `embedder.py`, `vector_db.py` |
| Retrieve / answer / API | `router.py`, `graph_retriever.py`, `vector_retriever.py`, `answer.py`, `api.py` |
| Batch growth / budget | `grow_corpus.py`, `budget.py` |
| Eval | `benchmarks/`, `benchmark_runner.py`, `benchmark_judge.py`, `chunk_ticker.py` |
| Learning / interview log | [`docs/PROBLEMS_AND_FIXES.md`](docs/PROBLEMS_AND_FIXES.md) — bugs we hit and how we fixed them |
| Internal build notes | [`docs/dev-notes/`](docs/dev-notes/) (curriculum handoff; not required to use the system) |

