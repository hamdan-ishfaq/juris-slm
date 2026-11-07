Split: dev (n=189); run: routed2
Commit: 4ef4b93; date: 2026-11-07; hardware: x86_64, NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB
Embeddings: bge-m3; reranker: ms-marco cross-encoder (data/models/reranker)

| Mode | R@1 | R@2 | R@4 | R@8 | R@16 | R@32 | R@64 | P@1 | P@8 | P@64 |
|---|---|---|---|---|---|---|---|---|---|---|
| dense | 9.1 | 13.7 | 22.9 | 32.6 | 46.1 | 56.8 | 65.3 | 8.6 | 5.0 | 1.6 |
| product | 18.7 | 28.3 | 41.5 | 60.0 | 75.1 | 77.9 | 77.9 | 20.9 | 9.7 | 5.7 |
