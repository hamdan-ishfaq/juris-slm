# Decisions

## D-001: LLM takes the GPU, embedding and reranking run on the CPU
**Date:** 2026-11-06 · **Status:** Accepted

**Context:** The target machine has a 6 GB GPU (RTX 4050) and 16 GB of RAM, 12 GB of it given to WSL. The LLM
must run fully on the GPU. Ollama's automatic split put 11% of Mistral-7B on the CPU, and the API and worker
held 5,054 MiB of GPU memory between them for bge-m3 and the reranker.

| Option | Good | Bad | Effort |
|---|---|---|---|
| LLM on GPU, embed and rerank on CPU | Mistral at 38 tokens/s; about 0.5 s added per question | Bulk ingest about 0.5 s per chunk; 2.2 GiB RAM per process | Small |
| Embed and rerank on GPU, smaller LLM | Fast ingest and search | About 1 GB of GPU memory left for an LLM | Medium |
| Swap models per stage | Every stage on GPU | A model reload on each question (a Mistral load took 2.3-13 s) | Large |

Measured with Mistral-7B q4_K_M, `num_ctx` 4096, and a 1,820-token prompt:

| Setting | GPU share | GPU memory | Generation |
|---|---|---|---|
| Ollama automatic | 89% | 4,127 MiB | 19.8 tokens/s |
| `num_gpu` 99 | 100% | 4,837 MiB | 38.1 tokens/s |

On the CPU, bge-m3 took 88 ms per query at best and the reranker 385 ms for 20 pairs.

**Decision:** Run the LLM with `num_gpu` 99 on the GPU, and embedding and reranking on the CPU. Ollama keeps one
model loaded at a time (`OLLAMA_MAX_LOADED_MODELS=1`).

**Why:** Generation is by far the slowest stage, and full offload doubled its speed. The CPU stages add under a
second per question.

**Why not the others:** Nothing useful fits in the 1 GB left beside embed and rerank. Swapping costs more time
per question than it saves.

**Consequences:** Forcing `num_gpu` skips Ollama's safety estimate, so nothing else can hold GPU memory while
the LLM runs. `make check-llm-gpu` fails if any of the LLM is off the GPU. Bulk ingest and benchmarks with no LLM
loaded can use `docker-compose.gpu.yml`, which must not stay up beside the LLM. The API and worker need about
5 GB of RAM together.

**Revisit if:** The model comparison picks a model that leaves room for embedding on the GPU, or the target GPU
has more memory.
