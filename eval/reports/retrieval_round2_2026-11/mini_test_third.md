Split: test (n=587); run: round2_mini
Commit: 7b97789; date: 2026-11-13; hardware: x86_64, NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB
Embeddings: bge-m3; reranker: ms-marco cross-encoder (data/models/reranker)

| Mode | R@1 | R@2 | R@4 | R@8 | R@16 | R@32 | R@64 | P@1 | P@8 | P@64 |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 3.0 | 4.2 | 7.1 | 11.1 | 17.2 | 24.7 | 34.8 | 2.1 | 1.4 | 0.7 |
| dense | 18.7 | 26.5 | 38.6 | 50.5 | 63.8 | 77.2 | 85.2 | 17.3 | 7.6 | 2.0 |
| product | 25.1 | 36.2 | 48.4 | 60.9 | 70.5 | 74.1 | 74.1 | 24.5 | 9.0 | 4.7 |
