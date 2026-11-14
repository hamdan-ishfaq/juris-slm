# Build story

JurisGuard started as a feature-heavy prototype whose quoted results came from tests written for it. This is what was found
when each claim was checked against the code, what was changed, and what it measured. Every number has a report under
`eval/reports/`; failed attempts are kept there too.

## The starting point

- **The headline number didn't measure what it said.** "88.6% end-to-end" passed if the gold text was in the answer *or the
  sources*, so a correct retrieval with a wrong answer counted as a pass. The quoted 92.7% appeared in no report; the
  report said 91.8%. On a public benchmark (LegalBench-RAG) the pipeline scored 25.3% Recall@8 on the mini test set.
- **The keyword search was silently empty.** `plainto_tsquery` required every term, so it matched almost nothing and the
  "hybrid" search was vector search alone.
- **The context cap didn't work,** the "BM25" wasn't BM25, the gap-analysis "agent" made no model calls, the graph code
  matched "Article 6" anywhere in any law and never read the edges it stored, and tracing couldn't have sent a trace.
- **A latency figure that didn't reproduce.** The recorded 2.7 minutes an answer came out at 28.8 s p50 when rebuilt, with
  the benchmark forcing an extra HyDE call. Runs to the token cap were suspected and ruled out (10 of 10 stopped normally);
  the LLM was running 11% on the CPU.

## What changed, phase by phase

| Phase | Change | Measured |
|---|---|---|
| 0 | Rebuilt the stack; a LegalBench-RAG harness with the benchmark's own scorer | Pipeline 25.3% Recall@8, mini test |
| 1-2 | Moved to the repo root; removed SSO, SCIM, WORM, legal hold, clause library and deadlines | Tests and E2E unchanged |
| 3 | Scored retrieval and answers separately; `answer_mode`; a retrieval gate on every PR | A deliberately reversed ranking failed the gate |
| 4 | Keyword search only for cited provisions (D-002); document names in embeddings; routing (D-005, D-007) | 39.1% on 1,135 held-out queries, from 16.7% for plain vector search |
| 5 | Qwen3 8B chosen by measurement (D-010); `/api/chat`; streaming (D-009); the LLM alone on the GPU (D-001) | Better relevancy, quotes and German (D-010); answer time p50 8.5 s and p95 16.8 s on 50 questions, no faster than Mistral |
| 6 | Document text marked as data; citation check by law and article; offline proof; dependency upgrades | BIPIA attacks followed 0.8%, from 19.2%; 0 packets to public addresses |
| 6b | Search the documents whose descriptions are nearest the question when filenames don't match (D-015) | 48.5% on 1,209 unused CUAD queries, from 35.0% |
| 7 | A citation graph parsed by rules, replacing `dlg.py` (D-016) | Linked provision reached the model in 11 of 15 held-out questions, from 9 |
| 8 | A checklist review as the gap-analysis agent (D-017) | 83.5% of 1,000 CUAD decisions, against 56.7% for the rule-based tool |
| 9 | A read-only MCP server behind a hashed token (D-018) | Live check with the SDK's client |
| 10 | Erasure fixed, backup and erasure runbooks tested, these documents | Restore matched every table's row count |

## What broke on the way, and how it was caught

- **Routing that worked on 72 documents failed on 714.** The first held-out score (44.0%) lost to plain vector search with
  names (46.9%): ordinary words matched filenames. The fix was tuned on half the held-out documents and scored on the
  other half (D-007).
- **A reranker that hurt.** The English cross-encoder cut German ranking to a third of BM25's (GerDaLIR MRR@10 0.141 against
  0.345), so German questions keep retrieval order (D-006).
- **An answer check that passes contradictions.** On ContractNLI the relevance check passed 99.1% of claims the contract
  contradicts. An NLI gate would have turned about half the correct answers into quoted text, so it wasn't adopted, and
  the product doesn't claim answers are verified (D-014).
- **A scorer that counted twice.** With overlapping chunks, the benchmark's scorer summed each span's overlap, and 60 of
  189 queries scored recall above 1.0; overlap first looked like an 11-point gain. The harness now scores the union of
  spans; published scores didn't change.
- **A sweep that searched the wrong documents.** The chunk-size sweep searched 17 of 72 documents and read about 3 points
  high; exact search reproduced the earlier run and found it.
- **A speed-up that wasn't one.** The latency benchmark asked one question ten times, and two runs of the same model four
  minutes apart differed by 3 s, so "13.6 s to 9.1 s by changing the model" was noise. Run again with 50 different
  questions, alternating the models, Qwen3 was no faster than Mistral, and the tail was 16.8 s, not 9.2 s.
- **A baseline that was too weak.** An outside review asked whether BM25 was tuned. It wasn't: no stemming, library
  defaults, and no document names while the vector rows had them. Tuned on the tune set and scored once on the fresh set,
  it went from 6.2% to 9.4%, and 13.8% with names; every "against BM25" gain had been 3 to 8 points too large.
- **A graph that pushed out good chunks.** The first citation-graph attempt reached fewer cited provisions (16 of 20, from
  18): added chunks took the places of retrieved ones. Linked provisions now get their own room.
- **A UI race.** The graph view's matter list replaced a choice made while it loaded; the Playwright graph test failed
  twice before the cause was found.
- **Erasure that didn't erase.** Writing the erasure runbook against the code found that deleting a document left the
  uploaded file on disk, and that deleting any user who had used the product failed with a 500 on their audit events.
  Files are now removed, and users are anonymised and disabled while the hash-chained audit rows stay intact.
- **An installer with known flaws.** pip-audit of the image after adding the MCP SDK found the base image's pip 25.0.1,
  which the earlier audit hadn't covered; the images now upgrade it.

## What it still doesn't do

The README's "Known defects" table is the current list: finding a contract still depends on naming it, answers aren't
checked for support, the gap analysis over-reports missing clauses, and one document injection in 120 still worked.
