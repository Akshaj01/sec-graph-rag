# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `multi_company_smoke_temp0_p6_run2.json`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.940 | 0.881 – 0.989 | 0.903 | 0.824 – 0.969 | 0.037 | -0.003 – 0.091 |
| hop_0 | 8 | 0.938 | 0.812 – 1.000 | 0.938 | 0.812 – 1.000 | 0.000 | 0.000 – 0.000 |
| hop_1 | 16 | 0.867 | 0.719 – 0.984 | 0.797 | 0.602 – 0.945 | 0.070 | -0.016 – 0.203 |
| hop_2 | 8 | 1.000 | 1.000 – 1.000 | 0.938 | 0.812 – 1.000 | 0.062 | 0.000 – 0.188 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Reading:** Overall gap 0.037 (95% CI -0.003 – 0.091); hop-2 gap 0.062 (95% CI 0.000 – 0.188). The overall interval includes zero (or below), so the suite-wide lead is not stable. Hop-2's interval also includes zero or below.
