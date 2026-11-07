Split: dev (n=189); run: routed
Commit: 192c2a2; date: 2026-11-07; hardware: x86_64, NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB
Embeddings: bge-m3; reranker: ms-marco cross-encoder (data/models/reranker)

| Mode | R@1 | R@2 | R@4 | R@8 | R@16 | R@32 | R@64 | P@1 | P@8 | P@64 |
|---|---|---|---|---|---|---|---|---|---|---|
| dense | 9.1 | 13.7 | 22.9 | 32.6 | 46.1 | 56.8 | 65.3 | 8.6 | 5.0 | 1.6 |
| product | 15.2 | 23.8 | 36.7 | 51.4 | 65.9 | 68.9 | 68.9 | 18.0 | 8.5 | 5.2 |
