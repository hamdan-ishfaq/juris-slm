# Held-out evaluation, 2026-11-07

LegalBench-RAG queries on documents that played no part in tuning, searching all 714 documents and 182,914 chunks. Scored by
the benchmark's own code. privacy_qa isn't covered, since all its documents are in the mini set used for tuning.

## Final score

1,135 queries from the half of the held-out documents kept out of tuning, with no query reused from the first attempt below.
The sample and split were committed before any tuning on them. Product code is commit `00fabca`. Details in `final.json` and
`final_comparison.json`.

| Method | Recall@8 | Precision@8 | ContractNLI (135) | MAUD (500) | CUAD (500) |
|---|---|---|---|---|---|
| BM25 baseline | 3.8% [2.8, 4.9] | 0.6% | 8.6 | 0.3 | 6.0 |
| Plain vector search | 16.7% [14.6, 18.8] | 2.3% | 18.7 | 4.9 | 28.0 |
| Vector search, document name embedded | 36.8% [34.2, 39.4] | 5.7% | 73.1 | 25.1 | 38.7 |
| **JurisGuard pipeline** | **39.1% [36.6, 41.6]** | **6.1%** | **83.3** | **27.8** | **38.4** |

Paired by query, Recall@8 of the pipeline minus plain vector search is +22.4 points [19.8, 24.9], and minus vector search with
document names is +2.3 points [1.2, 3.4].

**How to read this**

- Every query in this benchmark names its document, which is what these methods use. Questions that name no document get
  much less from them.
- Routing still sent 20 of 407 routed queries to the wrong document, 14 of them among the 39 routed in CUAD.
- The pipeline's candidate pool is 20, so its Recall@64 (52.3%) is below vector search's (66.7%).
- Recall alone can be bought with more text, so precision is reported beside it. It rose too.
- The mix differs from the mini set, with more MAUD and CUAD and no privacy policies, so don't compare it with mini figures.

## Earlier attempts, kept on purpose

**First score (`heldout.json`), 1,500 queries, frozen at `25a0947`.** Pipeline 44.0% [41.9, 46.4] against 46.9% [44.7, 49.2] for
vector search with document names, so the pipeline lost. Routing that made no errors on 72 documents sent 169 of 859 routed queries
to the wrong document among 714. Having read those errors, this sample couldn't be scored again.

**Tuning half (`tune.json`), 648 queries.** Used to fix routing at this scale: pipeline 46.4% [43.1, 50.0], vector search with
document names 43.2% [40.1, 46.8]. Not a clean score.

**Aborted run (`aborted_first_attempt.txt`).** Stopped when ingest failed at document 328 of 714 on a filename's encoding. No score
was computed from it.
