# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `multi_company_smoke_judged.json`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.938 | 0.869 – 0.992 | 0.886 | 0.793 – 0.963 | 0.052 | -0.026 – 0.136 |
| hop_0 | 8 | 0.938 | 0.812 – 1.000 | 0.922 | 0.797 – 1.000 | 0.016 | 0.000 – 0.047 |
| hop_1 | 16 | 0.883 | 0.711 – 1.000 | 0.789 | 0.586 – 0.945 | 0.094 | -0.117 – 0.305 |
| hop_2 | 8 | 0.958 | 0.875 – 1.000 | 0.875 | 0.625 – 1.000 | 0.083 | 0.000 – 0.250 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Recommendation:** Hybrid scores higher on average (0.052 overall, 0.083 on hop 2), and neither 95% interval sits entirely above zero, so the lead is not stable on this suite.
