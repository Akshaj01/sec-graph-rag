# Measure it — Phase plan (Plan P1 ≈ Roadmap P4)

**Living checklist** for the eval / calibration phase of SEC GraphRAG.  
Akshaj + Cursor both use this file as the source of truth while we work through it over the next days/weeks.

| | |
|--|--|
| **Maps to** | Personal plan **Project 1 · Measure it** (weeks 4–6) ≈ 6-project roadmap **Project 4 · LLM-as-Judge with Human Calibration**, applied to already-built GraphRAG (roadmap P1). |
| **Not this phase** | LLM gateway (plan P2), research agent / red-team (plan P3). |
| **Goal** | Defendable answer to *“How do you know your RAG is good?”* — numbers, κ, CI gate, honest failures — then move to gateway. |
| **Working style** | Learn by doing: Akshaj writes a short design note for each step; Cursor implements; Akshaj explains the non-trivial bits before commit. |
| **Status** | **DONE** 2026-11-06. Project 1 ship gate met. Published: three-run generation hybrid **0.93** / vector **0.90**; hop-2 is the real finding (CI above zero); overall gap CI includes zero; retrieval_v4; κ 0.84 with post-hoc caveat; recall gate green. Next phase is gateway ([`GATEWAY_PLAN.md`](GATEWAY_PLAN.md)). |

## Words this file uses

**Suite / golden set.** The 44 questions in `benchmarks/multi_company_smoke.json`, with the facts each answer is supposed to hit written down ahead of time. A score is a check against that list.

**Hop.** How many steps the question needs. Hop 0 is one definition ("what is AWS"). Hop 1 is one relationship ("what does Apple make"). Hop 2 joins or compares two facts ("JPM credit risk vs market risk"). Stratified means the 44 are spread across those buckets on purpose.

**OOS.** Out of scope. The filing does not contain the answer, so the right behavior is to refuse. 12 of the 44 are OOS.

**Required facts.** The checklist for an answerable question. The judge scores those facts. It does not score "does this paragraph sound like the sample answer."

**LLM-as-judge.** A model reads the system's answer and the required facts and gives a number. That model is not you. It can be wrong, which is why the human labels exist.

**Gold chunk.** The 10-K passage that actually contains a required fact, stored as an id. Retrieval is scored against these ids. Generation is scored against the facts.

**Retrieval vs generation.** Retrieval asks whether the search returned the right passages. Generation asks whether the written answer included the required facts. Those are two tables. A useful graph sentence can still miss the gold passage, so hybrid can win generation and lose retrieval.

**recall@k.** Of the gold chunks for one question, the fraction that showed up in the first k results. recall@5 uses the first 5. recall@10 uses the first 10. Two gold chunks, one of them in the top 5, scores 0.5.

**MRR.** Mean reciprocal rank. First gold chunk in slot 1 scores 1. Slot 4 scores 1/4. Missing entirely scores 0. Average those. It pays for a right chunk near the top, not just somewhere in the list.

**nDCG.** A ranking score that also cares how far down a relevant chunk sits, and can treat some chunks as more relevant than others. This phase left it optional and did not compute it.

**κ (kappa).** Cohen's kappa. A 0-to-1 score for "did two graders agree more than luck would." Raw agreement is the simpler count: 19/20 means the snapped scores matched on 19 questions. κ drops when one grader gives almost everything the same score, because matching is then easy to get by chance. Weighted κ means a near miss (you 1.0, judge 0.5) hurts less than a total miss (you 1.0, judge 0). This repo reports the linear version. Quadratic is logged next to it and punishes the total miss more.

**Hold-out.** The 20 questions that were not on the first 24-question practice sheet. The rubric was not edited from these. That is the κ in the README (0.84 after the two label fixes).

**Self-agreement.** You scored 15 questions, came back later, and scored them again without looking. That κ (0.42) is how steady you are. A judge cannot be expected to match you more tightly than you match yourself.

