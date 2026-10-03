# Problems & Fixes — Interview Learning Log

Living log of real failures we hit building SEC GraphRAG, why they happened, and what we changed.  
Use this to prep interviews: every row is a story of **symptom → root cause → fix → what you’d say out loud**.

**Repo:** https://github.com/Akshaj01/sec-graph-rag  
**Last updated:** 2026-10-03

---

## How to use this in interviews

1. Pick 2–3 stories (metric lie, cross-issuer leak, hop-2, ticker clobber).
2. Speak in this order: **what broke → how I found it → what I changed → what I’d still improve**.
3. Prefer numbers and file names over buzzwords.
4. Be honest about open issues (hop-0 false refuses, small-n bench).

---

## Closed problems (fixed)

### 1. Extraction truncation (dense Item 1)

| | |
|--|--|
| **Symptom** | Structured extract cut off mid-JSON / missing entities on long 10-K sections. |
| **Root cause** | Default `EXTRACTION_MAX_TOKENS=4096` too small for Item 1. |
| **Fix** | Raise to `16384` via `.env` / settings (`EXTRACTION_MAX_TOKENS`). |
| **Where** | `config.py`, `.env.example` |
| **Interview angle** | “Token limits aren’t abstract — they silently corrupt structured extraction. I treat max_tokens as a product knob and verify with a smoke extract.” |

---

### 2. Global Company ticker clobber

| | |
|--|--|
| **Symptom** | After growing a multi-company corpus, Apple’s Company node could show another issuer’s ticker (last writer wins). |
| **Root cause** | `Company` is a **global** node (shared across filings). Early writes stored a single `ticker` property and overwrote it on every MERGE. |
| **Fix** | `home_ticker` set only when the filing **issuer** writes that Company; accumulate `tickers[]` for all mentioning filings. |
| **Where** | `resolver.py` (`is_issuer`, `mark_issuer_company`), `graph_writer.py` (`_merge_global_entity`), `test_ticker_clobber.py` |
| **Interview angle** | “Global entities need multi-valued provenance. Issuer identity and ‘mentioned in filing X’ are different facts — I stopped conflating them.” |

---

### 3. Risk / Product / Executive identity collisions

| | |
|--|--|
| **Symptom** | Unrelated companies’ “Cybersecurity” risks or similarly named products could merge onto one node. |
| **Root cause** | Canonical ids were name-only for types that are **not** shared across issuers. |
| **Fix** | Ticker-prefix RiskFactor / ProductLine / Executive ids (`AAPL_IPHONE` vs `META_FACEBOOK`). Keep Company / Subsidiary / Supplier global. |
| **Where** | `resolver.py` (`TICKER_SCOPED_ENTITY_TYPES`, `canonical_entity_id`) |
| **Interview angle** | “Ontology design is about which entities are world-unique vs issuer-local. Getting that wrong looks fine on a one-company demo.” |

---

### 4. Hop-2 hybrid failures (refuse / thin answers / weak packs)

| | |
|--|--|
| **Symptom** | Multi-relation questions (products **and** risks, segment compares) failed or refused even when graph had the edges; hop-2 scores lagged. |
| **Root causes** | (a) Planner often returned **one** template for a two-aspect ask. (b) Evidence packs blew token budget / order was wrong. (c) Answer model **false-refused** despite usable graph facts. |
| **Fix** | Multi-template plans + deterministic `augment_template_ids`; evidence caps / packing; unjustified-refuse repair and `draft_from_graph_evidence` fallback; raise answer token budget where needed. |
| **Where** | `graph_retriever.py`, `answer.py`, `config.py` (`ANSWER_MAX_TOKENS`, evidence caps) |
| **Interview angle** | “Retrieval wasn’t always the bug — packing and answer-time refuse heuristics were. I fixed the path end-to-end, then re-benched hop-2.” |

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
| **Interview angle** | “My keyword metric said multi-hop was perfect. I found 1.0 scores on wrong answers, replaced it with a fact-checklist judge, and published the honester numbers. That’s evals engineering.” |

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
| **Interview angle** | “Citation validation only proves ‘we retrieved it,’ not ‘it’s the right issuer.’ Eval found Meta chunks on an Apple answer; I fixed write + retrieve + cleaned Neo4j.” |

