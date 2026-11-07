# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `three-run item means (p6+run2+run3)`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only.

Per-item scores are the mean across the three temperature-0 runs (temp0_p6, run2, run3), then paired bootstrap.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.927 | 0.864 – 0.977 | 0.899 | 0.823 – 0.962 | 0.028 | -0.006 – 0.067 |
| hop_0 | 8 | 0.938 | 0.812 – 1.000 | 0.938 | 0.812 – 1.000 | 0.000 | 0.000 – 0.000 |
| hop_1 | 16 | 0.831 | 0.682 – 0.951 | 0.812 | 0.625 – 0.961 | 0.018 | -0.057 – 0.109 |
| hop_2 | 8 | 1.000 | 1.000 – 1.000 | 0.884 | 0.780 – 0.976 | 0.116 | 0.024 – 0.220 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Reading:** Overall gap 0.028 (95% CI -0.006 – 0.067); hop-2 gap 0.116 (95% CI 0.024 – 0.220). The overall interval includes zero (or below), so the suite-wide lead is not stable. Hop-2 sits entirely above zero.
