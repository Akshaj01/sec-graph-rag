# SEC GraphRAG

Question answering over ten companies' 10-K filings that combines a **knowledge graph** (for relationships like *who competes with whom* or *which risks attach to which company*) with **vector search** (for everything else). Every answer cites the exact filing passages it came from, and citations to anything that wasn't retrieved are rejected.

On 44 hop-stratified questions, the graph path wins where relationships matter (multi-relation / hop-2: **1.00** vs **0.88**). Overall the gap is small — three temperature-0 runs average hybrid **0.93** vs vector-only **0.90** (gap **+0.028**); the paired bootstrap 95% CI for that gap includes zero. Vector-only retrieves as well or better (ties recall@5 / MRR; leads recall@10). LLM judge hold-out κ **0.84** (two labels corrected after seeing judge scores).

Companies: AAPL, META, MSFT, NVDA, GOOGL, AMZN, JPM, NFLX, XOM, JNJ.

## Results

44 questions. The score is an LLM judge against required facts. Out of scope means a correct refuse. Cells are the **mean of three** temperature-0 runs ([`three_run_means.md`](benchmarks/results/three_run_means.md)).

| Hop / bucket | Hybrid | Vector-only | n |
|--------------|-------:|------------:|--:|
| Hop 0 (definitions) | **0.94** | **0.94** | 8 |
| Hop 1 (single edge) | **0.83** | 0.81 | 16 |
| Hop 2 (compare / multi-rel) | **1.00** | 0.88 | 8 |
| OOS (must refuse) | **1.00** | **1.00** | 12 |
| **Overall (mean of runs)** | **0.93** | 0.90 | 44 |

Hop-2 is the real finding. Per-item means across the three runs, then paired bootstrap: hop-2 gap **+0.116** (95% CI **0.024 – 0.220**, entirely above zero). Overall gap **+0.028** (95% CI **−0.006 – 0.067**, includes zero). Hop-2 is only 8 questions, and the interval reflects that. See [`ablation_bootstrap_three_run.md`](benchmarks/results/ablation_bootstrap_three_run.md).

Retrieval is scored separately, on 32 answerable items. Out-of-scope items are skipped.

| | Recall@5 | Recall@10 | MRR |
|--|--------:|----------:|----:|
| Graph | 0.41 | 0.46 | 0.40 |
| Vector | **0.84** | **0.94** | **0.70** |
| Hybrid | **0.84** | 0.91 | **0.70** |

The graph adds little to *finding* the right passage — vector search already does that well. The likely reason it still helps the *answer* on multi-relation questions: it hands the model explicit edges (company → competitor → risk) instead of leaving it to infer them from text.

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

Both stores share the same `chunk_id`, so a graph edge always points back to the passage it was extracted from, and graph and vector evidence can be merged and cited the same way.

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

Suite `multi_company_smoke` v4: 44 questions across the ten companies, stratified by hop count (definitions, single relationship, multi-relationship comparisons) plus out-of-scope questions the system must refuse. Each answerable question has gold chunk IDs for retrieval scoring and required facts for answer scoring.

Generation headline: mean of three temperature-0 runs —

- [`multi_company_smoke_temp0_p6.json`](benchmarks/results/multi_company_smoke_temp0_p6.json)
- [`multi_company_smoke_temp0_p6_run2.json`](benchmarks/results/multi_company_smoke_temp0_p6_run2.json)
- [`multi_company_smoke_temp0_p6_run3.json`](benchmarks/results/multi_company_smoke_temp0_p6_run3.json)

Summary: [`three_run_means.md`](benchmarks/results/three_run_means.md). Bootstrap on per-item three-run means: [`ablation_bootstrap_three_run.md`](benchmarks/results/ablation_bootstrap_three_run.md). An older pre-fix package (hybrid **0.86** / vector **0.89**) lives under [`benchmarks/results/archive/`](benchmarks/results/archive/).

**Judge calibration (rubric v1):** held-out linear weighted κ **0.84** (raw agreement 19/20). Two first-pass scores of 1.0 were corrected after seeing the judge (Meta AI competition → 0, Meta AI glasses → 0.5), so treat κ as a calibration check, not a fully blind panel. Self-agreement on a later re-label is κ **0.42** (13/15); both passes are mostly 1.0, so two one-step flips move κ more than the raw rate suggests. [`benchmarks/calibration/RESULTS.md`](benchmarks/calibration/RESULTS.md).

**CI gate:** fails if the committed hybrid recall@10 drops more than **0.02** from **0.911**. It reads the saved results file and does not call a model, so it costs nothing to run. A manual `workflow_dispatch` with `break=true` zeroes one saved hit to show the gate failing. Retrieval tables: [`benchmarks/results/retrieval_v4.md`](benchmarks/results/retrieval_v4.md).

### 60-second pass

