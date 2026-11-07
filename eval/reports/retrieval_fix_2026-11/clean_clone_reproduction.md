# Clean-clone reproduction of the LegalBench dev table

A fresh clone on GitHub's CPU runner, workflow run 42321715869, commit `2acb437`, in 3h 27m. This is the code from before document routing, and only the workflow trigger differs from `192c2a2`. Recall@8 matches the local GPU run (`legalbench_dev.md`) on every mode. A few other cells of `product` and `fts` differ by up to 0.4 points, from CPU versus GPU embeddings.

| Mode | R@1 | R@2 | R@4 | R@8 | R@16 | R@32 | R@64 | P@1 | P@8 | P@64 |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0.9 | 3.4 | 5.4 | 8.8 | 13.9 | 21.6 | 34.1 | 0.7 | 1.1 | 0.8 |
| dense | 9.1 | 13.7 | 22.9 | 32.6 | 46.1 | 56.8 | 65.3 | 8.6 | 5.0 | 1.6 |
| dense_exact | 9.1 | 13.7 | 22.9 | 32.6 | 46.1 | 56.8 | 65.3 | 8.6 | 5.0 | 1.6 |
| fts | 1.4 | 2.1 | 3.6 | 7.2 | 10.6 | 16.8 | 26.4 | 1.1 | 0.9 | 0.5 |
| hybrid | 9.1 | 13.7 | 22.9 | 32.6 | 46.1 | 56.8 | 65.3 | 8.6 | 5.0 | 1.6 |
| hybrid_rerank | 3.0 | 7.9 | 12.8 | 18.6 | 29.3 | 42.8 | 65.3 | 4.2 | 2.9 | 1.6 |
| product | 9.5 | 14.0 | 22.9 | 32.6 | 46.0 | 50.2 | 50.2 | 9.0 | 5.0 | 3.6 |
