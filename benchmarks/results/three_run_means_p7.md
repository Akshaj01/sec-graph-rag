# Three-run generation means

Mean of per-run `mean_score` values (and hop buckets). Parentheses are min-max across runs.

| Run | Hybrid | Vector-only | Gap |
|-----|-------:|------------:|----:|
| multi_company_smoke_temp0_p7.json | 0.957 | 0.935 | 0.023 |
| multi_company_smoke_temp0_p7_run2.json | 0.957 | 0.946 | 0.011 |
| multi_company_smoke_temp0_p7_run3.json | 0.957 | 0.949 | 0.009 |

| | Hybrid | Vector-only | Gap |
|--|-------:|------------:|----:|
| **Mean of runs** | 0.957 (0.957-0.957) | 0.943 (0.935-0.949) | 0.014 |

| Hop / bucket | Hybrid mean | Vector mean | Gap |
|--------------|------------:|------------:|----:|
| Hop 0 | 1.000 | 1.000 | 0.000 |
| Hop 1 | 0.914 | 0.865 | 0.050 |
| Hop 2 | 0.938 | 0.958 | -0.021 |
| OOS | 1.000 | 1.000 | 0.000 |
