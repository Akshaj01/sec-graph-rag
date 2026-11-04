# Calibration results (rubric v1)

Scores snap to 0 / 0.5 / 1. Midpoints 0.25 and 0.75 snap upward. Reported weight is linear: a one-step miss counts half of a 0-vs-1 miss. Rubric v1 was not edited after these labels.

The n=24 sheet `benchmarks/judge_calibration_hybrid.md` is history. It was used while reading disagreements. It is not the reported κ.

## Judge vs human (hold-out, n=20)

Labeled 2026-11-02. Every human score was 1.0. The judge snapped to 0 on one item and 0.5 on two.

| | |
|--|--|
| Linear weighted κ | **0.00** |
| Quadratic weighted κ | 0.00 |
| Raw agreement | **0.85** (17/20) |
| Spearman | undefined (human side is constant) |

κ is 0 because one rater used a single category. The three misses are then exactly what chance predicts. Raw agreement is the number that says how often the scores matched.

Splits (you / judge snapped):

- `hop1_meta_ai_competition` — 1.0 / 0.0 (judge raw 0.125)
- `hop0_meta_ai_glasses` — 1.0 / 0.5
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
