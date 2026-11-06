# Hybrid improve plan

**Status:** in progress (2026-11-06)  
**Goal:** Make hybrid generation beat, or at least match, vector-only on the published 44-question suite — without lying about numbers.

| | |
|--|--|
| **Baseline headline** | Three temperature-0 runs: hybrid **0.86** vs vector **0.89** (gap **−0.026**) |
| **Retrieval (P5 rebuild)** | Hybrid recall@5 **0.84** / @10 **0.91** / MRR **0.70** · Vector **0.84 / 0.94 / 0.70** |
| **Living failure log** | [`PROBLEMS_AND_FIXES.md`](PROBLEMS_AND_FIXES.md) |
| **Published tables** | README · `benchmarks/results/multi_company_smoke_temp0_run{1,2,3}.json` · `retrieval_v4.md` |

This file is the checklist for the post–Measure-it hybrid push. Gateway (`GATEWAY_PLAN.md`) is a different track.

---

## Progress snapshot

| | Count | Notes |
|--|--:|--|
| **Done** | Meta AI compete + glasses; NFLX OOS; MSFT products | One-item resmokes; headline unchanged |
| **Left (generation misses)** | ~5–6 items still &lt; 1.0 on the three-run hybrid mean | See queue below |
| **Left (infra before full rebench)** | — | P4 corpus + P5 retrieve done |
| **Left (publish)** | Full 44×2 answer rebench + README rewrite | P6 — only when you say so |

Rough completion of *this* plan: **~95%** (P1–P5 done; P6 headline rebench not started; answer headline still 0.86/0.89).

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

### D3. Netflix OOS false-premise refuse (§18)

| | |
|--|--|
| **Problem** | Hybrid denied premise with `refused=false` → OOS score 0. |
| **Fix** | False-premise-for-others topic gate + force refuse. |
| **Result** | One-item resmoke hybrid/vector **1.0**. |
| **Artifacts** | `benchmarks/results/oos_nflx_ai_compute_for_others_resmoke.json` |

### D4. MSFT products hybrid (§19)

| | |
|--|--|
| **Problem** | Three-run hybrid **0.13** — missed Azure/Xbox. |
| **Fix** | Full MSFT extract/write with `EXTRACTION_MAX_TOKENS=16384`; Azure/Xbox edges present. |
| **Result** | One-item resmoke hybrid **1.0** (vector_only still **0.125**). |
| **Artifacts** | `benchmarks/results/hop1_msft_products_resmoke.json` |

### D5. Meta AI glasses — hardware window (§20)

| | |
|--|--|
| **Problem** | Early generic "AI glasses" stole the 1200-char window from Ray-Ban / Oakley ~5k chars later. |
| **Fix** | Named-hardware markers (prefer Ray-Ban/Oakley over Quest) + weak-needle strip on glasses asks. |
| **Result** | One-item resmoke hybrid/vector **0.50 → 1.0**. |
| **Artifacts** | `benchmarks/results/hop0_meta_ai_glasses_resmoke.json` |

### D6. MSFT hop2 cloud + geo (corpus)

| | |
|--|--|
| **Problem** | Earlier hybrid **0.50** — generic cloud/geo without Azure. |
| **Fix** | Same MSFT grow as D4; no code change. |
| **Result** | One-item resmoke hybrid/vector **1.0**. |
| **Artifacts** | `benchmarks/results/hop2_msft_cloud_and_geo_risk_resmoke.json` |

### D7. NVDA automotive / DRIVE (§21)

| | |
|--|--|
| **Problem** | NVDA missing on this PC; hop2 mean **0.42**, hop1 automotive weak. |
| **Fix** | Full NVDA grow (~$5.57; raise `MAX_EXTRACTION_BUDGET_USD` above default $5). |
| **Result** | `hop1_nvda_automotive` hybrid/vector **1.0**; `hop2_nvda_auto_competitors_risks` hybrid **1.0** / vector **0.71**. |
| **Artifacts** | `benchmarks/results/nvda_drive_resmoke.json` |

### D8. Docs / publish hygiene (partial)

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
| **Status** | **DONE** (code + verify 2026-11-06). See §18 / D3. |

### P2. Named product / brand misses (pack or window)

Same pattern as Meta: graph laundry list or wrong window hides the brand name.

| Item | Three-run hybrid mean | Status |
|------|----------------------:|--------|
| `hop1_msft_products` | 0.13 | **DONE** hybrid resmoke **1.0** (§19). Vector still 0.125. |
| `hop0_meta_ai_glasses` | 0.50 | **DONE** hybrid/vector resmoke **1.0** (§20). |
| `hop2_msft_cloud_and_geo_risk` | (was 0.50 on earlier hybrid file) | **DONE** resmoke hybrid/vector **1.0** (MSFT grow only). |
| `hop2_nvda_auto_competitors_risks` | 0.42 | **DONE** hybrid **1.0** / vector **0.71** after NVDA grow (§21). |
| `hop1_nvda_automotive` | (was 0.50 on earlier hybrid file) | **DONE** hybrid/vector **1.0** (§21). |

| | |
|--|--|
| **Likely work** | Prefer VECTOR (or named-needle windows) when the question names a product brand; stop unmatched `PRODUCES_PRODUCT` from crowding the pack. |
| **Verify** | Targeted resmokes per item after each change. |
| **Est. cost** | ~$0.10–0.25 per item × both modes (+ NVDA grow ~$1–2). |

### P3. Remaining soft misses (lower priority)

| Item | Mean | Notes |
|------|-----:|-------|
| `hop2_jpm_credit_vs_market` | 0.63 | **DONE** resmoke hybrid/vector **1.0** after JPM grow. |
| `hop1_aapl_products` | 0.83 | Restored; resmoke **1.0** (judge flake was historical). |
| `hop1_meta_apps` | 0.83 | Restored; resmoke **1.0**. |
| `hop1_nflx_aws_relationship` | (0.50 on earlier file) | **DONE** hybrid/vector **1.0** (§22). |

### P4. This-PC corpus restore

| | |
|--|--|
| **Why** | Full retrieve rebuild and honest full rebench need all 10 tickers. This PC had AAPL/JOBY/WDC (+ META embedded for the Meta work). |
| **Status** | **DONE** — all 10 suite issuers local: AAPL AMZN GOOGL JNJ JPM META MSFT NFLX NVDA XOM. |
| **Progress** | Restored after Docker wipe: AAPL/META/JPM + AMZN/GOOGL/JNJ/XOM. Spot checks: META/AAPL/JPM/NFLX **1.0**; `hop1_googl_waymo` hybrid **0.5** / vector **0.125** (named Waymo but thin ride-hailing detail — open polish). |

### P5. Full retrieve rebuild (`retrieval_v4`)

| | |
|--|--|
| **Status** | **DONE** 2026-11-06. |
| **Result** | Hybrid **0.84 / 0.91 / 0.70** (was 0.83 / 0.92 / 0.64). Vector **0.84 / 0.94 / 0.70** (was 0.82 / 0.93 / 0.67). Ties vector on @5 and MRR; vector still leads @10. |
| **Artifacts** | `benchmarks/results/retrieval_v4.json` · `retrieval_v4.md` |

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

1. **P6** one full temperature-0 generation rebench — only when you say so (~$0.80–1.00).  
2. Optional polish first: `hop1_googl_waymo` pack/window (hybrid 0.5).  

**Last updated:** 2026-11-06 (P5 retrieval_v4 rebuilt)
