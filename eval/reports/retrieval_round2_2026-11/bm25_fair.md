# A fair BM25 baseline, 2026-11-14

An outside review asked whether the BM25 baseline was tuned. It wasn't: `bm25s` defaults (k1 1.5, b 0.75), English
stopwords, no stemming, and chunks indexed without their document's name, while the vector-search rows embed the name.

## What changed

- English Snowball stemming (PyStemmer) on chunks and queries.
- k1 and b chosen on the round-2 tune set only (648 queries, 714 documents), from k1 in {0.9, 1.2, 1.5, 2.0} and b in
  {0.3, 0.5, 0.75, 0.9} (`bm25_tune.json`): without names k1 2.0, b 0.3 (4.9% on tune); with names k1 0.9, b 0.3 (20.9%).
- A `bm25_names` row: each chunk indexed with the product's document-name prefix (`build_embedding_text`), the BM25
  counterpart of vector search with names. Each BM25 row now differs from its vector row only in the retriever.
- The old setup reproduces the published mini dev figure exactly (8.8% Recall@8), so the change alone moved nothing.

## Fresh set, 1,209 unused CUAD queries, scored once with the new settings

| Method | Recall@8 | Pipeline's paired gain |
|---|---|---|
| Pipeline | 48.5% [46.0, 51.0] | |
| Vector search, names embedded | 35.3% [33.1, 37.8] | +13.2 [+10.7, +15.4] |
| Plain vector search | 24.9% [22.6, 27.1] | +23.6 [+20.9, +26.3] |
| BM25, names indexed | 13.8% [12.1, 15.6] | +34.7 [+32.1, +37.5] |
| BM25 | 9.4% [7.8, 10.9] | +39.1 [+36.3, +41.7] |
| BM25 as first published | 6.2% [4.9, 7.5] | +42.3 [+39.6, +44.7] |

The vector and pipeline rows are the same runs as `fresh_score.json`, re-aggregated, not re-run.

## Mini dev (189 queries, 72 documents; tuned on before)

| Method | Recall@8 | Recall@64 |
|---|---|---|
| BM25 as first published | 8.8% | 34.1% |
| BM25 | 11.8% | 36.5% |
| BM25, names indexed | 23.9% | 64.8% |
| Dense, for comparison | 57.8% | 88.6% |

## What it means

- The first baseline understated BM25 by about half (6.2% against 9.4%). Every "against BM25" gain was too large, by 3 to 8
  points. The comparisons with vector search didn't use BM25 and are unchanged.
- Names help BM25 as they help vector search (9.4% to 13.8% here; 11.8% to 23.9% on mini dev). The benchmark's queries
  all name their document, so it rewards whatever method uses the name.
- Vector search still beats a tuned BM25 by a wide margin with or without names, on templated questions whose wording
  is shared across hundreds of contracts.
- The other BM25 figures in the round-2 and held-out reports stay as first published, untuned; they aren't re-scored,
  since those sets were already scored more than once.
