# Hybrid improve plan

**Status:** in progress (paused 2026-11-06)  
**Goal:** Make hybrid generation beat, or at least match, vector-only on the published 44-question suite — without lying about numbers.

| | |
|--|--|
| **Baseline headline** | Three temperature-0 runs: hybrid **0.86** vs vector **0.89** (gap **−0.026**) |
| **Retrieval baseline** | Hybrid recall@5 **0.83** / @10 **0.92** / MRR **0.64** · Vector **0.82 / 0.93 / 0.67** |
| **Living failure log** | [`PROBLEMS_AND_FIXES.md`](PROBLEMS_AND_FIXES.md) |
| **Published tables** | README · `benchmarks/results/multi_company_smoke_temp0_run{1,2,3}.json` · `retrieval_v4.md` |

This file is the checklist for the post–Measure-it hybrid push. Gateway (`GATEWAY_PLAN.md`) is a different track.

---

## Progress snapshot

| | Count | Notes |
|--|--:|--|
| **Done** | 1 hard zero closed (retrieve + window) | `hop1_meta_ai_competition` one-item resmoke **0.875** |
| **Left (generation misses)** | ~7 items still &lt; 1.0 on the three-run hybrid mean | See queue below |
| **Left (infra before full rebench)** | Corpus restore on this PC | Need all 10 tickers in Neo4j + pgvector |
| **Left (publish)** | Full 44×2 answer rebench + README rewrite | Only after enough fixes land |

Rough completion of *this* plan: **~35%** (Meta AI end-to-end; P1 refuse code landed, live resmoke waiting on Anthropic credits; headline not updated yet).

---

## Done

### D1. Meta AI competition — retrieve (§16)

| | |
|--|--|
| **Problem** | Gold `Item1A:0` at dense rank ~21; over-fetch capped at 15; flat needle boost saturated. |
| **Fix** | `over_fetch_k` (25–40) + named-rival competition boost (+0.30). |
| **Result** | Item recall@5/10/MRR **0.67 → 1.0**. |
| **Artifacts** | `benchmarks/results/retrieval_meta_ai_overfetch_comp_boost.json` |

### D2. Meta AI competition — answer window (§17)

| | |
|--|--|
| **Problem** | Gold chunk cited but TikTok at char ~5092 outside the 1200-char window. |
| **Fix** | Keep `AI` in `query_needles`; competition asks center on named-rival markers. |
| **Result** | One-item resmoke hybrid/vector **0.00/0.125 → 0.875**. |
| **Artifacts** | `benchmarks/results/hop1_meta_ai_competition_window_resmoke.json` |

### D3. Docs / publish hygiene (partial)

| | |
|--|--|
| **Done** | Logged in PROBLEMS_AND_FIXES; README footnote; profile README note; repo description. |
| **Not done** | Rewrite the three-run headline table (needs full rebench). |

### Attempted, insufficient alone

| | |
|--|--|
| **A0** | Keep short acronym `AI` in vector `lexical_needles` — no recall move by itself. Kept as correctness. |

---

## Still to do (ordered)

Work one step at a time: fix → targeted retrieve and/or answer resmoke → log → ask before the next step. Same loop as Meta AI.

### P1. False-premise OOS refuse — `oos_nflx_ai_compute_for_others`

| | |
|--|--|
| **Why** | Hard **0.00** on all three hybrid runs. Denies the premise in prose but leaves `refused=false`, so the judge zeros it. |
| **Code** | **DONE 2026-11-06** — `looks_like_false_premise_for_others` + topic gate + skip unjustified-refuse repair + final force-refuse. Tests green. Logged §A2. |
| **Verify** | **BLOCKED** — Anthropic API: credit balance too low. NFLX text is embedded; graph extract still needed after credits. Then one-item hybrid+vector resmoke. |
| **Est. cost** | ~$0.97 NFLX extract + ~$0.05–0.15 answer/judge. |

### P2. Named product / brand misses (pack or window)

Same pattern as Meta: graph laundry list or wrong window hides the brand name.

