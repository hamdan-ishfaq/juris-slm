# Retrieval, second round, 2026-11-12 to 2026-11-13

One change came out of this round: when the filename rule finds no document, the pipeline searches the three documents
whose descriptions are nearest the question (D-015). The chunker stays as it was. Harnesses: `eval/legalbench/round2.py`
and `eval/legalbench/chunking.py`. 95% bootstrap intervals; paired differences are per query. Product code `7b97789`.

## Final score

**1,209 CUAD queries that no earlier run used**, on documents from the held-out scoring half, searching all 714 documents.
The set was fixed and committed (`round2_sets.json`) before any tuning, and scored once (`fresh_score.json`,
`fresh_no_name.json`). These documents were scored once before, in the held-out final set, with only totals read.

| Method | Recall@8 | Precision@8 | Pipeline's paired gain |
|---|---|---|---|
| **Pipeline** | **48.5% [46.0, 51.0]** | 6.1% | |
| Pipeline before D-015 | 35.0% [32.7, 37.5] | 5.1% | +13.5 [+11.2, +15.5] |
| Vector search, document names embedded | 35.3% [33.1, 37.8] | 5.2% | +13.2 [+10.7, +15.4] |
| Plain vector search | 24.9% [22.6, 27.1] | 3.6% | +23.6 [+20.9, +26.3] |
| BM25 | 6.2% [4.9, 7.5] | 0.9% | +42.3 [+39.6, +44.7] |
| *Document chosen by the user, asked without its name* | *73.1% [71.0, 75.1]* | 9.8% | |
| *Asked without the name, across all documents* | *0.8% [0.4, 1.3]* | 0.1% | |

- The pipeline finds 1.9 times as much of the gold text as plain vector search, on documents and queries it was never
  tuned on. Before this round, the CUAD part of the held-out set was 38.4%.
- The last two rows say the result rests on the question naming its document. Without a name there's nothing to find among
  714 contracts; with the document picked in the interface, recall is higher than with a name.
- This is CUAD only, because no unused ContractNLI or MAUD queries were left (below).

**ContractNLI and MAUD, the held-out final set scored a second time** (635 queries, `final_score.json`), so not a clean
score:

| Method | Recall@8 | ContractNLI | MAUD | Pipeline's paired gain |
|---|---|---|---|---|
| **Pipeline** | **40.0% [36.7, 43.4]** | 84.0 | 28.1 | |
| Pipeline before D-015 | 39.6% | 83.3 | 27.8 | +0.4 [-0.8, +1.6] |
| Vector search, document names embedded | 35.1% | 72.4 | 25.1 | +4.8 [+2.7, +7.1] |
| Plain vector search | 7.8% | 18.7 | 4.9 | +32.1 [+28.8, +35.7] |
| BM25 | 2.0% | 8.6 | 0.3 | +37.9 [+34.6, +41.3] |
| *Document chosen, no name* | *43.0%* | 89.9 | 30.4 | |

D-015 changes nothing here, as expected: the filename rule already routed these. MAUD stays weak even with the document
given (30.4%), so its loss is within the document.

**Mini test split, scored a third time** (587 queries, 72 documents, `mini_test_third.json`): pipeline 60.9% [57.4, 64.2],
vector search with names 50.5%, BM25 11.1%. By sub-dataset: privacy policies 67.6, ContractNLI 83.4, MAUD 35.1, CUAD 58.8.
The first two scorings, at Phase 0 and Phase 4, were 25.3% and 32.8%. It was scored twice before and the design was
informed by its dev half, so it's shown for comparison with the benchmark's mini set, not as a clean score.

# Tuning, for the record

Nothing from here down is a clean score: the held-out tuning half (648 queries, 714 documents searched) and the mini dev
split (189 queries, 72 documents) were both tuned on.

## What's left to score cleanly

| Set | Status |
|---|---|
| Mini dev | Tuned on |
| Mini test | Scored twice, totals only |
| Held-out first sample, 1,500 queries | Routing errors read |
| Held-out tuning half, 648 queries | Tuned on |
| Held-out final set, 1,135 queries | Scored once, routing error totals read |
| **Unused CUAD queries on the final-half documents** | **1,209, never run: the `fresh` set** |

ContractNLI has no unused held-out queries and MAUD has 4, so the clean score covers CUAD only. ContractNLI and MAUD will be
scored a second time on the final set and labelled as such.

## Without the document's name

Every query has the form "Consider <document>; <question>". Removing the first clause leaves questions such as "Is there an
anti-assignment clause in this contract?", asked across 714 documents. Tuning half, Recall@8:

| Method | With the name | Without it |
|---|---|---|
| BM25 | 3.4% | 0.5% |
| Vector search, document names embedded | 43.2% | 1.7% |
| Pipeline | 46.4% [43.2, 49.9] | 1.7% [0.9, 2.6] |
| **Pipeline, document chosen by the user, asked without the name** | | **59.8% [56.6, 63.3]** |