---

### 7. Cost / confirm gates (process, not a code bug)

| | |
|--|--|
| **Symptom** | Easy to accidentally burn paid extract/answer calls. |
| **Fix** | `budget.py`, `--confirm` on grow/benchmark, rough cost estimates in runners. |
| **Where** | `budget.py`, `grow_corpus.py`, `benchmark_runner.py` |
| **Interview angle** | “I treat LLM spend like an API quota — estimate, smoke, then confirm full runs.” |

---

### 8. Hop-0 false refuses (AppleCare / Azure) — wrong evidence *window*

| | |
|--|--|
| **Symptom** | “What is AppleCare?” / “What is Azure?” refused (`refused=true`, score 0) even though those terms exist in the same 10-K chunks other answers cite. |
| **Root cause** | Right chunks were retrieved, but `ANSWER_MAX_VECTOR_CHARS=1200` **prefix**-truncated passages. AppleCare sat ~char 1744; Azure often later. The model honestly refused the head-only pack. Unjustified-refuse repair is GRAPH-only, so it never helped. A first window fix also had to prefer **question** needles over passage `entity_ids` (iPhone/Mac appear earlier and stole the window). |
| **Fix** | `truncate_passage_for_query` (query-centered window); post-HNSW lexical/entity boost + over-fetch in `vector_retriever.py`. |
| **Where** | `answer.py`, `vector_retriever.py`, `test_answer_evidence.py`; smoke report `benchmarks/results/multi_company_smoke_hop0_fix.json` |
| **Verify** | Rebench both items × hybrid/vector_only → all **score=1.0**, `refuse=False`. |
| **Interview angle** | “The refuse wasn’t over-caution — we truncated away the definition. Eval said refuse; I fixed packing, not the prompt.” |

---

## Open / known weaknesses (not fully fixed)

### B. Small labeled set (n=24)

| | |
|--|--|
| **Symptom** | Hop buckets have 4–8 items; a 0.2 swing can be ~1–2 questions. |
| **Status** | Acknowledged in README; growing to 80–120 is future work, not claimed. |
| **Interview angle** | “Signal, not proof. I report n and don’t oversell.” |

---

### C. Judge not calibrated to human labels

| | |
|--|--|
| **Symptom** | No published “judge agrees with me X% of the time” number yet. |
| **Status** | Open — ~1–2 hours of hand-labeling the 24 would close this for interviews. |

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
4. Recruiter packaging (README, screenshots, public repo)  
5. **LLM judge** replaces keyword as primary metric  
6. **Cross-issuer leak** found in judged/keyword results → write gate + retrieve filter + cleanup  
7. **Hop-0 false refuses** → query-centered vector windows + lexical re-rank (AppleCare/Azure smoke = 1.0)  

---

## Quick “story cards” (memorize these)

**Card 1 — Metric lied**  
Keyword gave J&J / JPM 1.0 on bad answers → fact-checklist LLM judge → 0.79 vs 0.76 overall, hop-2 still clearly hybrid.

**Card 2 — Eval → systems fix**  
Apple products cited Meta accession → global Company + Meta-written `PRODUCES_PRODUCT` → issuer write gate + chunk ticker filter + Neo4j cleanup.

**Card 3 — Multi-company identity**  
Last-write `ticker` clobber and unscoped product/risk ids → `home_ticker` / `tickers[]` + ticker-prefixed local types.

**Card 4 — Hop-2**  
One template + refuse heuristics ≠ multi-hop failure of retrieval → multi-template plans + evidence packing + refuse repair.

**Card 5 — Hop-0 windowing**  
AppleCare/Azure “not in evidence” while sitting mid-chunk past a 1200-char head truncate → query-centered windows (+ don’t let entity_ids steal the needle).

---

## Changelog for this doc

| Date | Note |
|------|------|
| 2026-10-03 | Initial log from build + packaging + judge + cross-issuer leak work. |
| 2026-10-03 | Closed hop-0 AppleCare/Azure false refuses (passage window + lexical re-rank). |

When you hit a new bug: add a section under **Closed** or **Open**, link files, and one interview sentence. Keep claims tied to commits/results — don’t invent scale.
