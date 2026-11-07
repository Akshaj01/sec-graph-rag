# SEC GraphRAG

Hybrid knowledge-graph + vector RAG over ten companies' 10-Ks. Closed ontology in Neo4j, the same chunks in pgvector, router picks graph and/or vectors, answers cite only chunks from that retrieval.

On 44 hop-stratified questions, the graph path wins where relationships matter (multi-relation / hop-2: **1.00** vs **0.88**). Overall the gap is small — three temperature-0 runs average hybrid **0.93** vs vector-only **0.90** (gap **+0.028**); the paired bootstrap 95% CI for that gap includes zero. Vector-only retrieves as well or better (ties recall@5 / MRR; leads recall@10). LLM judge hold-out κ **0.84** (two labels corrected after seeing judge scores).

## Results

44 questions. The score is an LLM judge against required facts. Out of scope means a correct refuse. Cells are the **mean of three** temperature-0 runs ([`three_run_means.md`](benchmarks/results/three_run_means.md)).

| Hop / bucket | Hybrid | Vector-only | n |
|--------------|-------:|------------:|--:|
| Hop 0 (definitions) | **0.94** | **0.94** | 8 |
| Hop 1 (single edge) | **0.83** | 0.81 | 16 |
| Hop 2 (compare / multi-rel) | **1.00** | 0.88 | 8 |
| OOS (must refuse) | **1.00** | **1.00** | 12 |
| **Overall (mean of runs)** | **0.93** | 0.90 | 44 |

Hop-2 is the real finding. Per-item means across the three runs, then paired bootstrap: hop-2 gap **+0.116** (95% CI **0.024 – 0.220**, entirely above zero). Overall gap **+0.028** (95% CI **−0.006 – 0.067**, includes zero). See [`ablation_bootstrap_three_run.md`](benchmarks/results/ablation_bootstrap_three_run.md).

Retrieval is scored separately, on 32 answerable items. Out-of-scope items are skipped.

| | Recall@5 | Recall@10 | MRR |
|--|--------:|----------:|----:|
| Graph | 0.41 | 0.46 | 0.40 |
| Vector | **0.84** | **0.94** | **0.70** |
| Hybrid | **0.84** | 0.91 | **0.70** |

Hybrid alternates a vector chunk, then a graph chunk, and skips a chunk already used. Graph edges are ordered by how many question words they hit. Extraction confidence only breaks a tie. Both lists are retrieved even when the router said graph. Graph-only recall moves between runs because the planner does not return the same edges every time.

## Example

**Q:** What product lines does Apple produce? · route `graph` · `citations_valid`

> Apple produces hardware (iPhone, iPad, Mac, Wearables…), OSes, and services (AppleCare, Cloud Services, …).

Cites include `0000320193-25-000079:Item1:0`, `…:Item7:0`.

**Q:** What compute products does NVIDIA produce, and what geopolitical risks is it exposed to? · route `both`

> NVIDIA produces data-center / gaming GPUs (A100, H100, …) and faces geopolitical / export-control risk (e.g. China-related controls) among other exposures.

Cites include `0001045810-26-000021:Item1:0`, `…:Item1A:3`, …

<p align="center">
  <img src="docs/images/neo4j-graph.png" alt="Neo4j: Apple PRODUCES_PRODUCT graph" width="48%" />
  <img src="docs/images/neo4j-risks.png" alt="Neo4j: Apple EXPOSED_TO_RISK graph" width="48%" />
</p>
<p align="center">
  <img src="docs/images/ask-api.png" alt="POST /ask successful response with citations" width="80%" />
</p>

## How the numbers were measured

Suite `multi_company_smoke` v4. Generation headline: mean of three temperature-0 runs —

- [`multi_company_smoke_temp0_p6.json`](benchmarks/results/multi_company_smoke_temp0_p6.json)
- [`multi_company_smoke_temp0_p6_run2.json`](benchmarks/results/multi_company_smoke_temp0_p6_run2.json)
- [`multi_company_smoke_temp0_p6_run3.json`](benchmarks/results/multi_company_smoke_temp0_p6_run3.json)

Summary: [`three_run_means.md`](benchmarks/results/three_run_means.md). Bootstrap on per-item three-run means: [`ablation_bootstrap_three_run.md`](benchmarks/results/ablation_bootstrap_three_run.md). An older pre-fix package (hybrid **0.86** / vector **0.89**) lives under [`benchmarks/results/archive/`](benchmarks/results/archive/).

**Judge calibration (rubric v1):** held-out linear weighted κ **0.84** (raw agreement 19/20). Two first-pass scores of 1.0 were corrected after seeing the judge (Meta AI competition → 0, Meta AI glasses → 0.5), so treat κ as a calibration check, not a fully blind panel. Self-agreement on a later re-label is κ **0.42** (13/15). [`benchmarks/calibration/RESULTS.md`](benchmarks/calibration/RESULTS.md).

CI fails if a committed hybrid recall@10 drops more than **0.02** from **0.917**. It reads the saved file and does not call a model. Retrieval tables: [`benchmarks/results/retrieval_v4.md`](benchmarks/results/retrieval_v4.md).

### 60-second pass

1. Generation: three-run hybrid **0.93** vs vector **0.90**; hop-2 **1.00** vs **0.88** with a CI above zero; overall CI includes zero.
2. One graph question: `python answer.py "What product lines does Apple produce?" --ticker AAPL`.
3. One refusal: a question the 10-K corpus cannot answer (Tesla battery supply, Bitcoin on Apple's balance sheet).
4. Soft misses still open on hop-1 product / competition asks. See **What didn't work**.

## Design decisions

Locked during the eval phase. Retrieval and generation are separate scores. A high answer with the wrong gold chunk is still a retrieval miss. The judge grades required facts, not a paragraph match to the gold line. Reported κ is the hold-out, not the 24/24 debug sheet. The ablation is hybrid versus vector-only.

The system constraints that came first: six entity types and eight relationship types, Cypher only from allowlisted templates, and a citation must be in this retrieval's chunk allowlist.

## What didn't work

Hybrid answers with three-run mean below 1.0. Detail is in [`docs/PROBLEMS_AND_FIXES.md`](docs/PROBLEMS_AND_FIXES.md).

| Item | 3-run hybrid | What happened |
|------|-------------:|----------------|
| `hop1_aapl_competes_meta` | 0.00 | Graph route missed the compete edge (vector also 0) |
| `hop0_jpm_credit_risk` | 0.50 | Partial credit-risk coverage |
| `hop1_nvda_products` | 0.50 | Compute product list incomplete (vector 0.75) |
| `hop1_googl_waymo` | 0.50 | Names Waymo; thin autonomous ride-hailing detail |
| `hop1_msft_products` | 0.71 | Azure/Xbox still flaky across runs (vector 0.25) |
| `hop1_meta_ai_competition` | 0.75 | Soft vs vector 0.875 |
| `hop1_aapl_products` | 0.83 | Product list incomplete vs required facts |

Earlier systems bugs worth saying anyway: keyword overlap scored wrong answers as 1.0, a 1200-character window hid AppleCare and Azure, and an Apple product answer once cited Meta's 10-K.

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
  --rejudge benchmarks/results/multi_company_smoke_temp0_p6_run3.json --confirm
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
| Eval | `benchmarks/`, `benchmark_runner.py`, `benchmark_judge.py`, `bootstrap_ci.py`, `chunk_ticker.py` |
| Failure log | [`docs/PROBLEMS_AND_FIXES.md`](docs/PROBLEMS_AND_FIXES.md) — bugs we hit and how we fixed them |
| License | [`LICENSE`](LICENSE) (MIT) |
