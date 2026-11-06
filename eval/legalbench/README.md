# LegalBench-RAG harness

Measures JurisGuard retrieval on [LegalBench-RAG](https://github.com/zeroentropy-ai/legalbenchrag),
using character-span precision and recall computed by the benchmark's own `QAResult` class.

## What is pinned

| Item | Value |
|---|---|
| Scorer | `zeroentropy-ai/legalbenchrag` at commit `431bc8f2488a81569ab7259fa633dcc50ab77f9a` |
| Dataset archive | sha256 `27431be37db9b1db23f8ab790a42d076adb1f72d7f9e7562e36a10573405f88d` |
| Query set | Mini: 194 queries from each of 4 subsets (776 total, 72 documents). Selected the way the benchmark's `benchmark.py` does with `SORT_BY_DOCUMENT=True` |
| Split | `split.json`, seed 20261106, by document. 25% of each subset's documents are dev |

`data/` is not committed. `fetch` downloads it and checks the checksum.

## Rules

- Tune on dev only. A test score is produced once per milestone, and only aggregates are written.
- Keep failed runs.
- Results carry a bootstrap 95% interval over queries (1,000 resamples, fixed seed).

## What is adapted

- **Spans.** The product chunker records no offsets, so `ingest` locates each chunk in its source
  text and reports any it cannot place. Those chunks score nothing rather than being dropped from
  the denominator.
- **`parent_content`.** Left out of benchmark chunk metadata because it would add 2.5 GB of
  duplicate text. Ranking does not read it, so retrieval results are unaffected. Generation over
  this corpus is measured separately.
- **Query ids.** Two pairs of benchmark queries are exact duplicates and share an id. Each still
  counts in the score, as in the benchmark.

## Modes

| Mode | Meaning |
|---|---|
| `bm25` | Okapi BM25 from `bm25s` on the same chunks. External baseline, not product code |
| `fts` | Product keyword leg: `search_fts` on the expanded query |
| `dense` | Product `search_similar`, using the HNSW index |
| `dense_exact` | Same query with index scans off, to expose approximate-search loss |
| `hybrid` | Product `hybrid_search`, RRF of `fts` and `dense` |
| `hybrid_rerank` | `hybrid`, then the product reranker over the top 64 |
| `product` | `_retrieve_and_rank` with default settings, HyDE off, every reranked result kept. The pool is `rag_top_k`, so k above that cannot improve |

## Running

Product modes need the ML dependencies and GPU, so they run in the API container against a separate
`juris_bench` database. `bm25` and `score` run on the host.

```bash
make bench   # fetch, ingest once, run every mode, score dev; writes eval/reports/bench/

# The same steps by hand:
.venv/bin/python eval/legalbench/legalbench.py fetch
.venv/bin/python eval/legalbench/legalbench.py split   # only to regenerate split.json

BENCH="docker compose -f docker-compose.yml -f docker-compose.gpu.yml run --rm --no-deps \
  -e DATABASE_URL=postgresql+asyncpg://juris:juris_password@db:5432/juris_bench \
  -v $PWD/eval:/app/eval api"

docker compose exec db createdb -U juris juris_bench
$BENCH alembic upgrade head
$BENCH python eval/legalbench/legalbench.py ingest
$BENCH python eval/legalbench/legalbench.py run --run baseline

.venv/bin/python eval/legalbench/legalbench.py run --run baseline --modes bm25
.venv/bin/python eval/legalbench/legalbench.py score --run baseline --split dev \
  --output eval/reports/baseline_2026-11/legalbench_dev.json
```

`score` writes the JSON report and a Markdown table next to it, with the commit, split and scorer.
