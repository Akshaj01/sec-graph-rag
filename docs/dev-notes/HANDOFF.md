# SEC GraphRAG — Handoff

**Last updated:** 2026-11-05  
**Repo:** https://github.com/Akshaj01/sec-graph-rag (`main` at `e32f498`)  
**Primary living plan:** [`docs/MEASURE_IT_PLAN.md`](../MEASURE_IT_PLAN.md) (closed). Next stub: [`docs/GATEWAY_PLAN.md`](../GATEWAY_PLAN.md).

Use this file + `docs/dev-notes/AGENTS.md` + **`docs/MEASURE_IT_PLAN.md`** to continue in a **new Cursor chat** on the PC. Chat history will not transfer. `git pull` first. The published numbers are already in the repo. Do not start another paid answer run to recreate them.

---

## How context works

A new agent only knows:

1. This GitHub repo (code + docs)
2. **`docs/dev-notes/AGENTS.md`** — Learning Protocol, ontology, build phases
3. **`docs/dev-notes/HANDOFF.md`** (this file) — current status + next step
4. **`docs/MEASURE_IT_PLAN.md`** — Measure-it work packages (WP0–WP7) and design decisions
5. Whatever you paste into the first message

Do **not** invent architecture. Measure it is closed. Gateway work starts from `docs/GATEWAY_PLAN.md` with a design note, not with code.

---

## Project goal

Hybrid **Knowledge Graph + Vector RAG** over SEC **10-K** filings.

**BASWE Project 1 (build) — DONE:** FastAPI `/ask` with validated citations; README hybrid vs vector-only table.

**Personal plan “Measure it” (Plan P1 ≈ roadmap P4) — DONE:** retrieval metrics, κ, CI gate, and a three-run generation table. Gateway is the next phase and is still a stub.

---

## Resume on the PC (2026-11-05)

`git pull` on `main`. HEAD is `e32f498`. The PC needs its own `.env` (never committed) and Docker (`neo4j_graphrag`, `pgvector_graphrag`). The corpus under `data/` is gitignored, so a fresh PC does not have the graph until ingest is run there. The score files below are in git. Reading them does not need Docker or an API key.

**Generation headline.** Three runs, planner + router + answer + judge at temperature 0. Files: `benchmarks/results/multi_company_smoke_temp0_run1.json`, `run2`, `run3`. Suite `benchmarks/multi_company_smoke.json` (v4, n=44).

| | Hybrid | Vector-only |
|--|--:|--:|
| Runs | 0.862, 0.862, 0.856 | 0.889, 0.878, 0.889 |
| Mean | **0.86** | **0.89** |

Gap of the means **−0.026**. Paired gaps **−0.033**, **−0.016**, **−0.027**. Hop table is in the README. Five items still moved. `hop1_aapl_products` hybrid text was identical and the judge scored it 1.0, 1.0, 0.5.

**Retrieval headline** (retrieve-only, not re-run after the temperature pin): hybrid recall@5 **0.83**, recall@10 **0.92**, MRR **0.64**. Vector **0.82 / 0.93 / 0.67**. Graph-only on that run **0.43 / 0.51 / 0.38**. Recall gate baseline is hybrid recall@10 **0.9167**.

**Code that produced this.** Unforced retrieve fetches graph and vector. The scored list and the evidence pack alternate vector, graph, vector, graph, and skip a chunk already used. Graph edges are ranked by question-word hits. Extraction confidence only breaks a tie. `force_route=VECTOR` stays vector-only. Reciprocal rank fusion was simulated and not shipped (recall@5 would have fallen to about 0.75).

**Do not**

- Quote hybrid **0.92** vs vector **0.89**, or the bootstrap gap **0.038**. That pair is older. `benchmarks/results/ablation_bootstrap.md` is that older pair.
- Run `bootstrap_ci.py` on the new files and call the output the current gap. `FULL_RUN_HYBRID_SCORE` forces `hop2_jpm_credit_vs_market` back to **0.375**. The three-run files score that item **0.625** on every run.
- Run `benchmark_runner.py` without `--suite benchmarks/multi_company_smoke.json`. The default suite is `benchmarks/aapl_smoke.json`.
- Start another 44-question answer run unless Akshaj asks. The three runs already cost about $2.59.
- Write gateway code before a design note in `docs/GATEWAY_PLAN.md`.

