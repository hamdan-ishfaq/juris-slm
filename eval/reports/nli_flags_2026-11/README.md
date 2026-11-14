# Flagging unsupported claims, 2026-11-14 (D-019)

The answer check passes 99.1% of claims the contract contradicts (D-014). This phase tested whether a flag could fire on
few supported claims and still catch contradicted ones. Everything below was fixed in advance in
`eval/nli/PREREGISTRATION.md`; the harness is `eval/nli/flags.py`.

**Result: no option met the pre-registered rule, so nothing was added.** The product keeps its relevance and citation
checks and says under each answer that support isn't checked.

## Setup

- Each ContractNLI (CC BY 4.0) hypothesis stands in for a claim; the premise is the five contract spans closest to it by
  bge-m3, as retrieval would supply them.
- Threshold for each option chosen on ContractNLI dev so that 10% of supported claims are flagged.
- Held out, scored once: 600 pairs from ContractNLI train (200 per label, seed 20261114, 332 documents). No earlier run
  used train; the test split was already scored for D-014.
- Times in the API container on the reference laptop: CPU options share about 3.5 cores; the Qwen3 judge runs on the GPU.

## Held-out result (`heldout.md`, `heldout.json`; 95% Wilson intervals)

| Option | False flags on supported (rule: upper bound ≤ 15%) | Contradicted flagged (rule: ≥ 30%, lower bound above false flags) | Not mentioned flagged | Time per claim (budget: answer's flags p50 ≤ 2 s) | Verdict |
|---|---|---|---|---|---|
| mDeBERTa, spans joined | 10.0% [6.6, 14.9] | 47.5% [40.7, 54.4] | 37.5% [31.1, 44.4] | 3.25 s | Fails time: about 13 s for a four-claim answer |
| mDeBERTa, each span | 11.5% [7.8, 16.7] | 53.0% [46.1, 59.8] | 36.5% [30.1, 43.4] | 3.0 s | Fails false flags and time |
| MiniLM, each span | 10.5% [7.0, 15.5] | 45.5% [38.8, 52.4] | 22.5% [17.3, 28.8] | 53 ms | Fails false flags, by 0.5 points on the upper bound |
| Qwen3 8B as judge | 33.5% [27.3, 40.3] | 95.5% [91.7, 97.6] | 81.5% [75.5, 86.3] | 0.53 s | Fails false flags: a third of supported claims |

On dev, at the chosen thresholds: false flags 9.8% for each threshold option, contradicted flagged 50.5%, 53.7% and 54.7%;
the judge flagged 33.1% of supported claims and 87.4% of contradicted ones.

## What it means

- Choosing the threshold for a false-flag budget changes D-014's picture. At its default decision mDeBERTa flagged 43% of
  supported claims; at a 10% budget the NLI models still catch about half of the contradictions, four to five times what a
  flag firing at random at the same rate would.
- MiniLM is fast enough (53 ms a claim) and close: its point estimate is on budget and only the upper bound misses. A larger
  held-out sample could settle it, but that would be a new pre-registered test, not a loosened rule.
- The judge model agrees with contradictions but calls a third of supported claims unsupported, so its flags would be noise.
- The 200 real-answer claims were not labelled: with no option passing on ContractNLI and time, they couldn't change the
  outcome. ContractNLI is English; German remains untested.
