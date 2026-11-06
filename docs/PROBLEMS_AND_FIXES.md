# Problems & Fixes

Living log of failures hit while building SEC GraphRAG, why they happened, and what changed. Each closed item is symptom, root cause, and fix.

**Repo:** https://github.com/Akshaj01/sec-graph-rag  
**Last updated:** 2026-11-05 (three temperature-0 answer runs)

---

## Closed problems (fixed)

### 1. Extraction truncation (dense Item 1)

| | |
|--|--|
| **Symptom** | Structured extract cut off mid-JSON / missing entities on long 10-K sections. |
| **Root cause** | Default `EXTRACTION_MAX_TOKENS=4096` too small for Item 1. |
| **Fix** | Raise to `16384` via `.env` / settings (`EXTRACTION_MAX_TOKENS`). |
| **Where** | `config.py`, `.env.example` |

---

### 2. Global Company ticker clobber

| | |
|--|--|
| **Symptom** | After growing a multi-company corpus, Apple’s Company node could show another issuer’s ticker (last writer wins). |
| **Root cause** | `Company` is a **global** node (shared across filings). Early writes stored a single `ticker` property and overwrote it on every MERGE. |
| **Fix** | `home_ticker` set only when the filing **issuer** writes that Company; accumulate `tickers[]` for all mentioning filings. |
| **Where** | `resolver.py` (`is_issuer`, `mark_issuer_company`), `graph_writer.py` (`_merge_global_entity`), `test_ticker_clobber.py` |

---

### 3. Risk / Product / Executive identity collisions

| | |
|--|--|
| **Symptom** | Unrelated companies’ “Cybersecurity” risks or similarly named products could merge onto one node. |
| **Root cause** | Canonical ids were name-only for types that are **not** shared across issuers. |
| **Fix** | Ticker-prefix RiskFactor / ProductLine / Executive ids (`AAPL_IPHONE` vs `META_FACEBOOK`). Keep Company / Subsidiary / Supplier global. |
| **Where** | `resolver.py` (`TICKER_SCOPED_ENTITY_TYPES`, `canonical_entity_id`) |

---

### 4. Hop-2 hybrid failures (refuse / thin answers / weak packs)

| | |
|--|--|
| **Symptom** | Multi-relation questions (products **and** risks, segment compares) failed or refused even when graph had the edges; hop-2 scores lagged. |
| **Root causes** | (a) Planner often returned **one** template for a two-aspect ask. (b) Evidence packs blew token budget / order was wrong. (c) Answer model **false-refused** despite usable graph facts. |
| **Fix** | Multi-template plans + deterministic `augment_template_ids`; evidence caps / packing; unjustified-refuse repair and `draft_from_graph_evidence` fallback; raise answer token budget where needed. |
| **Where** | `graph_retriever.py`, `answer.py`, `config.py` (`ANSWER_MAX_TOKENS`, evidence caps) |

**After fixes (keyword era, then judge era):** hop-2 hybrid beat vector-only; under LLM judge ≈ **0.90 vs 0.69**.

---

### 5. Keyword recall lied (eval metric failure)

| | |
|--|--|
| **Symptom** | Answers scored **1.0** while being wrong or incomplete. |
| **Examples** | **J&J MedTech:** said “yes MedTech” then cited pharma drugs (DARZALEX, IMBRUVICA) — keyword hit “MedTech”. **JPM credit vs market:** hedged that market risk wasn’t clearly named — still scored 1.0 on “Credit”/“Market”. |
| **Root cause** | Score = substring hit rate on `gold_keywords`. Easy to game; ignores faithfulness and contradiction. |
| **Fix** | Suite v2: `required_facts` + `gold_answer`; Haiku + Instructor **LLM-as-judge**; keyword kept secondary. Rejudged saved answers without full re-answer (`--rejudge`). |
| **Where** | `benchmarks/multi_company_smoke.json`, `benchmark_judge.py`, `benchmark_runner.py`, `benchmarks/results/multi_company_smoke_judged.json` |
| **Headline (judge)** | Overall hybrid **0.79** vs vector **0.76**; hop-2 **0.90 vs 0.69** (n=24). |

**Still not human accuracy** — automated judge, small n, no hand-label agreement % yet.

---

### 6. Meta-on-Apple cross-issuer citation leak

