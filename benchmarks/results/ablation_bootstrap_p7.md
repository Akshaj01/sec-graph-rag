# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `3-run item means`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only.

Per-item scores are the mean across 3 runs (multi_company_smoke_temp0_p7.json, multi_company_smoke_temp0_p7_run2.json, multi_company_smoke_temp0_p7_run3.json), then paired bootstrap.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.957 | 0.903 – 1.000 | 0.943 | 0.878 – 0.992 | 0.014 | -0.059 – 0.093 |
| hop_0 | 8 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |
| hop_1 | 16 | 0.914 | 0.781 – 1.000 | 0.865 | 0.690 – 0.990 | 0.049 | -0.138 – 0.255 |
| hop_2 | 8 | 0.938 | 0.812 – 1.000 | 0.958 | 0.896 – 1.000 | -0.021 | -0.167 – 0.083 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Reading:** Overall gap 0.014 (95% CI -0.059 – 0.093); hop-2 gap -0.021 (95% CI -0.167 – 0.083). The overall interval includes zero (or below), so the suite-wide lead is not stable. Hop-2's interval also includes zero or below.
