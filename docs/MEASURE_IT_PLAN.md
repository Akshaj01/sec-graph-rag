# Measure it — Phase plan (Plan P1 ≈ Roadmap P4)

**Living checklist** for the eval / calibration phase of SEC GraphRAG.  
Akshaj + Cursor both use this file as the source of truth while we work through it over the next days/weeks.

| | |
|--|--|
| **Maps to** | Personal plan **Project 1 · Measure it** (weeks 4–6) ≈ 6-project roadmap **Project 4 · LLM-as-Judge with Human Calibration**, applied to already-built GraphRAG (roadmap P1). |
| **Not this phase** | LLM gateway (plan P2), research agent / red-team (plan P3). |
| **Goal** | Defendable answer to *“How do you know your RAG is good?”* — numbers, κ, CI gate, honest failures — then move to gateway. |
| **Working style** | Learn by doing: Akshaj writes a short design note for each step; Cursor implements; Akshaj explains the non-trivial bits before commit. |

---

## 1. Big picture

```
SEC GraphRAG (built) ──► Measure it (THIS PHASE) ──► Gateway ──► Agent + red-team
         ▲                        │
         └──── CI gate blocks regressions on this repo
```

**Ship story when done:**  
*Hybrid graph+vector RAG over 10-Ks; N hop-stratified questions; judge calibrated to humans at κ=X; retrieval and generation reported separately; CI fails PRs that tank recall; hybrid leads multi-hop vs vector-only.*

---

## 2. Already done (do not redo)

Track so we don’t thrash.

| Artifact | Status | Where |
|----------|--------|--------|
| Closed ontology + allowlisted Cypher + citations | Done | codebase |
| Hybrid vs vector-only runner | Done | `benchmark_runner.py` |
| Suite v3, n=44, hop 0/1/2 + OOS | Done | `benchmarks/multi_company_smoke.json` |
| LLM-as-judge vs `required_facts` | Done | `benchmark_judge.py` |
| Headline table (hybrid **0.94** / vector **0.89**; hop-2 **0.96** / **0.88**) | Done | README + `…_judged.json` |
| Human ↔ judge agree **24/24** on older hybrid set | Done (agreement, not κ) | `benchmarks/judge_calibration_hybrid.md` |
| Failure → fix loop (false refuse, NFLX AWS, planner coerce, Apple supply…) | Done | `docs/PROBLEMS_AND_FIXES.md` |
| HANDOFF / agents notes out of root | Done | `docs/dev-notes/` |

**Still weak vs plan ship gate:** no gold-chunk retrieval metrics, no weighted κ, no CI gate, README “what didn’t work” / demo still thin, no bootstrap CI on the ablation.

---

## 3. Ship gate (done when all checked)

Copy from personal plan; tick as we finish.

- [x] Stratified golden set with **gold chunk IDs** versioned in repo (extend v3; don’t throw away n=44) — suite **v4**, 32/32 answerable labeled, 12 OOS empty
- [x] **Retrieval** metrics (recall@5/10, MRR) **and** **generation** metrics, by hop, hybrid vs vector-only — retrieval table in `benchmarks/results/retrieval_v4.md`; generation table already in README
- [x] Judge-vs-human **weighted Cohen’s κ** reported next to **self-agreement** (re-label ~15 items) — hold-out linear κ **0.00** (raw 17/20); self-agreement κ **0.42** (13/15); rubric v1 unchanged (`benchmarks/calibration/RESULTS.md`)
- [ ] One **ablation** table with bootstrap CIs + one-paragraph recommendation
- [ ] **CI gate** demonstrated failing a bad PR (e.g. recall@10 drop > ~2 points; cache LLM calls)
- [ ] README top: results → short capture → design decisions → **what didn’t work**
- [ ] Five worst remaining failures explained in NOTES / PROBLEMS

**Explicitly out of scope for this phase:** nDCG (optional), hosted demo, gateway, new RAG features unless a metric forces a tiny fix.

---

## 4. Work packages (do in order)

