# Three-run generation means

Mean of per-run `mean_score` values (and hop buckets). Parentheses are min-max across runs.

| Run | Hybrid | Vector-only | Gap |
|-----|-------:|------------:|----:|
| multi_company_smoke_temp0_p6.json | 0.901 | 0.874 | 0.026 |
| multi_company_smoke_temp0_p6_run2.json | 0.940 | 0.903 | 0.037 |
| multi_company_smoke_temp0_p6_run3.json | 0.940 | 0.920 | 0.020 |

| | Hybrid | Vector-only | Gap |
|--|-------:|------------:|----:|
| **Mean of runs** | 0.927 (0.901-0.940) | 0.899 (0.874-0.920) | 0.028 |

| Hop / bucket | Hybrid mean | Vector mean | Gap |
|--------------|------------:|------------:|----:|
| Hop 0 | 0.938 | 0.938 | 0.000 |
| Hop 1 | 0.831 | 0.813 | 0.018 |
| Hop 2 | 1.000 | 0.884 | 0.116 |
| OOS | 1.000 | 1.000 | 0.000 |