**Still open, not a reason to rerun.** Hybrid does not beat vector on generation. Vector still leads recall@10 and MRR. `hop1_meta_ai_competition` hybrid is 0.00 on all three runs. `oos_nflx_ai_compute_for_others` denies the premise in prose and leaves `refused` false, so the score is 0. The judge can still move a score when the paragraph did not. Profile README and the GitHub repo description already say 0.86 vs 0.89.

**Next, only if asked.** Gateway design note (circuit breaker, semantic cache, chaos demo). No code until that note exists.

---

## Where we are now (2026-11-05)

| Item | Status |
|------|--------|
| Corpus | **10 tickers** full Item 1/1A/7 (`AAPL AMZN GOOGL JNJ JPM META MSFT NFLX NVDA XOM`) |
| Suite | `multi_company_smoke` **v4**, **n=44**, hop 0/1/2 + OOS; **gold_chunk_ids on 32/32 answerable** (12 OOS empty) |
| Headline (generation) | Three temperature-0 runs, 2026-11-05: hybrid **0.86** (0.856–0.862) / vector **0.89** (0.878–0.889). Gap of the means **−0.026**. Five items still moved. |
| Judge | LLM-as-judge vs `required_facts`; old human agree **24/24** (history, not κ) |
| **WP0** (design) | **DONE** — see MEASURE_IT_PLAN §8 |
| **WP1** (gold chunks) | **DONE** — spot-check accepted |
| **WP2** (retrieval) | **DONE** — hybrid recall@5 **0.83** / MRR **0.64**; vector **0.82** / **0.67**; graph **0.43** / **0.38**. Edges ranked by question-word hits, confidence breaks ties (`benchmarks/results/retrieval_v4.md`) |
| **WP3** (κ) | **DONE** — corrected hold-out linear κ **0.84** (19/20). First pass was all 1.0s (κ 0.00). Self-agreement κ **0.42**. Rubric v1 unchanged. |
| **WP4** (bootstrap) | **DONE** on the older pair only — gap **0.038** [−0.047, 0.126]. Not the current headline. Current gap is the three-run mean, **−0.026**. |
| **WP5** (CI gate) | **DONE** — green [41779177304](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41779177304), red break [41782167624](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41782167624). Baseline hybrid recall@10 **0.9167**. |
| **WP6** (README) | **DONE** — three-run generation table, retrieval table, 60-second pass. Demo recording still optional. |
| **WP7** (close) | **DONE** — retrospective in `docs/MEASURE_IT_PLAN.md` §10. Gateway stub only. |
| **Next** | Plan P2 design note in `docs/GATEWAY_PLAN.md`. No gateway code until that note exists. |

**WP0 locked decisions:** “good” = retrieve supporting evidence (quality > volume) + accurate cited answers + refuse OOS; retrieval headline = recall@5 + MRR (@10 supporting); generation = hop judge hybrid vs vector; κ on ~15–20 held-out v3; ablation = hybrid vs vector + bootstrap CI.

---

## Status checklist (build)

| Phase | Status | Notes |
|-------|--------|-------|
| 1 Graph extraction | **DONE** | Multi-company Neo4j |
| 2 pgvector index | **DONE** | Shared `chunk_id`, HNSW |
| 3 Route + retrieve | **DONE** | Router + templates + `retrieve.py` |
| 4 Grounded answer + citations | **DONE** | `answer.py` + topic gate / repair |
| 5 Benchmark vs vector-only | **DONE** (build) | Suite + runner + README + `/ask` |
| Measure it (evals) | **DONE** | Ship gate checked 2026-11-03. Stub: `docs/GATEWAY_PLAN.md` |

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
            → answer.py (N+O+P): labeled evidence → draft → validate cites → CLI smoke OK
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