Each package = 1–3 sessions. Update **Status** as we go: `todo` | `in_progress` | `done`.

### WP0 — Kickoff / design ownership
**Status:** `done`  
**You hand-write:** half-page design: what “good” means for retrieval vs generation; which metrics; hold-out for κ.  
**Cursor:** tutor + clarify; none until design exists.  
**Exit:** design pasted under §8 or linked from NOTES. ✅

### WP1 — Gold chunk IDs on the suite
**Status:** `done` (5-item spot-check accepted 2026-11-01, including Meta Item1A:4)  
**Why:** retrieval metrics need labeled relevant chunks; answer-judge alone can’t separate retrieve vs generate failures.  
**You:** for each non-OOS item (or a agreed subset if time-boxed), verify 1–3 `gold_chunk_ids` from real filings (schema already has the field).  
**Cursor:** labeling helper / Streamlit-or-CLI to browse chunks by ticker+query; suite JSON updates; validation that IDs exist in the store.  
**Exit:** ≥ most answerable items have `gold_chunk_ids`; OOS stay empty; suite version bumped or notes updated. ✅ suite v4; `label_chunks.py check --postgres` ok.

### WP2 — Retrieval metrics harness
**Status:** `done`  
**Why:** “Is the pack wrong or the answer model wrong?”  
**You own conceptually:** recall@k, MRR definitions; hop bucketing.  
**Cursor:** script that runs graph / vector / hybrid **retrieve-only**, scores vs gold chunks, writes JSON + table by hop.  
**Hand-write (plan rule):** core metric functions (or thoroughly re-derive them in NOTES if AI drafts).  
**Exit:** README or `benchmarks/results/` table: recall@5/10 + MRR by hop × system. ✅ `benchmarks/results/retrieval_v4.md`

### WP3 — Weighted κ + self-agreement
**Status:** `done` — hold-out linear κ **0.00** (raw 17/20); self-agreement κ **0.42** (13/15); rubric v1 unchanged  
**Why:** 24/24 “agree” ≠ calibrated κ; interviewers ask for κ / bias honesty.  
**You:** re-label ~15 items on a different day (self-agreement ceiling); hold out a slice for κ (don’t tune rubric on the report set).  
**Cursor:** worksheet generator; κ / Spearman computation; update calibration doc + README line.  
**Hand-write:** κ formula usage + rubric tweaks from disagreement reads.  
**Exit:** README reports weighted κ and self-agreement; rubric version noted.

### WP4 — Ablation + confidence intervals
**Status:** `todo`  
**Why:** one measured change with uncertainty > vibes.  
**Pick one** (decide in session): hybrid vs vector-only is already the main ablation — formalize with bootstrap CIs on mean score and/or recall; **or** one config toggle (e.g. topic-gate on/off, multi-template on/off) if cheaper.  
**Cursor:** bootstrap helper + table.  
**You:** one paragraph recommendation.  
**Exit:** table + paragraph in README or `benchmarks/`.

### WP5 — CI regression gate
**Status:** `todo`  
**Why:** proves eval isn’t a one-off notebook.  
**Cursor:** GitHub Actions workflow; cached/fixture mode so CI isn’t a $ bill; intentional bad PR demo notes.  
**You:** choose the fail threshold (start: recall@10 drop > 2 points on a fixed smoke subset).  
**Exit:** badge or Actions run showing green on main + red on a deliberate break (screenshot or link).

### WP6 — Packaging for interviews
**Status:** `todo`  
**Cursor:** README reorder; “What didn’t work” from PROBLEMS + JPM flake + false-refuse story; optional 60–90s capture script/checklist.  
**You:** record demo; write design-decisions in your words; LinkedIn one-liner later (optional).  
**Exit:** stranger can judge the repo in two minutes from README top.

### WP7 — Phase retrospective → gateway
**Status:** `todo`  
**Exit:** all ship-gate boxes checked; open `docs/` gateway plan stub or start plan P2.

---

## 5. Suggested calendar (flexible)