| | |
|--|--|
| **Symptom** | `hop1_aapl_products` (graph route) cited Apple **and** Meta accession `0001628280-…`. `citations_valid=true` because Meta chunks were in the allowlist. |
| **Root causes** | (1) **Write pollution:** Meta extract created `APPLE-[:PRODUCES_PRODUCT]->META_IOS/SAFARI` with Meta `source_chunk_ids`; `_merge_relationship` replaced provenance with no issuer gate. (2) **Retrieve blind spot:** `ticker` passed only to vector; `retrieve_graph` returned all outgoing edges from global `APPLE`. |
| **Not the bug** | Keeping `COMPETES_WITH → META` as a neighbor — that’s intentional. Wrong was citing **Meta’s 10-K text** for Apple product facts. |
| **Fix** | Issuer-owned write skip; union `source_chunk_ids` + `write_tickers`; thread `ticker` into graph retrieve; filter fact chunks via `chunk_ticker.py`; `python graph_writer.py --cleanup-cross-issuer` (deleted 5 bad edges). |
| **Where** | `graph_writer.py`, `retrieve.py`, `graph_retriever.py`, `chunk_ticker.py`, `test_cross_issuer_leak.py` |

---

### 7. Cost / confirm gates (process, not a code bug)

| | |
|--|--|
| **Symptom** | Easy to accidentally burn paid extract/answer calls. |
| **Fix** | `budget.py`, `--confirm` on grow/benchmark, rough cost estimates in runners. |
| **Where** | `budget.py`, `grow_corpus.py`, `benchmark_runner.py` |

---

### 8. Hop-0 false refuses (AppleCare / Azure) — wrong evidence *window*

| | |
|--|--|
| **Symptom** | “What is AppleCare?” / “What is Azure?” refused (`refused=true`, score 0) even though those terms exist in the same 10-K chunks other answers cite. |
| **Root cause** | Right chunks were retrieved, but `ANSWER_MAX_VECTOR_CHARS=1200` **prefix**-truncated passages. AppleCare sat ~char 1744; Azure often later. The model honestly refused the head-only pack. Unjustified-refuse repair is GRAPH-only, so it never helped. A first window fix also had to prefer **question** needles over passage `entity_ids` (iPhone/Mac appear earlier and stole the window). |
| **Fix** | `truncate_passage_for_query` (query-centered window); post-HNSW lexical/entity boost + over-fetch in `vector_retriever.py`. |
| **Where** | `answer.py`, `vector_retriever.py`, `test_answer_evidence.py`; smoke report `benchmarks/results/multi_company_smoke_hop0_fix.json` |
| **Verify** | Rebench both items × hybrid/vector_only → all **score=1.0**, `refuse=False`. |

---

### 9. Hop-1 hybrid losses (Meta competition + J&J MedTech)

| | |
|--|--|
| **Symptom** | Hop-1 hybrid **0.81** vs vector **0.88**. Two failures: (a) “Does Apple compete with Meta?” → model said **No**; (b) “Does J&J produce MedTech?” → hybrid **0.5** (yes + drug cites) vs vector **1.0**. |
| **Root causes** | (a) Issuer chunk filter treated `COMPETES_WITH` like `PRODUCES_PRODUCT` and dropped Meta-stamped `APPLE→META` for `ticker=AAPL`; remaining competitors crowded the pack with product edges. (b) Graph has no `MedTech` ProductLine — only drug/device names — so graph-only route invented “yes MedTech” from DARZALEX/etc. |
| **Fix** | Strict chunk-ticker filter only for `ISSUER_OWNED_REL_TYPES` (shared with write gate); keep foreign provenance on `COMPETES_WITH` / `SUPPLIED_BY` / `DEPENDS_ON`. Competition asks drop `PRODUCES_PRODUCT` from the pack + needle-rank competitors. Produce yes/no asks force route `both`; omit unmatched `PRODUCES_PRODUCT` when a specific product/segment needle doesn’t hit (generic “apps/products” lists keep the full set). |
| **Where** | `graph_retriever.py`, `graph_writer.py`, `retrieve.py`, `answer.py`, `test_cross_issuer_leak.py`, `test_answer_evidence.py` |
| **Verify** | Hop-1 rebench n=8 → hybrid **1.00**, vector **0.81** (`multi_company_smoke_hop1_fix.json`); overall hybrid **0.95** vs vector **0.90**. |

---

### 10. Full-sync rebench (book closed on current code)