## What is NOT done (Measure-it / resume honesty)

- Measure it ship gate is checked. Optional demo recording was not done.
- Gateway is a stub only (`docs/GATEWAY_PLAN.md`). Agent / red-team (plan P3) stays closed.
- Not a 50–100 human-panel eval — n=44 automated judge. Corrected hold-out κ is **0.84** (first pass was 0.00). The hybrid lead’s interval crosses zero.

---

## Growing the corpus (multi-company batch tool — 2026-09-02)

`grow_corpus.py` batches Steps C–J (ingest → extract → resolve → Neo4j write →
pgvector embed) across multiple tickers in one run instead of the one-ticker-
at-a-time commands below. Every underlying Step is unchanged; this only adds
an outer loop, an aggregate budget gate before any spend, and a per-ticker
try/except so one bad ticker (no 10-K, nonstandard filing structure) doesn't
kill the batch.

```powershell
# Dry run: aggregate cost estimate only, no spend
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM XOM PFE --budget

# Real run: full filings (all Item 1/1A/7 chunks), Neo4j + pgvector
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM XOM PFE --confirm

# Cheap smoke test across several tickers first
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM --confirm --max-chunks 5

# Extra aggregate safety cap on top of the per-ticker MAX_EXTRACTION_BUDGET_USD
.\.venv\Scripts\python.exe grow_corpus.py MSFT JPM XOM --confirm --max-total-usd 20
```

A JSON report (per-ticker status, entities/relationships merged, chunks
embedded) is written to `./data/corpus_growth_<timestamp>.json`.

**Suggested starter set** (sector-diverse, away from AAPL's tech/consumer
profile, for a more portfolio-credible benchmark once expanded):
`MSFT, GOOGL, JPM, XOM, JNJ, WMT, PFE, KO, DIS, BA` — pick your own; nothing
is hardcoded as a default (a batch tool defaulting to real spend across N
companies with no args felt like the wrong default).

### Two correctness fixes that shipped alongside this tool

Both were latent bugs that only matter once a second company exists — the
AAPL smoke corpus never exercised them:

