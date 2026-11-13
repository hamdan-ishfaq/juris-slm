# Gap analysis on CUAD: the plan, fixed before any result

[CUAD v1](https://www.atticusprojectai.org/cuad) (CC BY 4.0, Zenodo record 4595826, sha256 of `CUAD_v1.zip`
`88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e`): 510 commercial contracts, each annotated for 41 clause
types, with an empty answer when the contract has none. Only the 462 contracts whose text is also a LegalBench-RAG document
are used, since those are already ingested and embedded (`juris_bench_full`).

**Task.** For each contract and each of 10 clause types, say whether the contract has the clause, and quote it. A gap
report is the list of clauses missing.

**Clause types** (a reviewer's checklist, from common to rare in CUAD): Governing Law, Anti-Assignment, Cap On Liability,
Audit Rights, Termination For Convenience, Exclusivity, Insurance, Change Of Control, Non-Compete, Warranty Duration.

**Split.** By contract, seed 20261113: 40 development contracts and 100 test contracts, listed in `sets.json`. The test set
is scored once.

**Measures,** with 95% bootstrap intervals over contracts:
- Missing clauses: precision and recall of "missing" against CUAD's empty answers. A false "missing" is a false alarm.
- Accuracy over all 1,000 test decisions, and per clause type.
- Quote found: for clauses called present that are present, the share whose quote overlaps a CUAD answer span.
- Model calls and seconds per contract.

CUAD's own metric (precision at 80% recall over span extraction) needs ranked span scores, which a yes/no decision with one
quote doesn't produce, so it isn't used; that is the adaptation.

**Methods:**
1. **Rule-based, unchanged:** the existing tool's topic patterns over the contract's chunks. Its "liability" topic is read
   as Cap On Liability and "termination" as Termination For Convenience; it has no way to say anything about the other
   eight, so they count as "missing".
2. **One LLM call:** the same question and schema, with the first 9,000 characters of the contract as context.
3. **Agent (D-017):** the product's search inside the contract for each clause type, then the same question and schema.

Prompts and settings may be changed on the development set only.
