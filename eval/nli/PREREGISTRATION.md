# Flagging unsupported claims: what will be measured, fixed before any code (2026-11-14)

The answer check passes 99.1% of claims the contract contradicts (D-014). D-014 also tried mDeBERTa as a per-sentence
warning and rejected it: at its default decision it flagged 42.6% of supported claims. This phase asks one question: is
there a flag that fires rarely on supported claims and still catches a useful share of unsupported ones? If not, the
result is published and the current label ("support not checked") stays.

## What changes from D-014

D-014 used each model's default decision. Here the threshold is set from a false-flag budget, and the premise is varied:

| Option | Premise | Where it runs |
|---|---|---|
| mDeBERTa-v3-base (xnli, multilingual) | the 5 retrieved spans together, as in D-014 | CPU |
| mDeBERTa-v3-base | each span alone, take the highest entailment | CPU |
| multilingual MiniLM (L6) | each span alone | CPU |
| Qwen3 8B as judge, one JSON call per answer listing every claim | the retrieved spans | GPU, already loaded |

No fine-tuning, no new model download beyond these.

## Data

- **Tuning:** ContractNLI dev (its official split), as in D-014.
- **Held out, scored once:** a seeded sample of ContractNLI train (seed 20261114, 600 pairs, stratified by label). No run in
  this project has used train. The test split was scored once for D-014 and isn't reused for a new threshold.
- **Real answers:** 200 claims split from JurisGuard answers to the 50 law questions and 50 LegalBench-RAG CUAD questions,
  labelled supported / unsupported against the retrieved spans before any option is run on them. Labels are proposed by
  the developer's tooling and **checked by hand by the project owner on a random 50**; agreement is reported, and
  disagreements are resolved by the owner. A model of the same family as a judge option doesn't label.
- English only. The flag is off for German answers unless a German check is measured; the UI says which.

## Metrics

- **False-flag rate** (primary constraint): share of supported claims flagged.
- **Detection**: share of contradicted claims flagged, and separately of not-mentioned claims.
- **Information check**: a flag that fires at rate r on everything catches r of contradictions by chance, so detection is
  compared with the false-flag rate, not with zero.
- **Time to flags**: seconds from the final answer to the flags, p50 and p95, on the 50 law questions (n=100).
- 95% intervals on everything (bootstrap over claims; Wilson for proportions). At n=200 a 10% rate is about ±4 points.

## Operating point and budgets

- Threshold chosen on dev for a false-flag rate of 10%.
- Flags arrive after the final answer, so they don't delay it. Time to flags: **p50 ≤ 2 s, p95 ≤ 4 s** (the answer itself is
  p50 8.5 s, p95 16.8 s). CPU options must leave the LLM the whole GPU (D-001); extra RAM in the API **≤ 1.2 GB**.

## Decision rule, applied once to the held-out and real-answer sets

Adopt an option only if all hold:

1. False-flag rate on held-out ContractNLI ≤ 15% (upper 95% bound) and on the 200 real claims ≤ 15% (upper bound).
2. Detection of contradicted claims ≥ 30%, with its lower 95% bound above that option's false-flag rate.
3. Within the time and RAM budgets.

If several pass, the one with the highest detection. If none pass, keep the current check and label, publish the table, and
log it as a decision either way.

## Time-box

One week, to 2026-11-21. Whatever is measured by then is published, finished or not.
