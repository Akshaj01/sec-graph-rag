# Ablation bootstrap — hybrid vs vector-only

Paired bootstrap on the judged generation scores in `multi_company_smoke_temp0_p6.json`. Each draw resamples questions with replacement and keeps a question's hybrid and vector-only scores together. The 95% interval is the middle 95% of 10000 draws (seed 0). The point estimate is the original mean. Gap is hybrid minus vector-only.

| Slice | n | Hybrid mean | Hybrid 95% CI | Vector mean | Vector 95% CI | Gap | Gap 95% CI |
|-------|--:|------------:|---------------|------------:|---------------|----:|------------|
| overall | 44 | 0.901 | 0.824 – 0.966 | 0.874 | 0.790 – 0.946 | 0.026 | -0.025 – 0.080 |
| hop_0 | 8 | 0.938 | 0.812 – 1.000 | 0.938 | 0.812 – 1.000 | 0.000 | 0.000 – 0.000 |
| hop_1 | 16 | 0.758 | 0.578 – 0.906 | 0.797 | 0.602 – 0.945 | -0.039 | -0.133 – 0.047 |
| hop_2 | 8 | 1.000 | 1.000 – 1.000 | 0.777 | 0.616 – 0.938 | 0.223 | 0.062 – 0.384 |
| oos | 12 | 1.000 | 1.000 – 1.000 | 1.000 | 1.000 – 1.000 | 0.000 | 0.000 – 0.000 |

**Reading:** Overall gap 0.026 (95% CI -0.025 – 0.080); hop-2 gap 0.223 (95% CI 0.062 – 0.384). The overall interval includes zero (or below), so the suite-wide lead is not stable. Hop-2 sits entirely above zero.
