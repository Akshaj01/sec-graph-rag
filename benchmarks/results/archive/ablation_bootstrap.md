# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `multi_company_smoke_judged.json`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only. `hop2_jpm_credit_vs_market` uses the full-run hybrid score 0.375, not the later one-item rerun of 1.0.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.924 | 0.851 – 0.981 | 0.886 | 0.793 – 0.963 | 0.038 | -0.047 – 0.126 |
| hop_0 | 8 | 0.938 | 0.812 – 1.000 | 0.922 | 0.797 – 1.000 | 0.016 | 0.000 – 0.047 |
| hop_1 | 16 | 0.883 | 0.711 – 1.000 | 0.789 | 0.586 – 0.945 | 0.094 | -0.117 – 0.305 |
| hop_2 | 8 | 0.880 | 0.719 – 1.000 | 0.875 | 0.625 – 1.000 | 0.005 | -0.234 – 0.250 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Recommendation:** Hybrid scores higher on average (0.038 overall, 0.005 on hop 2), and neither 95% interval sits entirely above zero, so the lead is not stable on this suite.