**Spearman.** Did the questions you scored higher also get scored higher by the judge? It compares the order, not the exact numbers. It was blank on the first hold-out pass because every human score was 1.0, so there was no order to compare.

**Snap.** The judge prints decimals like 0.125 or 0.667. Before κ, both sides are forced onto 0, 0.5, or 1. The midpoints 0.25 and 0.75 go up.

**Ablation.** Change one thing and measure again. Here the one thing is the graph. Hybrid is graph plus vectors. Vector-only is the same questions with the graph path removed. The gap between those two scores is the ablation.

**Gap.** Hybrid mean minus vector-only mean on the same questions. Positive means hybrid scored higher on average.

**Bootstrap.** A check on whether a slightly different draw of these 44 questions would still show that gap. Redraw 44 questions from the same 44, putting each one back, so some show up twice and some drop out. Recompute the gap. Do that 10,000 times. The interval is the middle 95% of those gaps.

**Paired.** A redrawn question brings its hybrid score and its vector score together. JPM's hybrid score stays with JPM's vector score.

**Confidence interval.** That middle 95%. The lead is stable only when the whole interval sits entirely above zero. Published numbers use the post-fix three-run package: mean of runs hybrid **0.93** / vector **0.90**; pooled-item bootstrap overall gap CI includes zero; hop-2 gap CI stays above zero (`ablation_bootstrap_three_run.md`). Older single-file / pre-fix intervals are history.

**Seed.** The redraws start from a fixed number (0), so running the script again prints the same interval.

**Percentile.** Sort the 10,000 gaps. The interval edges are the gaps at the 2.5% and 97.5% positions. The number reported as the gap is the gap on the original 44, not the average of the redraws.

**CI gate.** A GitHub Actions check. It fails if the saved hybrid recall@10 drops by more than 0.02. It reads a file and does not call a model. This "CI" means continuous integration. The other "CI" above means confidence interval.

---

## 1. Big picture

```
SEC GraphRAG (built) ──► Measure it (DONE) ──► Gateway (NEXT) ──► Agent + red-team
         ▲                        │
         └──── CI gate blocks regressions on this repo
```

**Ship story (met):**  
*Hybrid graph+vector RAG over ten companies' 10-Ks; 44 hop-stratified questions; graph wins where relationships matter (hop-2); overall gap small and CI includes zero; judge hold-out κ 0.84 (two labels corrected after seeing judge); retrieval and generation reported separately; CI fails PRs that tank recall.*

---

## 2. Already done (do not redo)

Track so we don’t thrash.

| Artifact | Status | Where |
|----------|--------|--------|
| Closed ontology + allowlisted Cypher + citations | Done | codebase |
| Hybrid vs vector-only runner | Done | `benchmark_runner.py` |
| Suite v3, n=44, hop 0/1/2 + OOS | Done | `benchmarks/multi_company_smoke.json` |
| LLM-as-judge vs `required_facts` | Done | `benchmark_judge.py` |
| Headline table (post-fix three-run mean: hybrid **0.93** / vector **0.90**; hop-2 CI above zero) | Done | README + `three_run_means.md` + `ablation_bootstrap_three_run.md` |
| Human ↔ judge agree **24/24** on older hybrid set | Done (agreement, not κ) | `benchmarks/judge_calibration_hybrid.md` |
| Failure → fix loop (false refuse, NFLX AWS, planner coerce, Apple supply…) | Done | `docs/PROBLEMS_AND_FIXES.md` |
| Internal build notes out of public surface | Done | `docs/archive/dev-notes/` |

**Ship gate:** all §3 boxes checked. Project 1 is closed.

---

## 3. Ship gate — **all checked; Project 1 DONE**

