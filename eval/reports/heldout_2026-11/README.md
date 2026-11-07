# Held-out evaluation, first score, 2026-11-07

LegalBench-RAG queries on documents outside the mini set used for tuning, searching all 714 documents and 182,914 chunks.
1,500 queries, seed 20261107, 500 each from ContractNLI, MAUD and CUAD, with the design committed before any result.
privacy_qa isn't covered, since all its documents are in the mini set. Scored by the benchmark's own code. The product code
is the frozen commit `25a0947`, and the harness commit is in `heldout.json`.

| Mode | Recall@8 | Precision@8 | ContractNLI | MAUD | CUAD |
|---|---|---|---|---|---|
| BM25 baseline | 4.5% [3.7, 5.5] | 0.5% | 7.8 | 0.4 | 5.4 |
| Vector, document name embedded | 46.9% [44.7, 49.2] | 6.2% | 81.8 | 25.4 | 33.5 |
| Pipeline with routing | 44.0% [41.9, 46.4] | 6.2% | 59.2 | 30.4 | 42.6 |

**The pipeline scored below vector search.** Routing that made no errors on 72 documents went wrong at 714: of 859 routed
queries, 169 went to the wrong document, 151 of them among the 256 routed ContractNLI queries, and 18 of 183 in CUAD.
MAUD had 420 routed and none wrong. The dev score of 66.2% overstated what this version achieves.

These queries name their document, which favours embedding the name, and they mix differently from the mini set, so
compare them with mini-set figures only with care.

`aborted_first_attempt.txt` is an earlier attempt, stopped when ingest failed at document 328 of 714. No score was
computed from it.

Having seen these routing errors, this sample can't be used for further tuning.
