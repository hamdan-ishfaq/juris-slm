# JurisGuard V2 — Architecture

## Profiles

| Profile | `LLM_PROVIDER` | Generation (T2) | Aux (T1) | External calls |
|---------|----------------|-----------------|----------|----------------|
| **dev** | `openrouter` | phi-4-mini via OpenRouter | Ollama `qwen2.5:0.5b` | OpenRouter only |
| **airgap** | `ollama` | `phi3.5:mini` | Ollama aux | **None** |

Flip profiles by changing `.env` — no code changes.

## Model tiers

```
T0  bge-m3 + reranker + Postgres hybrid FTS  (always local)
T1  Ollama aux — HyDE, decompose, graph extract, contextual prep
T2  Generation — RAG answers, analyze, compare synthesis
T3  Extractive fallback — no LLM when T2 fails
```

## RAG pipeline

1. Query guard (L2 regex + L3 sentinel)
2. Redis cache (law Q&A)
3. Embed (+ optional HyDE on T1)
4. Hybrid retrieve + rerank
5. DLG context (law) / graph context (documents)
6. T2 generate → extractive fallback if needed
7. Citation verify

## Graph strategy

- **Contract graph:** LLM extraction on T1 aux during ingest (`GRAPH_EXTRACTION_ENABLED`)
- **Law graph (DLG):** Deterministic article edges — `POST /api/v1/corpus/dlg/bootstrap`

## Enterprise swap

```env
OPENROUTER_MODEL=anthropic/claude-sonnet   # or any OpenRouter model
OLLAMA_AUX_MODEL=llama3.2:3b
EMBEDDING_MODEL_PATH=/path/to/jina-v3
```

Same eval harness (`make eval-logical`) validates regressions.

## Optional integrations

- **OIDC:** `OIDC_ENABLED=true` + Keycloak issuer URLs
- **Langfuse:** `TRACING_ENABLED=true` + `LANGFUSE_*` keys
- **Fine-tune slot:** Colab QLoRA → GGUF → Ollama tag `jurisguard-v1`

## Commands

```bash
make up && make migrate
make test-unit
make eval-full-local    # offline + API eval when LLM available
make airgap-bundle      # offline deploy tarball
cd frontend && npm install && npm run dev
```
