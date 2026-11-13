# Citation graph, 2026-11-13

A graph of which provision refers to which, read by rule from the four statutes, replaces `dlg.py` (D-016). When a
question cites a provision, the pipeline looks it up by law and article, and adds up to two provisions it cites or is cited
by, each with its own room after the retrieved context and its path shown in the sources. Product code `f956f43`.

## The graph

2,766 provisions and 3,620 references (BGB 2,797, AI Act 320, GDPR 318, BDSG 185), 80 of them across laws. On a hand-checked
sample of 32 chunks the parser's precision was 95.2% (40 of 42) and its recall 90.9% (40 of 44); details and the
development sample in `parser_check.md`.

## Does following citations help?

There is no public EU-law benchmark of questions that need a linked provision, so the project wrote its own: each question
cites one provision and its answer is in another the cited one links to, checked in the law text rather than in the graph
(`eval/golden/linked_provisions*.jsonl`). The measure is whether that provision reaches the model. These are the project's
own questions, not a benchmark result. Harness: `eval/law_graph/linked.py`.

| Set | Questions | Before (code `cbee59a`) | With the graph | Cited provision reaches the model |
|---|---|---|---|---|
| Development, read while designing | 20 | 12 | **15** | 18 → 20 |
| Held-out, written before the changes, scored once | 15 | 9 | **11** | 14 → 15 |

- No question the old pipeline answered from the right provision lost it.
- The held-out gains (2 of 15) are both links the cited provision makes itself (GDPR Art. 30 → Art. 9, BGB § 440 → § 281).
  Of the 7 held-out questions whose answer is in a provision that cites the asked one, none changed: the graph added
  other citing provisions instead.
- The held-out set was scored once at `36b08b7`. Taking one chunk per linked provision came after, from a demonstration
  question; the second scoring on the final code gives the same 11 (`linked_heldout_final.json`).
- 15 and 20 questions are few: read this as "it helps a few questions and costs nothing on these", not as a rate.

The first attempt is kept (`linked_dev_first_attempt.json`): 13 of 20, and the cited provision in context fell from 18 to 16.
Linked chunks took the places of retrieved ones beyond the context cap, and a question naming both the DSGVO and the BDSG
had its "§ 22" read as a GDPR article. Linked provisions now get their own room, and a law name has to fit the provision
word ("§" is BDSG or BGB, "Article" is GDPR or AI Act).

## A question it fixed

"Which kinds of data stop the small-organisation exemption from the records duty in GDPR Article 30 applying?" Before, the
special categories of Article 9 never reached the model. Now the sources include "GDPR Art. 30 → GDPR Art. 9", and the
answer names special categories under Article 9(1) and criminal-offence data under Article 10.

"What does Article 12 require?", which used to reach the AI Act and quote it, now answers from GDPR Article 12: with no law
named, the law of the best retrieved chunk decides. The answer doesn't say which law it read, so a question meant for the
AI Act would still be answered from the GDPR.

## Cost and regressions

- **Latency:** the graph step took 32.2 s over the 44 law-corpus questions that reached it in the regression suite, 0.73 s
  each on average on the CPU (`stage_metrics.txt`), mostly the reranker scoring every chunk of up to 12 linked provisions. Retrieval
  took 0.51 s a question, generation 4.9 s.
- **The project's 110-case EU suite:** 107 passed (`logical.json`; recent runs 106 to 108). The two long-standing misses
  remain, and gdpr-023 missed. Asked three times each, the answer wrote "Article 37" in 3 of 3 before the graph and
  "Art. 37" in 2 of 3 with it, the third naming neither; the suite accepts only "Art. 37", so this question moves with the
  model's wording.

## What it doesn't change

- Contract search: the graph runs only for questions on the law corpus, so LegalBench-RAG retrieval is untouched by
  construction.
- GraphRAG-Bench wasn't run: it is general text, and a parser for statutory citations has nothing to read there (D-016).
