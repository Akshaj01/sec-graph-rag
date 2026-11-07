# Hybrid improve plan

**Status:** **DONE** (2026-11-06) — honest three-run publish  
**Goal:** Make hybrid generation beat, or at least match, vector-only on the published 44-question suite — without lying about numbers.

| | |
|--|--|
| **Headline (three-run mean)** | Hybrid **0.93** (0.901–0.940) vs vector **0.90** (0.874–0.920); gap **+0.028** |
| **Bootstrap (pooled item means)** | Overall gap CI **−0.006 – 0.067** (includes zero). Hop-2 gap **+0.116**, CI **0.024 – 0.220** (above zero). |
| **Lead finding** | Graph helps on multi-relation / hop-2 asks (**1.00** vs **0.88**). Suite-wide lead is not stable. |
| **Retrieval (`retrieval_v4`)** | Hybrid recall@5 **0.84** / @10 **0.91** / MRR **0.70** · Vector **0.84 / 0.94 / 0.70** |
| **Living failure log** | [`PROBLEMS_AND_FIXES.md`](PROBLEMS_AND_FIXES.md) |
| **Published tables** | README · `three_run_means.md` · `ablation_bootstrap_three_run.md` · `retrieval_v4.md` |

Gateway (`GATEWAY_PLAN.md`) is a different track.

---

## Definition of done (met)

1. Targeted hybrid-improve fixes landed with logged resmokes.  
2. Full corpus on the publish machine.  
3. Three temperature-0 generation runs under `benchmarks/results/`.  
4. README leads with hop-2 + honest overall CI (not a single-run cherry-pick).

**Deferred:** new blind 30–40 item κ labeling (keep κ 0.84 with post-hoc caveat).

**Last updated:** 2026-11-06 (three-run mean + bootstrap published)
