# Gap analysis on CUAD, 2026-11-13

The gap analysis used to match seven topic patterns in a contract's first 40 chunks, with no model call. It is now a
checklist review (D-017): for each clause type, the product's own search inside the contract, one model call held to a JSON
schema, and the quote checked against the retrieved text. Plan, split and measures were committed before any result
(`eval/gap_agent/README.md`). Model Qwen3 8B, 100% on the GPU; harness `eval/gap_agent/cuad.py`.

## Test set, scored once

100 CUAD contracts (CC BY 4.0) × 10 clause types = 1,000 decisions: does the contract have the clause? 95% bootstrap
intervals over contracts.

| Method | Accuracy | "Missing" precision | "Missing" recall | False alarms | Quote overlaps CUAD's answer | Calls / contract | s / contract |
|---|---|---|---|---|---|---|---|
| **Checklist review** | **83.5% [81.1, 86.1]** | 81.1% [77.3, 84.7] | 93.3% [91.2, 95.2] | **126** | **89.5%** | 10.1 | 21.5 |
| One call over the first 9,000 characters | 62.3% [57.8, 66.9] | 60.8% | 98.5% | 368 | 50.9% | 10.1 | 19.0 |
| Rule-based tool, as it was | 56.7% [52.9, 60.6] | 58.7% | 85.2% | 347 | 8.1% | 0 | 0.0 |
| Calling every clause missing | 57.9% [53.1, 62.6] | 57.9% | 100.0% | 421 | — | 0 | 0 |

A false alarm is a clause reported missing that the contract has. The old tool and the one-call baseline did no better than
reporting everything missing; the review is the only method well above it.

By clause type (accuracy, %):

| Clause | Review | One call | Rule-based | All missing |
|---|---|---|---|---|
| Governing Law | 95 | 26 | 12 | 12 |
| Anti-Assignment | 77 | 33 | 30 | 30 |
| Cap On Liability | 77 | 46 | 57 | 42 |
| Audit Rights | 90 | 59 | 54 | 54 |
| Termination For Convenience | 79 | 67 | 38 | 65 |
| Exclusivity | 69 | 79 | 68 | 68 |
| Insurance | 92 | 74 | 73 | 73 |
| Change Of Control | 83 | 82 | 82 | 82 |
| Non-Compete | 83 | 78 | 75 | 75 |
| Warranty Duration | 90 | 79 | 78 | 78 |

Per clause, for the review (re-aggregated on 2026-11-14 from the same saved predictions, no new model calls;
`cuad_test_per_clause.json`). "Share truly missing" is the precision of calling everything missing, the level a "missing"
must beat to mean anything:

| Clause | Accuracy | "Missing" precision | "Missing" recall | False alarms | Share truly missing |
|---|---|---|---|---|---|
| Governing Law | 95 | 77 | 83 | 3 | 12 |
| Anti-Assignment | 77 | 57 | 90 | 20 | 30 |
| Cap On Liability | 77 | 65 | 98 | 22 | 42 |
| Audit Rights | 90 | 87 | 96 | 8 | 54 |
| Termination For Convenience | 79 | 82 | 86 | 12 | 65 |
| Exclusivity | 69 | 69 | 99 | 30 | 68 |
| Insurance | 92 | 93 | 96 | 5 | 73 |
| Change Of Control | 83 | 92 | 87 | 6 | 82 |
| Non-Compete | 83 | 85 | 93 | 12 | 75 |
| Warranty Duration | 90 | 90 | 97 | 8 | 78 |

A "missing" for Exclusivity is right 69% of the time when 68% of contracts lack the clause, so it carries no information.
Anti-Assignment and Cap On Liability have the most false alarms after it. Change Of Control's accuracy only matches
guessing, but its "missing" is right 92% of the time against 82%.

- The opening of a contract rarely holds its governing law or assignment terms, which is where reading only the start
  fails.
- On Exclusivity the review is no better than calling it missing, and worse than one call; on Change Of Control it is level.
  These clauses are often worded indirectly ("sole supplier", "assignment by operation of law"), and the review searches
  with CUAD's definition rather than with such wording.
- The review calls clauses missing more often than CUAD does: 666 of 1,000 against CUAD's 579. Most of its errors are false
  alarms, so a "missing" in the report means "not found in the best five passages", and is worth a look by hand.
- 1 of 1,000 decisions ended "not verified" (a quote not found in the text) and none "not checked".

## Development set

40 contracts, used for prompt and retry changes (`cuad_dev.json`): first run 83.8%, after retrying failed calls and
asking for quotes under 300 characters 82.5%, the same within noise and faster (21.6 s against 32.6 s a contract). Two
development calls failed, one with a bare 500 from Ollama and one with JSON cut off mid-quote; both are now retried once,
and Ollama's error text is kept.

## How this was measured, and what it doesn't show

- Only the 462 CUAD contracts whose text is also a LegalBench-RAG document were eligible, since those were already
  ingested; 140 were drawn by seed. These documents were searched during earlier retrieval work, but never with these
  questions or labels.
- CUAD's own metric, precision at 80% recall over ranked spans, needs scored spans, which a yes-or-no decision with one
  quote doesn't give, so presence accuracy and quote overlap are used instead.
- CUAD is US commercial contracts. The product's data-protection item (whether processor terms meet GDPR Article 28) has
  no CUAD label and is unmeasured.
- Failure handling is covered by tests rather than this run: Ollama failing, a reply that isn't the schema, a quote never
  found, an empty document and the call budget running out (`backend/tests/test_contract_review.py`).
