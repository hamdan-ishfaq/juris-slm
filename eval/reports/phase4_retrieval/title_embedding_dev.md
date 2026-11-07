Split: dev (n=189); run: title_exp
Commit: 24741e9; date: 2026-11-07; hardware: x86_64, NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB
Embeddings: bge-m3; reranker: ms-marco cross-encoder (data/models/reranker)

| Mode | R@1 | R@2 | R@4 | R@8 | R@16 | R@32 | R@64 | P@1 | P@8 | P@64 |
|---|---|---|---|---|---|---|---|---|---|---|
| dense | 18.0 | 28.0 | 40.1 | 57.8 | 72.0 | 82.1 | 88.6 | 18.6 | 9.2 | 2.1 |
| product | 25.2 | 36.4 | 50.0 | 66.2 | 80.6 | 82.6 | 82.6 | 25.1 | 11.0 | 5.9 |