1. Generation: three-run hybrid **0.93** vs vector **0.90**; hop-2 **1.00** vs **0.88** with a CI above zero; overall CI includes zero.
2. One graph question: `python answer.py "What product lines does Apple produce?" --ticker AAPL`.
3. One refusal: a question the 10-K corpus cannot answer (Tesla battery supply, Bitcoin on Apple's balance sheet).
4. Soft misses still open on hop-1 product / competition asks. See **What didn't work**.

## Design decisions

| Decision | Why | What it costs |
|----------|-----|---------------|
| **Closed ontology** (6 entity / 8 relationship types) instead of open extraction | Clean, queryable graph; entity resolution stays tractable; edges are comparable across companies | Anything outside the 6/8 types is invisible to the graph and falls back to vector search |
| **Allowlisted Cypher templates** instead of model-written Cypher | No injection or runaway queries; every graph query is reviewable and testable | Coverage is limited to the question shapes the templates support; new shapes need a new template |
| **Citation allowlist**: every cited `chunk_id` must come from this retrieval, else reject / regenerate | Stops invented sources; makes every claim traceable to a filing passage | Can't catch a real chunk cited for the wrong claim; regeneration adds latency and cost |
| **Ticker-scoped writes and retrieval** (`home_ticker` + `tickers[]` on shared companies) | Prevents cross-filing leaks — e.g. Meta's 10-K inventing Apple product edges | Shared entities need extra bookkeeping; global relationships are harder to express |
| **Cheap Haiku router** (graph / vector / both) | Low cost per question; most questions don't need the graph | Sometimes routes wrong — mitigated by retrieving both lists even when the router says graph |
| **Hybrid merge**: alternate a vector chunk, then a graph chunk, skipping chunks already used; graph edges ordered by question-word hits, extraction confidence only as a tie-break | Keeps the strong vector ranking while making room for graph evidence | Graph-only recall varies between runs because the planner does not return the same edges every time |
| **Separate retrieval and generation scores** | A good answer built on the wrong passage is still a retrieval miss; tells you which half failed | Needs gold chunk IDs per question, which are labeled by hand |
| **Judge grades required facts**, not similarity to a gold answer | Rewards correct content in any wording | Requires writing required facts per question; scores are only as good as those fact lists |

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

Earlier systems bugs worth saying anyway: keyword overlap scored wrong answers as 1.0 (which is why the judge grades required facts now), a 1200-character window hid AppleCare and Azure, and an Apple product answer once cited Meta's 10-K (which led to the ticker-scoped write gate).

## Quick start

```bash
docker compose up -d
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY + OPENAI_API_KEY (+ USER_AGENT_EMAIL for SEC EDGAR)
```

**Build a small corpus from scratch** (paid — always check the estimate first):

```bash
python grow_corpus.py AAPL --budget                     # estimate only, no spend
python grow_corpus.py AAPL --confirm --max-chunks 5     # cheap smoke: ingest → extract → Neo4j → pgvector
python grow_corpus.py AAPL --confirm                    # full Items 1 / 1A / 7
```

`--max-total-usd 20` aborts before any spend if the aggregate estimate is higher. Add more tickers in one run (`python grow_corpus.py AAPL MSFT NVDA --budget`).

**Ask:**

```bash
python answer.py "What product lines does Apple produce?" --ticker AAPL
python answer.py "What is AppleCare?" --ticker AAPL
python answer.py "What product lines does Apple produce?" --ticker AAPL --vector-only   # baseline

python -m uvicorn api:app --host 127.0.0.1 --port 8000
# POST http://127.0.0.1:8000/ask
# {"question":"What product lines does Apple produce?","ticker":"AAPL"}
```

**Benchmark** (paid answer run; the judge is the cheaper Haiku). The full suite needs all ten companies in the corpus:

```bash
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json --limit 2
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json --confirm
# Re-score saved answers with LLM judge (no answer re-run):
python benchmark_runner.py --suite benchmarks/multi_company_smoke.json \
  --rejudge benchmarks/results/multi_company_smoke_temp0_p6_run3.json --confirm
```

Neo4j Browser: http://localhost:7474 (`neo4j` / `password` by default) · API docs: http://127.0.0.1:8000/docs

## Repo map

| Area | Files |
|------|--------|
| Ingest / extract / resolve / write | `ingest.py`, `extractor.py`, `resolver.py`, `graph_writer.py` |
| Vectors | `embedder.py`, `vector_db.py` |
| Retrieve / answer / API | `router.py`, `graph_retriever.py`, `vector_retriever.py`, `answer.py`, `api.py` |
| Batch growth / budget | `grow_corpus.py`, `budget.py` |
| Eval | `benchmarks/`, `benchmark_runner.py`, `benchmark_judge.py`, `retrieval_benchmark.py`, `retrieval_metrics.py`, `bootstrap_ci.py`, `calibration_metrics.py`, `recall_gate.py` |
| Tests | `test_*.py` |
| Failure log | [`docs/PROBLEMS_AND_FIXES.md`](docs/PROBLEMS_AND_FIXES.md) — bugs hit and how they were fixed |
| License | [`LICENSE`](LICENSE) (MIT) |