- [x] Stratified golden set with **gold chunk IDs** versioned in repo — suite **v4**, 32/32 answerable labeled, 12 OOS empty
- [x] **Retrieval** metrics (recall@5/10, MRR) **and** **generation** metrics, by hop, hybrid vs vector-only — `retrieval_v4.md`; three-run generation in README
- [x] Judge-vs-human **weighted Cohen’s κ** next to **self-agreement** — hold-out linear κ **0.84** (raw 19/20) after correcting two bad 1.0s; self-agreement κ **0.42**; rubric v1 unchanged
- [x] One **ablation** table with bootstrap CIs + recommendation — pooled three-run overall gap **+0.028**, CI **−0.006 – 0.067** (includes zero); hop-2 gap **+0.116**, CI **0.024 – 0.220** (above zero) (`ablation_bootstrap_three_run.md`)
- [x] **CI gate** demonstrated failing a bad PR — green [41779177304](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41779177304); red break [41782167624](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41782167624); baseline re-pinned to **0.9115**
- [x] README top: results → short capture → design decisions → **what didn’t work** (hop-2 lead first; stranger-readable)
- [x] Worst remaining failures explained — hop-1 soft misses on the three-run package (`PROBLEMS_AND_FIXES.md` + README)

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
**Status:** `done` — hold-out linear κ **0.84** (raw 19/20) after correcting Meta AI competition to 0 and Meta AI glasses to 0.5; first pass was κ **0.00**. Self-agreement κ **0.42** (13/15). Rubric v1 unchanged.  
**Why:** 24/24 “agree” can hide a judge that does not match a second pass. κ is the number that shows that.  
**You:** re-label ~15 items on a different day (self-agreement ceiling); hold out a slice for κ (don’t tune rubric on the report set).  
**Cursor:** worksheet generator; κ / Spearman computation; update calibration doc + README line.  
**Hand-write:** κ formula usage + rubric tweaks from disagreement reads.  
**Exit:** README reports weighted κ and self-agreement; rubric version noted.

### WP4 — Ablation + confidence intervals
**Status:** `done` — three-run mean + pooled bootstrap in README. Overall lead is not stable (CI includes zero); hop-2 lead is stable (CI above zero).  
**Why:** one measured change with uncertainty > vibes.  
**Pick one** (decide in session): hybrid vs vector-only is already the main ablation — formalize with bootstrap CIs on mean score and/or recall; **or** one config toggle (e.g. topic-gate on/off, multi-template on/off) if cheaper.  
**Cursor:** bootstrap helper + table.  
**You:** one paragraph recommendation.  
**Exit:** table + paragraph in README or `benchmarks/`.

### WP5 — CI regression gate
**Status:** `done` — green push run and red break dispatch are both on Actions.  
**Why:** proves eval isn’t a one-off notebook.  
**Cursor:** GitHub Actions workflow; cached/fixture mode so CI isn’t a $ bill; intentional bad PR demo notes.  
**You:** choose the fail threshold (start: recall@10 drop > 2 points on a fixed smoke subset).  
**Exit:** badge or Actions run showing green on main + red on a deliberate break (screenshot or link).

### WP6 — README packaging
**Status:** `done` — README opens with results, the 60-second pass, design decisions, and the five misses. Recording a demo is still optional.  
**Cursor:** README reorder; “What didn’t work” from PROBLEMS + JPM flake + false-refuse story; optional 60–90s capture script/checklist.  
**You:** record demo; write design-decisions in your words; LinkedIn one-liner later (optional).  
**Exit:** stranger can judge the repo in two minutes from README top.

### WP7 — Phase retrospective → gateway
**Status:** `done` — Project 1 ship gate met 2026-11-06. Retrospective below (updated). Gateway stub is `docs/GATEWAY_PLAN.md`. No gateway code until that design note.

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
4. Akshaj: write the core (metrics / κ / CI threshold) in NOTES before commit.  
5. Update this file: Status, checkboxes, **Session log**.  
6. Commit when a WP exit criterion is met (not every WIP).

