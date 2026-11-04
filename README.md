# SEC GraphRAG

Hybrid **knowledge-graph + vector RAG** over SEC **10-K** filings. Closed ontology in Neo4j, the same chunks in pgvector, router picks graph and/or vectors, answers cite only chunks from that retrieval.

10 tickers, 44 hop-stratified questions. Hybrid generation mean **0.92** vs vector-only **0.89**. That lead is **not stable**: the 95% interval on the gap includes values below zero. Vector leads retrieval (recall@5 **0.82** vs hybrid **0.67**).

## Results

44 questions. The score is an LLM judge against required facts. Out of scope means a correct refuse.

| Hop / bucket | Hybrid | Vector-only | n |
|--------------|-------:|------------:|--:|
| Hop 0 (definitions) | **0.94** | 0.92 | 8 |
| Hop 1 (single edge) | **0.88** | 0.79 | 16 |
| Hop 2 (compare / multi-rel) | 0.88 | 0.88 | 8 |
| OOS (must refuse) | **1.00** | **1.00** | 12 |
| **Overall mean** | **0.92** | 0.89 | 44 |

**Recommendation:** Hybrid scores higher on average (0.038 overall, 0.005 on hop 2), and neither 95% interval sits entirely above zero, so the lead is not stable on this suite.

Retrieval is scored separately, on 32 answerable items. Out-of-scope items are skipped.

| | Recall@5 | Recall@10 | MRR |
|--|--------:|----------:|----:|
| Graph | 0.42 | 0.51 | 0.37 |
| Vector | **0.82** | **0.93** | **0.67** |
| Hybrid | 0.67 | 0.80 | 0.51 |

Hybrid lists graph chunks first. Those are often a different passage than the gold prose, so they push the gold id down. The answer can still be right because the graph statement carries the fact.

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

Suite `multi_company_smoke` v4. Generation numbers are the judged run on the same questions.

**Judge calibration (rubric v1):** held-out linear weighted κ **0.84** (raw agreement 19/20). Two first-pass scores of 1.0 were wrong and were corrected: Meta AI competition is a 0, Meta AI glasses is a 0.5. Self-agreement on a later re-label is κ **0.42** (13/15). The older 24/24 sheet is history. [`benchmarks/calibration/RESULTS.md`](benchmarks/calibration/RESULTS.md).

Paired bootstrap, 10,000 draws, seed 0. Gap = hybrid minus vector-only.

| Slice | n | Gap | 95% CI |
|-------|--:|----:|--------|
| Overall | 44 | 0.038 | −0.047 to 0.126 |
| Hop 2 | 8 | 0.005 | −0.234 to 0.250 |

CI fails if a committed hybrid recall@10 drops more than **0.02** from **0.802**. It reads the saved file and does not call a model.

Full tables: [`benchmarks/results/multi_company_smoke_judged.json`](benchmarks/results/multi_company_smoke_judged.json), [`benchmarks/results/retrieval_v4.md`](benchmarks/results/retrieval_v4.md), [`benchmarks/results/ablation_bootstrap.md`](benchmarks/results/ablation_bootstrap.md). The means use the full-run score for `hop2_jpm_credit_vs_market` (**0.375**). A later one-item rerun scored **1.0**. That rerun is not in the table.

### 60-second pass

1. Read the two tables above. Say the generation gap out loud, then say the interval crosses zero.
2. Ask one graph question: `python answer.py "What product lines does Apple produce?" --ticker AAPL`.
3. Ask one refusal: a question the 10-K corpus cannot answer (Tesla battery supply, Bitcoin on Apple's balance sheet).
4. Name one miss from **What didn't work** (Meta apps refused).

## Design decisions

Locked during the eval phase. Retrieval and generation are separate scores. A high answer with the wrong gold chunk is still a retrieval miss. The judge grades required facts, not a paragraph match to the gold line. Reported κ is the hold-out, not the 24/24 debug sheet. The ablation is hybrid versus vector-only, and the interval is part of the claim.

The system constraints that came first: six entity types and eight relationship types, Cypher only from allowlisted templates, and a citation must be in this retrieval's chunk allowlist.

## What didn't work

These five are still the weak spots on the published hybrid run. Detail is in [`docs/PROBLEMS_AND_FIXES.md`](docs/PROBLEMS_AND_FIXES.md).

| Item | Score | What happened |
|------|------:|----------------|
| `hop1_meta_apps` | 0.00 | Graph route refused "which apps does Meta produce?" |
| `hop1_meta_ai_competition` | 0.13 | Answered with Apple/Google ad limits, not platform or AI competitors |
| `hop0_meta_ai_glasses` | 0.50 | Said AI glasses and Quest, missed Ray-Ban Meta / Oakley Meta |
| `hop2_nvda_auto_competitors_risks` | 0.67 | Named auto SoCs and Ambarella, missed DRIVE / autonomous |
| `hop2_jpm_credit_vs_market` | 0.38, then 1.0 | Full run scored 0.375. A later rerun of this item alone scored 1.0. The table uses 0.375. |

Earlier failures that are fixed, and worth saying anyway: keyword overlap scored wrong answers as 1.0, a 1200-character window hid AppleCare and Azure, and an Apple product answer cited Meta's 10-K.

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