| | |
|--|--|
| **Symptom** | Published table mixed a fresh hop-1 slice with older hop-0/2/OOS answers. |
| **Fix** | Full 24×2 rebench (`multi_company_smoke_full_sync.json` → `multi_company_smoke_judged.json`). |
| **Result** | Hybrid **0.98** overall (hop-0 **0.92**, hop-1/2/OOS **1.00**); vector **0.92** (hop-0 **1.00**, hop-1 **0.81**, hop-2 **0.94**, OOS **1.00**). Material hybrid move: `hop2_jpm_credit_vs_market` **0.375 → 1.0** (route `both`). |
| **Calibration note** | Human **24/24** agree was on the *prior* hybrid answers; only that JPM hop-2 item changed score materially. |

---

### 11. Hybrid unjustified answers on OOS (GRAPH laundry list)

| | |
|--|--|
| **Symptom** | v3 OOS items (battery, blockchain, Meta glasses rival, Netflix “AI compute for others”, …) scored **0** on hybrid: model answered from unrelated `PRODUCES_PRODUCT` / `COMPETES_WITH` edges, or Instructor crashed on `refused=true` with empty `citation_chunk_ids`. Vector OOS was already **1.0**. |
| **Root cause** | Unjustified-**refuse** repair treated any GRAPH pack as on-topic and rewrote honest refuses into product dumps. Citation schema required ≥1 cite even when refusing. |
| **Fix** | `evidence_addresses_question` topic gate; skip refuse→answer repair unless on-topic; **unjustified-answer** repair / deterministic `normalize_refused_draft` when off-topic; allow empty cites when `refused=true`. |
| **Where** | `answer.py`, `test_answer_evidence.py` |
| **Verify** | `multi_company_smoke_v3_oos_resmoke.json` — 8 OOS × hybrid/vector → all **score=1.0**, `refuse=True`. |

---

### 12. Apple supply/China asks missed the evidence window

| | |
|--|--|
| **Symptom** | `hop1_aapl_china_supply_risk` / `hop1_aapl_supply_chain_risk` scored **0** (hybrid often refused; vector refused). Gold chunks Item1A:0/1 contain the prose. |
| **Root causes** | (1) Passage window centered on generic needle **“risks”** (Item 1A header) instead of **China** / **supply chain**. (2) Planner/`app`∈`Apple` falsely kept `COMPANY_PRODUCTS`, crowding the pack. (3) Topic gate treated `supply-chain` ≠ `supply chain`. |
| **Fix** | Prefer specific needles for windowing; risk-only asks drop `PRODUCES_PRODUCT` + strip product templates; hyphen/space-normalize topic match; `\bapp\b` not substring of Apple. |
| **Where** | `answer.py`, `graph_retriever.py`, tests |
| **Verify** | `multi_company_smoke_v3_aapl_supply_resmoke.json` — both items × both modes **1.0**. |

---

### 13. Hybrid retrieval buried the gold passage

| | |
|--|--|
| **Symptom** | Hybrid recall@5 was **0.67** while vector-only was **0.82**. On Exxon commodity risk the gold chunk was vector rank 1 and hybrid rank 12. Meta apps and NVIDIA products never retrieved a vector chunk at all. |
| **Root cause** | The hybrid list put every graph chunk first, then every vector chunk. A graph-only route never fetched the vector list, so there was nothing to place beside the graph chunks. |
| **Fix** | Alternate vector chunk, graph chunk, vector chunk, graph chunk. Skip a chunk already used. A normal ask retrieves both lists even when the router said graph. The vector-only benchmark still forces vector only. |
| **Where** | `retrieve.py`, `retrieval_metrics.py` (`interleave_ids`), `retrieval_benchmark.py`, `answer.py` (`_interleave_evidence`) |
| **Result** | Retrieve-only rerun, 32 answerable items. Hybrid recall@5 **0.84**, recall@10 **0.90**, MRR **0.63**. Vector stayed **0.82** / **0.93** / **0.67**. The four old top-5 misses now land inside the top 5. A later hybrid answer rerun, after this pack change, scored **0.85** overall. See §A. |

---

### 14. Extraction confidence was used as question relevance