Without the name these questions have no right answer to find among 714 contracts, so the near-zero row says the result
depends on naming the document, not that retrieval is broken. A user who doesn't name a document picks one in the
interface, which is the last row.

Choosing the document splits the loss by sub-dataset: CUAD 40.5% → 76.4%, ContractNLI 81.9% → 80.8%, MAUD 31.4% → 30.8%.
CUAD loses at finding the document, MAUD within the document.

## Choosing documents to search

The pipeline routes a question to one document when its capitalised words match a filename (D-007), merging that
document's results with a global search. Alternative: describe each document by its filename and first and last paragraphs,
embedded, and search the documents nearest to the question's naming clause.

| Variant, tuning half | Recall@8 | ContractNLI | MAUD | CUAD | Paired vs current |
|---|---|---|---|---|---|
| Current rule | 46.4% | 81.9 | 31.4 | 40.5 | |
| Nearest 3 for every question, weights 4,2,1 | 46.7% | 75.8 | 26.1 | 50.1 | +0.3 [-2.8, +3.2] |
| Rule first, nearest 3 otherwise, 4,2,1 | 49.2% | 79.7 | 30.6 | 49.8 | +2.8 [+0.1, +5.4] |
| Rule first, nearest 3 otherwise, 4 (one document) | 49.2% | 79.7 | 30.6 | 49.8 | identical to 4,2,1 |
| Rule first, nearest 3 otherwise, 2,1,1 | 50.9% | 80.5 | 31.5 | 52.7 | |
| **Rule first, nearest 3 otherwise, 1,1,1** | **51.3% [48.2, 54.7]** | 80.8 | 31.2 | 53.8 | **+4.8 [+2.5, +7.0]** |
| Same, as built into the product (`tune_d015.json`) | 51.3% | 80.8 | 31.2 | 53.8 | identical to the experiment |

- Searching the nearest documents for every question helped CUAD and hurt the others, where the rule was already right
  (110 of 110 ContractNLI and 181 of 181 MAUD rule routes correct).
- Weights 4 and 4,2,1 scored identically because, with reciprocal rank fusion over 20 results, a list weighted 4 scores
  at least 4/80 = 0.05 at every rank, above anything a list weighted 1 can reach (1/61). The first document's results fill
  all 20 places. The same holds for the current rule's 4:1 merge, so D-005's "a wrong guess can't hide everything else"
  is wrong when the routed document has 20 or more chunks.
- Questions with the name removed, asked across all documents, were pulled towards three unrelated documents:
  1.7% → 0.4%, paired -1.3 [-2.3, -0.5]. Only searching nearest documents when the question has a clause before its first
  ";", ":" or "?" removes that: 1,1,1 gated, without names, paired +0.0 [+0.0, +0.0]. A gate on capitalised words was tried
  first and let through every ContractNLI and MAUD question without its name, because defined terms are capitalised.
- 1,1,1 and 2,1,1 differ by +0.4 [-0.8, +1.6]; weights weren't tuned further.

## Chunk size and overlap

Mini dev, all 72 documents searched. Recall@8 counts chunks, so it rewards larger chunks with more text; the comparison
that matters is recall within the same 4,800 characters, about what eight current chunks hold.

| Chunker | Chunks | Pipeline R@8 | Pipeline recall at 4,800 chars | Vector, 4,800 chars |
|---|---|---|---|---|
| **Current (600, cut mid-word)** | 19,393 | 65.1% | **66.7% [61.0, 72.0]** | 60.9% |
| 600, cut at a space | 19,491 | 63.1% | 65.4% | 58.9% |
| 400 | 26,060 | 56.4% | 65.2% | 60.4% |
| 900 | 15,395 | 72.5% | 66.8% | 58.1% |
| 600, 150 overlap | 22,421 | 62.8% | 64.7% | 58.5% |
| 300 | 32,684 | 47.1% | 62.8% | 57.4% |

No setting beats the current chunker on the same amount of text, so it stays. The current chunker re-ingested from scratch
gave identical results, so the database's age plays no part.

## Mistakes found on the way, kept

- **Double-counted overlap.** The benchmark's scorer sums each retrieved span's overlap with the gold text, assuming retrieved
  spans don't overlap. With overlapping chunks, 60 of 189 queries scored recall above 1.0 (up to 1.93), and the overlap
  variant first read 79.5% at the budget. The harness now scores the union of spans (`7614d07`). Published held-out scores
  are unchanged by this: pipeline 39.08%, vector search with names 36.78%, BM25 3.79%, plain vector 16.7%.
- **Wrong documents searched.** The first sweep searched only the 17 dev documents rather than all 72, and scored about 3
  points high; a GPU-versus-CPU explanation was considered and ruled out, since exact search reproduced the earlier run on
  all 18 queries checked. Fixed in `a5fba01`; the wrong runs are in `chunking_mini_dev_wrong_documents.json`.
- **Name removal.** The product's own rule for separating name from question left names in 14 of 648 tuning queries, so the
  no-name variant uses the benchmark's template instead.