**Rule from personal plan:** you drive design and the metric code; AI does boilerplate, UI, YAML, plots, docs glue. Never commit what you can’t explain.

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
| `bootstrap_ci.py` | Paired bootstrap CI for hybrid − vector-only |
| `benchmarks/results/three_run_means.md` | Post-fix three-run generation means |
| `benchmarks/results/ablation_bootstrap_three_run.md` | Published WP4 pooled bootstrap |
| `benchmarks/results/archive/ablation_bootstrap.md` | Older single-file bootstrap (history) |
| `recall_gate.py` | Fail if hybrid recall@10 drops more than 0.02 |
| `benchmarks/fixtures/recall_baseline.json` | Pinned v4 hybrid recall@10 |
| `.github/workflows/recall-gate.yml` | CI on the saved fixture |
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

**Result to be able to say:** hybrid retrieval alternates vector then graph. Graph edges are ordered by how many question words they hit; extraction confidence only breaks a tie. On the 2026-11-05 rerun, hybrid recall@5 is **0.83**, vector **0.82**. Vector still leads recall@10 (**0.93** vs **0.92**) and MRR (**0.67** vs **0.64**). The earlier graph-first hybrid number was recall@5 **0.67**. Graph-only is **0.43** / **0.38** on this run; the planner is not deterministic, so that column is not a clean before-and-after. This does not replace the generation table. The generation headline is three temperature-0 runs: hybrid **0.86** (0.856–0.862) vs vector **0.89** (0.878–0.889).

### WP3 — κ split (2026-11-02)

**Reported κ** is human vs judge on the **20** suite items that are not in `judge_calibration_hybrid.md`. That n=24 sheet stays history. Rubric stays **v1** (do not edit the judge prompt from this hold-out).

**Scale:** both sides snap to **0 / 0.5 / 1**. Nearest bin. Midpoints **0.25** and **0.75** snap upward. So judge **0.125 → 0**, **0.6675 → 0.5**.

**Weight:** reported number is **linear** weighted Cohen’s κ. A one-step miss counts half of a full miss. Quadratic is logged beside it.

**Self-agreement:** re-score **15** of the original 24 (both first-pass partials included). Compare to the first `your_score`, not to the judge. Sheets hide the other score.

**Sheets:** `benchmarks/calibration/kappa_holdout.md`, `benchmarks/calibration/self_agreement.md`. Score with `python calibration_worksheet.py score`.

### WP4 — bootstrap (2026-11-03)

**Draw:** one question at a time, with replacement, hybrid score and vector-only score kept together. **10,000** draws, seed **0**. **95%** interval = middle 95% of the recomputed gaps (linear percentile). Point estimate = mean of the original 44, not the mean of the draws.

**Result:** full-run overall gap **0.038**, interval **−0.047 to 0.126**. Hop-2 gap **0.005**, interval **−0.234 to 0.250**. `hop2_jpm_credit_vs_market` is the full-run **0.375**, not the later rerun of 1.0.

**Recommendation (Akshaj):** Hybrid scores higher on average (0.038 overall, 0.005 on hop 2), and neither 95% interval sits entirely above zero, so the lead is not stable on this suite.

### WP5 — recall gate (2026-11-03)

**Check:** hybrid recall@10 on the 32 answerable v4 items, read from `benchmarks/results/retrieval_v4.json`. Baseline pinned at **0.9115** (re-pinned after the 2026-11-06 `retrieval_v4` rebuild; was 0.9167). Fail when the drop is **greater than 0.02**. A drop of exactly 0.02 passes. The item ids are pinned too, so deleting a question does not raise the average.

**CI** runs `pytest test_recall_gate.py` and `python recall_gate.py`. No model, no database.

**Local demo:** `python recall_gate.py` prints drop **0.0000** and exits 0. `python recall_gate.py --degrade-first` zeros one hit (drop **0.0312**) and exits 1.

