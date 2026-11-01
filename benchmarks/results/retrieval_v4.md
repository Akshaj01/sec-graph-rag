# Retrieval metrics — multi_company_smoke v4

Macro-average over answerable items with gold_chunk_ids. Rank is first occurrence of a chunk id. Hybrid list is graph ids, then vector ids not already present. Vector depth is 10 so recall@10 can differ from recall@5. The answer model still caps the pack (graph facts 12, vector passages 5); this table is retrieve-only and does not apply that cap. OOS items are skipped.

Scored n=32. OOS skipped=12.

| Hop | n | System | Recall@5 | Recall@10 | MRR |
|-----|--:|--------|--------:|----------:|----:|
| hop_0 | 8 | graph | 0.44 | 0.44 | 0.31 |
| hop_0 | 8 | vector | 1.00 | 1.00 | 0.71 |
| hop_0 | 8 | hybrid | 1.00 | 1.00 | 0.61 |
| hop_1 | 16 | graph | 0.36 | 0.47 | 0.29 |
| hop_1 | 16 | vector | 0.73 | 0.85 | 0.59 |
| hop_1 | 16 | hybrid | 0.46 | 0.65 | 0.39 |
| hop_2 | 8 | graph | 0.50 | 0.67 | 0.57 |
| hop_2 | 8 | vector | 0.81 | 1.00 | 0.79 |
| hop_2 | 8 | hybrid | 0.75 | 0.92 | 0.62 |
| overall | 32 | graph | 0.42 | 0.51 | 0.37 |
| overall | 32 | vector | 0.82 | 0.93 | 0.67 |
| overall | 32 | hybrid | 0.67 | 0.80 | 0.51 |