| Window | Focus | Notes |
|--------|--------|--------|
| Days 1–2 | WP0 + WP1 start | Design first; begin gold chunks on hop-1/2 (highest value) |
| Days 3–5 | WP1 finish + WP2 | Retrieval table exists |
| ~1 week | WP3 | Re-label day separated from first labels |
| Next | WP4 + WP5 | Ablation + CI |
| Last | WP6 + WP7 | Package; then gateway |

If only **~10h/week**: keep n≈40–44, skip nDCG, one ablation (hybrid vs vector), 60s capture instead of edited video — ship gate otherwise unchanged.

---

## 6. How we work each session

1. Pick **one WP** (or a sub-bullet) from this file.  
2. Akshaj: 5–15 min design note (what / decide / measure) — can be in chat or §8.  
3. Cursor: implement + tests.  
4. Akshaj: explain the core (metrics / κ / CI threshold) out loud or in NOTES before commit.  
5. Update this file: Status, checkboxes, **Session log**.  
6. Commit when a WP exit criterion is met (not every WIP).

**Rule from personal plan:** you drive design and interview-critical code; AI does boilerplate, UI, YAML, plots, docs glue. Never commit what you can’t explain.

---

## 7. Key paths (quick map)

| Path | Role |
|------|------|
| `benchmarks/multi_company_smoke.json` | Golden suite v4 (gold chunks on all answerable items) |
| `label_chunks.py` | Search ingest chunks; `check` gold ids vs cache / Postgres |
| `benchmark_schema.py` | `gold_chunk_ids`, `required_facts`, … |
| `benchmark_runner.py` / `benchmark_judge.py` | Answer eval |
| `benchmarks/judge_calibration_hybrid.md` | n=24 history (not the reported κ) |
| `benchmarks/calibration/` | WP3 hold-out sheet, self-agreement sheet, hidden keys |
| `calibration_metrics.py` / `calibration_worksheet.py` | snap, linear κ, Spearman; write and score sheets |
| `benchmarks/results/` | Reports (`retrieval_v4.md` is the WP2 table) |
| `retrieval_metrics.py` / `retrieval_benchmark.py` | recall@k, MRR, retrieve-only runner |
| `docs/PROBLEMS_AND_FIXES.md` | Failure → fix history |
| `docs/MEASURE_IT_PLAN.md` | **This file** |
| `README.md` | Public headline |

---

## 8. Design notes (paste session designs here)

### WP0 — done (2026-11-01)

**What “good” means:**  
The system is good if: (1) it retrieves evidence that actually supports the question (graph, vector, or both — whichever fits — quality of the pack over volume), (2) it answers accurately from that evidence with valid citations for claims it makes, and (3) it refuses when the corpus doesn’t support an answer. A high answer score with a wrong pack is still a retrieval failure. Answering an OOS question is a refuse failure.

**Retrieval metric choice:** Headline **recall@5** + **MRR**. Also log **recall@10** as supporting.  

**Generation metrics:** Hop-stratified **LLM-as-judge** vs `required_facts` / OOS refuse; **hybrid vs vector-only**. Keyword recall secondary.  

**κ hold-out plan:** `judge_calibration_hybrid.md` **24/24** = history / rubric-debug only. **Reported κ** on a held-out slice of **~15–20 items from suite v3** (not used to tweak the rubric after freeze). Also re-label ~15 later for self-agreement.  

**Ablation choice:** Formalize **hybrid vs vector-only** with **bootstrap CIs** (overall + preferably hop-2).

### WP1 — gold chunks (2026-11-01)

**Rule:** smallest covering set, max 3. A chunk counts only if its text supports at least one `required_fact`. One chunk when it covers every fact. A second chunk when a fact lives in a different passage (hop-2 with two topics). Out-of-scope stays empty. Labels come from ingest-cache text, not from hybrid citations.

**Exception to read:** `hop1_aapl_competes_meta` gold is Meta `Item1A:4` (Apple “integrated competitive products”). Apple’s own chunks never name Meta. A ticker-scoped AAPL retrieve will miss this on purpose. Spot-check accepted this label.