**Actions demo:** green push [41779177304](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41779177304). Red break dispatch [41782167624](https://github.com/Akshaj01/sec-graph-rag/actions/runs/41782167624): `gate` passed, `deliberate-break` failed on the zeroed hit.

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
| 2026-11-03 | WP4 | Paired bootstrap, 10k draws, seed 0. Overall gap 0.052, 95% CI −0.026 to 0.136. Hop-2 gap 0.083, CI 0.000 to 0.250. | Recommendation paragraph |
| 2026-11-03 | WP4 | Recommendation recorded: average lead is real, intervals do not sit entirely above zero, so the lead is not stable. | WP5 CI gate |
| 2026-11-03 | WP5 | Recall gate on saved hybrid recall@10. Threshold drop > 0.02. Local green drop 0.0000. Local red drop 0.0312. Pushed so Actions can run the green check. | Dispatch the break job for the red run |
| 2026-11-03 | WP5 | Break dispatch failed on purpose (`deliberate-break`). `gate` job on that run passed. | WP6 README packaging |
| 2026-11-03 | WP6 | README reordered: results, 60-second pass, design decisions, five remaining misses. | WP7 close the phase |
| 2026-11-03 | WP7 | Ship gate already checked. Retrospective written. Gateway stub opened. No gateway code. | Plan P2 design note, then the first gateway piece |
| 2026-11-04 | WP3 | Corrected two hold-out labels that contradicted the failure table: Meta AI competition 1.0→0, Meta AI glasses 1.0→0.5. Linear κ 0.00→0.84 (19/20). | — |
| 2026-11-05 | — | Temp-0 three-run package (pre-fix): hybrid **0.86** / vector **0.89**. Retrieval hybrid recall@5 **0.83**. | Hybrid-improve fixes |
| 2026-11-06 | — | Hybrid-improve + corpus restore + retrieval_v4 + P6 rebench; then two more temp-0 runs. Honest three-run mean **0.93** / **0.90**; pooled bootstrap; README rewrite; LICENSE; archive; recall baseline re-pin **0.9115**. | **Project 1 DONE** → gateway |

---

## 10. Retrospective (updated 2026-11-06)

**Project 1 ship gate is met.** Defendable answer to “how do you know the RAG is good?”:

- **Generation:** three temperature-0 runs after the hybrid-improve pass. Mean hybrid **0.93** (0.901–0.940) vs vector **0.90** (0.874–0.920). Paired gap **+0.028**. Pooled-item bootstrap: overall CI **−0.006 – 0.067** (includes zero); hop-2 gap **+0.116**, CI **0.024 – 0.220** (above zero). The graph helps where relationships matter; the suite-wide lead is not stable.
- **Retrieval (`retrieval_v4`):** hybrid recall@5 **0.84** / @10 **0.91** / MRR **0.70**. Vector **0.84 / 0.94 / 0.70**. Ties on @5 and MRR; vector leads @10. Graph-only ~0.41 and is planner-noisy.
- **Judge:** hold-out linear κ **0.84** (19/20) after two post-hoc label corrections (not a fully blind panel). Self-agreement κ **0.42**. Rubric v1 unchanged. A fresh blind 30–40 pass was deferred.
- **CI gate:** saved-file recall@10 check; baseline **0.9115**; max drop 0.02; green on main; deliberate-break dispatch still the red demo.
- **Open soft misses** (three-run hybrid means): compete-with-Meta 0.00, JPM credit-risk definition 0.50, NVDA/Waymo/MSFT/Meta AI product-list softness. Detail in README and `PROBLEMS_AND_FIXES.md`.

Demo recording and LinkedIn one-liner were optional and were not done.

## 11. After this phase

**Plan P2 · Run it** is next: [`docs/GATEWAY_PLAN.md`](GATEWAY_PLAN.md). Circuit breakers, semantic cache, chaos demo, then point model calls through it. Write the design note before any gateway code. Plan P3 (agent / red-team) stays closed.