| | |
|--|--|
| **Symptom** | A high-confidence edge about the wrong product could outrank a lower-confidence edge that named what the question asked. The evidence pack then sorted graph statements by confidence alone and dropped the name check the recall list still used. |
| **Root cause** | Confidence is stored at ingest. It means the extractor was sure the edge was real. It cannot mean the edge answers a question that did not exist yet. |
| **Fix** | Rank graph edges by how many question words hit the target and context. Confidence only breaks a tie. The evidence pack keeps that order. |
| **Not shipped** | Reciprocal rank fusion (`1/(60+rank)` from each list) was scored on the saved lists. Recall@5 fell to **0.75** from **0.84**, because a chunk that appears in both lists is often a general passage, not the gold one. Alternation stayed. |
| **Where** | `answer.py` (`_needle_hit_count`, `_rank_graph_facts_for_question`, `build_evidence_items`) |
| **Result** | Another retrieve-only rerun. Hybrid recall@5 **0.83**, recall@10 **0.92**, MRR **0.64**. Vector did not move. Graph-only recall@5 was **0.43** on this run; the planner does not return the same edges every time, so that column is not a clean before-and-after. |

---

### 15. Answer scores moved because three model calls were still sampling

| | |
|--|--|
| **Symptom** | The same suite scored differently on different nights. JPM hop-2 had already landed at 0.38, 1.0, and 0.63. |
| **Root cause** | The answer call was already at temperature 0. The graph planner, the router, and the judge were not, so they used the API default and sampled. |
| **Fix** | `temperature=0` on `plan_graph_query`, `classify_question`, and `judge_answer`. |
| **Where** | `graph_retriever.py`, `router.py`, `benchmark_judge.py` |
| **Result** | Three full runs. Hybrid means **0.862, 0.862, 0.856** (mean **0.86**). Vector-only means **0.889, 0.878, 0.889** (mean **0.89**). Five items still changed score. On Apple products the hybrid text was identical and the judge scored it 1.0, 1.0, and 0.5. Temperature 0 shrank the swing. It did not make the judge repeat itself. |

---

## Open / known weaknesses (not fully fixed)

### A. Three temperature-0 answer runs (2026-11-05)

Source: `benchmarks/results/multi_company_smoke_temp0_run1.json`, `run2`, and `run3`. Hybrid mean of means **0.860**. Vector-only mean of means **0.885**. Gap **−0.026**. The three paired gaps are **−0.033**, **−0.016**, and **−0.027**.

Items that moved inside these three runs:

| Item | Mode | Runs | What happened |
|------|------|------|----------------|
| `hop1_aapl_products` | hybrid | 1.0, 1.0, 0.5 | Same summary. The judge flagged a hallucination only on run 3, which caps the score at 0.5. |
| `hop1_meta_apps` | hybrid | 0.75, 0.75, 1.0 | The summary differs by a comma. WhatsApp was a miss, then a hit. |
| `hop1_msft_products` | vector | 0.50, 0.13, 0.50 | "devices" vs "various devices". Xbox was a hit, then a miss. |
| `hop1_meta_ai_competition` | vector | 0.50, 0.00, 0.50 | A sentence of regulatory wording changed. |
| `hop1_googl_waymo` | vector | 0.13, 0.50, 0.13 | One extra sentence on run 2. Waymo is still not named. |

The single rerun from earlier the same night, before this temperature pin, was hybrid **0.849** and vector-only **0.875** (`multi_company_smoke_hybrid_rerun.json`, `multi_company_smoke_vector_rerun.json`). On that hybrid file, Meta apps went from a refusal at **0.00** to **0.75**. Scores below 1.0 on that earlier hybrid file:

| Item | This run | Previous hybrid | What happened |
|------|------:|------:|----------------|
| `hop1_meta_ai_competition` | 0.00 | 0.125 | Apple/Google ad limits. No named platform or AI competitor. |
| `oos_nflx_ai_compute_for_others` | 0.00 | 1.0 | Denied the premise in the summary, but `refused` stayed false, so the score is 0. |
| `hop1_msft_products` | 0.125 | 1.0 | Named Microsoft 365, Dynamics, Windows, and Bing. Missed Azure and Xbox. |
| `hop2_nvda_auto_competitors_risks` | 0.418 | 0.667 | Auto SoCs. Missed DRIVE / autonomous. |
| `hop0_meta_ai_glasses` | 0.50 | 0.50 | Reality Labs and Quest. No Ray-Ban Meta / Oakley Meta. |
| `hop1_aapl_products` | 0.50 | 1.0 | Names iPhone, Mac, and iPad. The judge still scored 0.50. |
| `hop1_nflx_aws_relationship` | 0.50 | 1.0 | Says Netflix relies on AWS. Does not say Amazon's retail business competes with Netflix. |
| `hop1_nvda_automotive` | 0.50 | 1.0 | Partnerships and a computing platform. Does not name DRIVE. |
| `hop2_msft_cloud_and_geo_risk` | 0.50 | 1.0 | Says cloud computing and generic geopolitical risk. Does not name Azure. |
| `hop2_jpm_credit_vs_market` | 0.625 | 0.375 | Both risks named. The one-item rerun that scored 1.0 is not this run. |
| `hop1_meta_apps` | 0.75 | 0.00 | No longer a refusal. Family of Apps and Reality Labs. |
| `hop1_googl_waymo` | 0.938 | 1.0 | Waymo is covered. A small fact is still short. |

