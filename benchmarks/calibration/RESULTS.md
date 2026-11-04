# Calibration results (rubric v1)

Scores snap to 0 / 0.5 / 1. Midpoints 0.25 and 0.75 snap upward. Reported weight is linear: a one-step miss counts half of a 0-vs-1 miss. Rubric v1 was not edited after these labels.

The n=24 sheet `benchmarks/judge_calibration_hybrid.md` is history. It was used while reading disagreements. It is not the reported κ.

## Judge vs human (hold-out, n=20)

The first pass on 2026-11-02 scored every item **1.0**. Linear κ was **0.00** and raw agreement was 17/20. Two of those 1.0s contradicted the required facts and the failure table, so they were corrected on 2026-11-04. The numbers below are the corrected pass. Rubric v1 was not edited.

| | |
|--|--|
| Linear weighted κ | **0.84** |
| Quadratic weighted κ | 0.90 |
| Raw agreement | **0.95** (19/20) |
| Spearman | 0.82 |

Corrected labels:

- `hop1_meta_ai_competition` — 1.0 → **0**. Apple and Google show up as ad-tracking gatekeepers. The answer never names a platform or AI competitor. Judge snapped to 0 (raw 0.125).
- `hop0_meta_ai_glasses` — 1.0 → **0.5**. Reality Labs and Quest are covered. Ray-Ban Meta / Oakley Meta are not named. Judge was 0.5.

Remaining split (you / judge snapped):

- `hop2_nvda_auto_competitors_risks` — 1.0 / 0.5 (judge raw 0.6675)

## Self-agreement (n=15)

First pass on the debug sheet, second pass 2026-11-03. First-pass 0.375 snaps to 0.5 before κ.

| | |
|--|--|
| Linear weighted κ | **0.42** |
| Raw agreement | **0.87** (13/15) |
| Spearman | 0.42 |

Both passes are mostly 1.0, so two one-step flips move κ more than the raw rate suggests.

- `hop0_amzn_aws` — first 1.0, second 0.5. Second pass: the answer names the AWS segment and does not say cloud or technology services.
- `hop0_jpm_credit_risk` — first 0.5, second 1.0. Same answer. First pass wanted an explicit default/loss definition. Second pass accepted the obligor-default wording.