1. **Entity id collisions across companies** (`resolver.py`). Canonical
   Neo4j ids were built from normalized name text alone (e.g.
   `RiskFactor("Cybersecurity")` → `CYBERSECURITY`). A second company's
   similarly-named risk factor / product line / executive would `MERGE`
   onto the *same* node, blending unrelated descriptions and mention
   counts — worst for `Executive`, where two unrelated people sharing a
   common name would become one node. Fixed by namespacing
   `RiskFactor`/`ProductLine`/`Executive` ids with the ticker
   (`canonical_entity_id()` in `resolver.py`, mirrored in `embedder.py`'s
   `entity_ids_for_chunk` so pgvector's `entity_ids` column stays in sync).
   `Company`/`Subsidiary`/`Supplier` stay globally deduped on purpose — a
   shared supplier or a company named as another's competitor should
   resolve to one node.
   **Migration note:** this changes the id scheme for those three types.
   If AAPL is already written to your local Neo4j, re-running
   `grow_corpus.py`/`graph_writer.py` for AAPL will create new
   ticker-prefixed nodes alongside the old unprefixed ones rather than
   updating them in place. Reset the Neo4j volume (`docker compose down -v`
   then `docker compose up -d`) before growing the corpus for a clean graph.
2. **Vector retrieval silently defaulted to AAPL** (`vector_retriever.py`).
   `retrieve_vector`'s `default_ticker` was `"AAPL"`, so any question that
   didn't literally contain "apple"/"aapl" or an ALL-CAPS ticker token would
   still search only Apple's chunks — even after other companies were
   embedded. Default is now `None` (full-index search) so growing the
   corpus actually makes other companies reachable through `answer.py`/
   `api.py`'s default behavior. `guess_ticker()` still only recognizes
   Apple by name; pass `ticker` explicitly (the API's `ticker` field, or
   `retrieve_vector(..., ticker=...)`) for a scoped multi-company answer.

---

## Phase 4 — DONE (live-verified PC, 2026-08-24)

| Step | File(s) | Status |
|------|---------|--------|
| N Format + draft answer | `answer.py`, `config.py` (`ANSWER_*`) | **DONE** |
| O Citation validator + regenerate | `validate_citations`, `generate_validated_answer` | **DONE** |
| P CLI smoke | `python answer.py "..."` | **DONE** |

**Verified smoke:**
- `"What product lines does Apple produce?"` → route `graph`, 18 GRAPH facts, `citations_valid=true`, `regenerated=false`, cites `Item1:0` / `Item1:1`
- `"What is AppleCare?"` → route `vector`, 5 VECTOR passages, `citations_valid=true`, `regenerated=false`, cites `Item1:0`

FastAPI `/ask` live at `api.py` (see README).

## Phase 5 — DONE (2026-08-25)

| Step | File(s) | Status |
|------|---------|--------|
| Q Labeled suite + schemas | `benchmark_schema.py`, `benchmarks/aapl_smoke.json`, `benchmark.py` | **DONE** |
| R Hybrid vs vector-only runner | `benchmark_runner.py` | **DONE** |
| S README accuracy table | `README.md` | **DONE** |
| T FastAPI `/ask` | `api.py` | **DONE** |

**API smoke:** `POST /ask` {"question":"What is AppleCare?","ticker":"AAPL"} → `citations_valid=true`, route `vector`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
# POST http://127.0.0.1:8000/ask  body: {"question":"What is AppleCare?"}
# Docs: http://127.0.0.1:8000/docs
```

---

## Copy-paste into a NEW Cursor chat

```text
You are continuing SEC GraphRAG (Akshaj) on the PC. git pull first. Read completely:
1) docs/dev-notes/HANDOFF.md — section "Resume on the PC"
2) README.md — the published tables
3) docs/PROBLEMS_AND_FIXES.md — items 13–15 and section A
4) docs/GATEWAY_PLAN.md — next phase stub (no code yet)
5) docs/dev-notes/AGENTS.md

main is e32f498. Build phases 1–5 are DONE. Measure it is DONE.
Generation: three temperature-0 runs, hybrid 0.86 (0.856–0.862) vs vector 0.89 (0.878–0.889). Gap of the means −0.026. Do not quote 0.92 vs 0.89.
Retrieval: hybrid recall@5 0.83 vs vector 0.82. Vector leads recall@10 and MRR.
Do not rerun the paid suite unless asked. Do not start gateway code before a design note.
Do NOT invent architecture. Do NOT emit model-written Cypher. Do NOT commit .env or My Resume/.
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

# Phase 4 Steps N+O (draft + citation validation)
.\.venv\Scripts\python.exe answer.py "What product lines does Apple produce?"
.\.venv\Scripts\python.exe answer.py "What is AppleCare?"

# Phase 5 Step Q (list labeled suite — no paid eval yet)
.\.venv\Scripts\python.exe benchmark.py

# Phase 5 Step R — full suite is NOT the default. Default is aapl_smoke.json.
.\.venv\Scripts\python.exe benchmark_runner.py --suite benchmarks/multi_company_smoke.json --modes hybrid,vector_only --confirm

# Phase 5 Step T (API)
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
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
| Answer (Phase 4) | `answer.py` (N+O: draft + citation validation) |
| Benchmark (Phase 5) | `benchmark_schema.py`, `benchmarks/`, `benchmark_runner.py` |
| API | `api.py` |
| Docs | `README.md`, `docs/MEASURE_IT_PLAN.md`, `docs/PROBLEMS_AND_FIXES.md`, `docs/dev-notes/HANDOFF.md`, `docs/dev-notes/AGENTS.md` |

**Do not commit:** `.env`, `./data/*.db`, `My Resume/`