### B. Labeled set growth (v3 smoke, not yet headline)

| | |
|--|--|
| **Symptom** | The suite outgrew the first n=24 sync. |
| **Status** | Three temperature-0 answer runs on 2026-11-05. Hybrid **0.86** (0.856–0.862), vector-only **0.89** (0.878–0.889). Retrieval is separate: hybrid recall@5 **0.83** vs vector **0.82**; vector still leads recall@10 and MRR. |
| **Not doing now** | Multi-ticker retrieve (`tickers[]`) / LLM question fan-out — deferred; v3 items are already single-ticker. |

---

### C. Judge calibration (closed on n=24 hybrid)

| | |
|--|--|
| **Symptom** | Needed a published “human agrees with judge X% of the time” number. |
| **Status** | The n=24 sheet agreed **24/24**. That sheet was used to read the rubric. Reported κ is the hold-out after a correction: linear weighted κ **0.84** (raw 19/20), self-agreement κ **0.42** (13/15). The first hold-out pass was all 1.0s (κ **0.00**). Meta AI competition was rescored **0** and Meta AI glasses **0.5**. Rubric v1 was not edited. [`benchmarks/calibration/RESULTS.md`](../benchmarks/calibration/RESULTS.md). |
| **Caveat** | Same author as the gold facts. One hold-out split remains: NVIDIA auto competitors, human 1.0 vs judge 0.5. |

---

### D. Clone ≠ instant demo

| | |
|--|--|
| **Symptom** | Public repo needs keys + local Docker corpus (`data/` gitignored). |
| **Mitigations** | Screenshots, README architecture, optional Loom later. |

---

## Design choices that prevented whole classes of bugs

| Choice | Why it matters |
|--------|----------------|
| Closed ontology (6 entity / 8 rel types) | Stops “extract everything” graph sludge. |
| Allowlisted Cypher templates only | No model-written Cypher → no injection / hallucinated queries. |
| Shared `chunk_id` across Neo4j edges and pgvector | Citations and retrieval share one identity. |
| Citation allowlist | Necessary but **not sufficient** (see Meta leak) — must also scope what enters the pack. |
| Global vs ticker-scoped entities | Competitors share nodes; products/risks don’t. |

---

## Timeline of major fixes (rough)

1. Phase 1–5 curriculum: extract → graph → vectors → route → answer → keyword bench  
2. Multi-company grow → **ticker clobber** + **scoped entity ids**  
3. Hop-2 answer/retrieve fixes → hybrid wins hop-2 on keyword bench  
4. README, screenshots, public repo  
5. **LLM judge** replaces keyword as primary metric  
6. **Cross-issuer leak** found in judged/keyword results → write gate + retrieve filter + cleanup  
7. **Hop-0 false refuses** → query-centered vector windows + lexical re-rank (AppleCare/Azure smoke = 1.0)  
8. **Hop-1** → exempt cross-company rels from issuer chunk filter; produce yes/no → `both` + drop unmatched products (hybrid hop-1 **1.00**)  

---

## Short versions

**Card 1 — Metric lied**  
Keyword gave J&J / JPM 1.0 on bad answers → fact-checklist LLM judge. Three temperature-0 runs: hybrid **0.86** (0.856–0.862), vector-only **0.89** (0.878–0.889). Hold-out κ is **0.84** after two mistaken 1.0 labels were corrected.

**Card 2 — Eval → systems fix**  
Apple products cited Meta accession → global Company + Meta-written `PRODUCES_PRODUCT` → issuer write gate + chunk ticker filter + Neo4j cleanup. Same filter then erased Meta-stamped `COMPETES_WITH` → exempt cross-company rels.

