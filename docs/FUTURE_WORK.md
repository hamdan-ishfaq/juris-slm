# Future work

The project is closed as of 2026-11-14: phases 0 to 11 are merged and every number in the README comes from a saved
report. This file is the plan for picking it up again. Nothing here has been started or measured; times are estimates.

Rules carried over from the earlier phases: pre-register before writing code, tune on dev only, score the held-out set
once, keep failed runs, and publish the result either way.

## 1. Check that answers are supported by their sources (Phase 11b)

**The gap.** The answer check confirms that cited articles appear in the sources and that the answer is on their topic. It
doesn't check that the sources support what the answer says: it passes 99.1% of ContractNLI claims the contract
contradicts (D-014). Phase 11 tested four ways to flag such claims, and none met the pre-registered rule (D-019,
`eval/reports/nli_flags_2026-11/`).

**What Phase 11 left open:**

| Option | False flags on supported | Contradictions caught | Time per claim | Why it failed |
|---|---|---|---|---|
| MiniLM, each span | 10.5% [7.0, 15.5] | 45.5% | 53 ms | Upper bound 0.5 points over 15%, on 200 supported pairs |
| Qwen3 8B as judge | 33.5% | 95.5% | 0.53 s | A fixed verdict, with no threshold to set |

### Options, in the order to try them

**A. Calibrated Qwen3 judge (first choice).** Read the probability Qwen3 gives to "supported" and set a threshold on dev
for 10% false flags, as for the NLI models. It caught 95.5% of contradictions with its own verdict, so it has the most
room to gain.
- Checked 2026-11-14: Ollama 0.40.15 returns `logprobs` and `top_logprobs` on `/api/chat`, so no new dependency is needed.
- Risk: in that check the top token had probability 0.9999999, and probabilities this close to 0 or 1 leave little room
  for a threshold. Mitigations to pre-register: ask for a 1-5 support score and take the probability-weighted mean, or
  compare the log-odds of "supported" against the other two verdicts.
- Time budget: 0.53 s per claim is about 2.1 s for a four-claim answer, just over the 2 s p50 budget. Judge all of an
  answer's claims in one call and read one verdict per claim.

**B. MiniLM on a larger held-out set (fallback).** This needs no new code: run `eval/nli/flags.py` on a larger sample. It
probably passes, but it catches only about 45% of contradictions, so it is the weaker flag.

**C. Fine-tune a small NLI model on ContractNLI (only if A and B fail).** It fits the 6 GB GPU, but it trains on the
data the test comes from: training documents must be kept out of the held-out set, and the resulting number then holds
for contracts like ContractNLI's NDAs, not for German law.

### Held-out data

ContractNLI train has 7,191 pairs. Phase 11 used 600 of them, which leaves 3,330 supported, 641 contradicted and 2,620
not-mentioned pairs. A new held-out set of 600 per label (all 641 contradicted pairs would nearly be used up) narrows the
false-flag interval to about ±2.4 points at 10%. These pairs come from documents Phase 11 already scored, so label them
"unseen pairs, previously seen documents". ContractNLI dev stays the tuning set.

### Adoption rule (same as Phase 11, unchanged)

- False flags on supported claims: upper 95% bound at most 15%.
- Contradictions flagged: at least 30%, with the lower bound above the false-flag rate.
- Time to flags after the answer: p50 at most 2 s, p95 at most 4 s.
- At most 1.2 GB extra RAM; the LLM stays 100% on the GPU.

If an option passes, show its flag in the UI as "may not be supported by the sources" next to the claim, not as a
verdict. Then label 50 claims from real answers by hand to check that it transfers. A person does this, not a model,
because grading model output with a model is the circular check this project avoids.

**Estimate:** one to two days, mostly unattended GPU time.

## 2. Sessions with real users

Three to five sessions with law students or lawyers on public contracts (CUAD or ContractNLI documents, never client
material). Each session: two research questions and one gap report, thinking aloud, with notes on where they hesitated,
what they trusted and what they checked by hand. Write them up as sessions, without percentages: five people can't give
a rate.

## 3. Law-trained models

Test open, Ollama-runnable law fine-tunes (for example SaulLM-7B) against Qwen3 8B with the D-010 harness: the same dev
questions, quote accuracy, schema-valid JSON rate, German handling, and 100% GPU placement on 6 GB. The candidates found
so far use older base models, cover US or other non-EU law, or publish no benchmarks, so they're unlikely to win. The
estimate is about an hour of GPU time per model.

## 4. Known defects worth fixing first

From the README's defect table, ordered by cost against effect:

| Defect | Next step |
|---|---|
| A bare article number takes the law of the best retrieved chunk | Ask which law when the question names none and the top chunks disagree |
| Graph extraction swaps the LLM out (25-100 s reload) | Queue extraction for idle time, or run it on the CPU |
| Gap analysis over-reports missing clauses | Raise the evidence bar per clause for exclusivity, anti-assignment and cap on liability, tuned on the CUAD dev contracts |
| Finding the document depends on the question naming it | Route on document descriptions first (D-015 already embeds them), and measure on the no-name set |
| No retrieval-based refusal for German questions | Calibrate a German refusal threshold on GerDaLIR dev |

## Not planned

Fine-tuning the generator, Kubernetes, voice, Neo4j, and an LLM-extracted law graph: each is out of scope for a
single-developer project on one 6 GB laptop GPU.