### WP2 — retrieval metrics (2026-11-01)

**recall@k** = (gold chunks found in the first k unique retrieved ids) / (number of gold chunks). Each question counts once.

**MRR** = 1 / rank of the first gold chunk. Rank 1 → 1.0. No gold chunk in the list → 0.

**Rank:** first time a chunk id appears. Hybrid list is graph ids, then vector ids that were not already in the graph list. Vector list is depth 10. Out-of-scope items are not scored.

**Result to be able to say:** on suite v4, vector retrieval leads (overall recall@5 **0.82**, MRR **0.67**). Hybrid is lower (**0.67** / **0.51**) because graph chunks are placed first and often are not the gold prose chunks. Graph alone is lower still (**0.42** / **0.37**). This does not replace the generation table (hybrid **0.94** vs vector **0.89**). A good answer can come from a graph statement whose source chunk is not the gold passage.

### WP3 — κ split (2026-11-02)

**Reported κ** is human vs judge on the **20** suite items that are not in `judge_calibration_hybrid.md`. That n=24 sheet stays history. Rubric stays **v1** (do not edit the judge prompt from this hold-out).

**Scale:** both sides snap to **0 / 0.5 / 1**. Nearest bin. Midpoints **0.25** and **0.75** snap upward. So judge **0.125 → 0**, **0.6675 → 0.5**.

**Weight:** reported number is **linear** weighted Cohen’s κ. A one-step miss counts half of a full miss. Quadratic is logged beside it.

**Self-agreement:** re-score **15** of the original 24 (both first-pass partials included). Compare to the first `your_score`, not to the judge. Sheets hide the other score.

**Sheets:** `benchmarks/calibration/kappa_holdout.md`, `benchmarks/calibration/self_agreement.md`. Score with `python calibration_worksheet.py score`.

---

## 9. Session log

| Date | WP | What happened | Next |
|------|----|---------------|------|
| 2026-10-28 | — | Plan file created after GraphRAG rebench (hybrid 0.94). | WP0 design, then WP1 gold chunks |
| 2026-11-01 | WP0 | Pasted “what good means” (retrieve / answer+cite / refuse). | Finish WP0: metrics, κ hold-out, ablation |
| 2026-11-01 | WP0 | Closed: recall@5+MRR (+@10), hop judge H vs V, κ on 15–20 v3 hold-out, ablation H vs V + bootstrap CI. | WP1 gold chunk IDs |
| 2026-11-01 | WP1 | Suite v4: gold chunks on 32/32 answerable items (12 OOS empty). `label_chunks.py` + check vs ingest cache and Postgres. | Spot-check 5 labels, then WP2 retrieval harness |
| 2026-11-01 | WP1 | Spot-check accepted, including Meta Item1A:4 for Apple–Meta competition. | WP2 |
| 2026-11-01 | WP2 | Retrieve-only recall@5/10 + MRR by hop for graph, vector, hybrid. Vector leads retrieval; hybrid leads generation. | WP3 κ |
| 2026-11-02 | WP3 | Blind hold-out (n=20) and self-agreement (n=15) sheets. Linear κ on snapped 0/0.5/1. Rubric v1 frozen. | Fill both sheets, then `calibration_worksheet.py score` |
| 2026-11-02 | WP3 | Blind hold-out scored all **1.0**. Linear κ **0.0**, raw agreement **0.85** (17/20). Splits: Meta AI competition, Meta AI glasses, NVDA auto competitors. Spearman undefined. | Self-agreement sheet still blank |
| 2026-11-03 | WP3 | Self-agreement re-label. Linear κ **0.42**, raw **13/15**. Flips: AWS 1.0→0.5, JPM credit risk 0.5→1.0. README line added. Rubric not changed. | WP4 bootstrap CIs |

---

## 10. After this phase

**Plan P2 · Run it** — resilient LLM gateway (circuit breakers, semantic cache, chaos demo).  
Point SEC GraphRAG model calls through the gateway once it exists.  
Do **not** start P2 until §3 ship gate is honestly checked.