**Card 3 — Multi-company identity**  
Last-write `ticker` clobber and unscoped product/risk ids → `home_ticker` / `tickers[]` + ticker-prefixed local types.

**Card 4 — Hop-2**  
One template + refuse heuristics ≠ multi-hop failure of retrieval → multi-template plans + evidence packing + refuse repair.

**Card 5 — Hop-0 windowing**  
AppleCare/Azure “not in evidence” while sitting mid-chunk past a 1200-char head truncate → query-centered windows (+ don’t let entity_ids steal the needle).

**Card 6 — Hop-1 MedTech / compete**  
No MedTech node + drug laundry list → force `both` + drop unmatched products; compete-with-Meta edge lived in Meta’s filing → don’t strip foreign provenance on `COMPETES_WITH`.

**Card 7 — Hybrid list order**  
Graph chunks sat in front of the gold passage, and a graph-only route never fetched vectors. Alternating vector then graph, and always retrieving both lists, moved hybrid recall@5 from **0.67** to **0.84**. Ranking edges by question-word hits, with confidence only as a tie-break, left the next rerun at **0.83** / recall@10 **0.92** / MRR **0.64**. Vector still leads recall@10 and MRR.

---

## Changelog for this doc

| Date | Note |
|------|------|
| 2026-10-03 | Initial log from build + packaging + judge + cross-issuer leak work. |
| 2026-10-03 | Closed hop-0 AppleCare/Azure false refuses (passage window + lexical re-rank). |
| 2026-10-03 | Full rebench after hop-0 fix; assembled judged table (vector hop-2/OOS filled after API credits ran out). |
| 2026-10-03 | Closed hop-1 Meta compete + J&J MedTech; hybrid hop-1 **1.00**, overall **0.95**. |
| 2026-10-04 | Human vs judge calibration on hybrid n=24 → **24/24 agree**. |
| 2026-10-04 | Full sync rebench → hybrid overall **0.98**, hop-2 **1.00**; book closed for current code. |
| 2026-10-27 | Suite v3 n=44 (author golden set); smoke new ids only — no full rebench; multi-ticker deferred. |
| 2026-10-27 | Fix hybrid unjustified answers on OOS (topic gate + force refuse); OOS resmoke **8/8**. |
| 2026-10-27 | Fix Apple supply/China window + product crowding; supply resmoke **1.0**. |
| 2026-10-27 | Full v3 n=44 rebench → hybrid **0.83** / vector **0.87**; hop-2 hybrid **0.96**. Softened over-strict topic gate after first full run over-refused. |
| 2026-10-28 | Fix false-refuse / NFLX-AWS dump / planner invent / NVDA+Meta route; rebench → hybrid **0.92** / vector **0.89**. |
| 2026-10-28 | JPM hop-2 resmoke (full-run flake 0.375→1.0); headline patched to hybrid **0.94** / hop-2 **0.96** (no full rebench). |
| 2026-11-03 | Recorded the five remaining hybrid misses and replaced the 24/24 calibration claim with hold-out κ. |
| 2026-11-04 | Corrected hold-out labels for Meta AI competition (0) and Meta AI glasses (0.5). Reported κ is 0.84, not the first-pass 0.00. |
| 2026-11-05 | Hybrid retrieval alternates vector then graph and always fetches both lists. Recall@5 **0.67 → 0.84**. Vector still leads recall@10 and MRR. |
| 2026-11-05 | Graph edges ranked by question-word hits; confidence is only the tie-break. Next rerun: hybrid recall@5 **0.83**, recall@10 **0.92**, MRR **0.64**. Rank fusion was not shipped (recall@5 would have fallen to 0.75). |
| 2026-11-05 | Re-ran hybrid answers on all 44. Mean **0.85**. Meta apps 0.00→0.75. Several former 1.0s dropped. One OOS item answered instead of refusing. |
| 2026-11-05 | Re-ran vector-only answers on all 44. Mean **0.875** (previous **0.886**). One item moved: Amazon AWS and Prime 1.0→0.50. Paired gap **−0.026**, interval **−0.112 to 0.062**. |
| 2026-11-05 | Planner, router, and judge set to temperature 0. Three full runs: hybrid **0.86** (0.856–0.862), vector-only **0.89** (0.878–0.889). Five items still moved. Apple products hybrid text was identical and the judge scored it 1.0, 1.0, 0.5. |

When a new bug shows up: add a section under **Closed** or **Open** and link the files. Keep claims tied to commits and results.