| Item | Three-run hybrid mean | Missing |
|------|----------------------:|---------|
| `hop1_msft_products` | 0.13 | Azure, Xbox |
| `hop2_nvda_auto_competitors_risks` | 0.42 | DRIVE / autonomous |
| `hop0_meta_ai_glasses` | 0.50 | Ray-Ban Meta / Oakley Meta |
| `hop1_nvda_automotive` | (was 0.50 on earlier hybrid file) | DRIVE |
| `hop2_msft_cloud_and_geo_risk` | (was 0.50 on earlier hybrid file) | Azure |

| | |
|--|--|
| **Likely work** | Prefer VECTOR (or named-needle windows) when the question names a product brand; stop unmatched `PRODUCES_PRODUCT` from crowding the pack. |
| **Verify** | Targeted resmokes per item after each change. |
| **Est. cost** | ~$0.10–0.25 per item × both modes. |

### P3. Remaining soft misses (lower priority)

| Item | Mean | Notes |
|------|-----:|-------|
| `hop2_jpm_credit_vs_market` | 0.63 | Flaky historically (0.38 / 1.0 / 0.63). May be judge + pack. |
| `hop1_aapl_products` | 0.83 | Same text; judge moved 1.0→0.5 once. Not a retrieve bug. |
| `hop1_meta_apps` | 0.83 | Mostly fixed vs old refusal; polish only. |
| `hop1_nflx_aws_relationship` | (0.50 on earlier file) | Dual AWS supplier + Amazon retail compete. |

### P4. This-PC corpus restore

| | |
|--|--|
| **Why** | Full retrieve rebuild and honest full rebench need all 10 tickers. This PC had AAPL/JOBY/WDC (+ META embedded for the Meta work). |
| **Work** | `grow_corpus.py` for missing: `AMZN GOOGL JNJ JPM MSFT NFLX NVDA XOM` (and confirm META extract/graph, not just embed). |
| **Est. cost** | On the order of **~$15–25** extract+embed if nothing is cached (META alone was ~$2.19 extract). Run `--budget` first. |

### P5. Full retrieve rebuild (`retrieval_v4`)

| | |
|--|--|
| **When** | After P4 (and any retrieve-side fixes from P1–P2). |
| **Work** | `retrieval_benchmark.py --suite benchmarks/multi_company_smoke.json --confirm` |
| **Est. cost** | Embeddings already paid; still pays router/planner/embed-query calls — cheaper than full answers. |

### P6. Full generation rebench → new headline

| | |
|--|--|
| **When** | After P1–P2 look good on targeted resmokes (optional: after P3). |
| **Work** | `benchmark_runner.py --suite benchmarks/multi_company_smoke.json --modes hybrid,vector_only --confirm` (prefer temperature-0, ideally 1 run first; 3 runs only if publishing a new range). |
| **Est. cost** | ~**$0.80–1.00** per full 44×2 run (last three-run package was ~$2.59). |
| **Then** | Rewrite README hop table, profile README, repo description, HANDOFF. Do **not** patch one item into the old mean and call it the headline. |

---

## Out of scope for this plan

- Gateway design / code (`docs/GATEWAY_PLAN.md`) — separate track  
- Multi-ticker retrieve / question fan-out  
- Rubric edits to juice Meta AI from 0.875 → 1.0  
- Quoting the old hybrid **0.92** pair  

---

## Definition of done

1. Targeted fixes for P1 and the worst P2 items land with logged resmokes in PROBLEMS_AND_FIXES.  
2. Full corpus on the machine that will publish.  
3. One (or three) full temperature-0 generation rebench(es) written under `benchmarks/results/`.  
4. README + profile + HANDOFF quote the **new** measured means — not the 2026-11-05 three-run table.

Until step 4, the public headline stays **0.86 vs 0.89**.

---

## Suggested next session

1. Top up Anthropic credits.  
2. Finish **P1 verify**: `grow_corpus.py NFLX --confirm` then one-item resmoke.  
3. Then **P2** (MSFT Azure/Xbox or NVDA DRIVE) or **P4** corpus grow.  
4. Do not start P6 until you say so.

**Last updated:** 2026-11-06 (P1 code in; credits blocked)
