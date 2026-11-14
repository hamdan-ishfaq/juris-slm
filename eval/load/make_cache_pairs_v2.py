#!/usr/bin/env python3
"""Second, fresh pair set for the semantic cache (eval/load/PLAN.md step 5, amendment of 2026-11-15).

The first set counted any hit on a near miss as wrong. One of its near misses asked exactly what another cached question
asks, so that hit was a correct answer scored as wrong. Here every probe names the cached question whose answer it
should get ("answer_id"), or none. A hit is right only if it lands on that question. Every probe is new wording, none
reused from the first set. The threshold stays at 0.9531, chosen on the first set's dev half, and every probe here is
held out.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# probe -> answer_id (a law_qa id, or None when no cached question answers it)
HITS: dict[str, str] = {
    "Explain lawful processing as defined in GDPR Article 6.": "gdpr-001",
    "What are the requirements for valid consent in GDPR Article 7?": "gdpr-002",
    "What protection does GDPR Article 8 give to children's data?": "gdpr-003",
    "Under Article 9, which personal data are special categories?": "gdpr-004",
    "Under Article 10, when is it allowed to process data on criminal convictions?": "gdpr-005",
    "What rule does Article 11 set for processing that does not require identification?": "gdpr-006",
    "What are the transparency obligations in Article 12?": "gdpr-007",
    "Under Article 13, what information is owed when data is collected from the data subject?": "gdpr-008",
    "Under Article 14, what information is owed when data is not obtained from the data subject?": "gdpr-009",
    "Explain the right of access under Article 15.": "gdpr-010",
    "Explain the right to rectification under Article 16.": "gdpr-011",
    "Explain the right to erasure under Article 17.": "gdpr-012",
    "Explain the right to restriction of processing under Article 18.": "gdpr-013",
    "Explain the right to data portability under Article 20.": "gdpr-014",
    "Explain the right to object under Article 21.": "gdpr-015",
    "Explain the rules on automated decision-making under Article 22.": "gdpr-016",
    "Explain processor obligations under Article 28.": "gdpr-017",
    "What processing records does Article 30 make mandatory?": "gdpr-018",
    "What measures for security of processing does Article 32 require?": "gdpr-019",
    "Under Article 33, when must the supervisory authority be notified of a personal data breach?": "gdpr-020",
    "When does Article 36 require prior consultation with the supervisory authority?": "gdpr-021",
    "When does Article 35 require a data protection impact assessment?": "gdpr-022",
    "When do Articles 37-39 require a data protection officer to be designated?": "gdpr-023",
    "Explain the rules for international transfers under Articles 44-49.": "gdpr-024",
    "When are legitimate interests a lawful basis under Article 6(1)(f)?": "gdpr-025",
    "When does contract performance serve as a lawful basis under Article 6(1)(b)?": "gdpr-026",
    "When does a legal obligation serve as a lawful basis under Article 6(1)(c)?": "gdpr-027",
    "When can vital interests be relied on for processing under Article 6(1)(d)?": "gdpr-028",
    "When is public task a lawful basis under Article 6(1)(e)?": "gdpr-029",
    "Explain what data minimization requires under Article 5(1)(c).": "gdpr-030",
    "Explain what a purchase contract is under BGB Section 433.": "bgb-001",
    "Explain when a defect exists under BGB Section 434.": "bgb-002",
    "Explain the remedies for defects under BGB Section 437.": "bgb-003",
    "Explain when damages are owed for breach of duty under BGB Section 280.": "bgb-004",
    "Explain how a contract is formed under BGB Section 145.": "bgb-005",
    "Explain the withdrawal rights under BGB Section 355.": "bgb-006",
    "Explain the core obligations of a lease under BGB Section 535.": "bgb-007",
    "Explain what defines a work contract under BGB Section 631.": "bgb-008",
    "Explain the agency rules under BGB Section 675.": "bgb-009",
    "Explain when the standard limitation period begins under BGB Section 199.": "bgb-010",
    "Explain the difference between a controller and a processor under GDPR.": "cross-001",
    "Explain how GDPR processor terms relate to a master services agreement.": "cross-002",
    "Explain how legitimate interests are balanced under GDPR Article 6(1)(f).": "cross-003",
    "Explain which transfer tools are relevant under GDPR Article 46.": "cross-004",
    "Explain how employee data may be processed in a B2B context under GDPR.": "cross-005",
}

# Near misses: no cached question answers these (answer_id None).
MISSES: list[tuple[str, str]] = [
    ("other_article", "Explain lawful processing as defined in GDPR Article 26."),
    ("other_article", "What are the requirements for valid consent in GDPR Article 4?"),
    ("other_article", "What protection does GDPR Article 18 give to children's data?"),
    ("other_article", "Under Article 19, which personal data are special categories?"),
    ("other_article", "Under Article 11, when is it allowed to process data on criminal convictions?"),
    ("other_article", "What rule does Article 2 set for processing that does not require identification?"),
    ("other_article", "What are the transparency obligations in Article 5?"),
    ("other_article", "Explain the right of access under Article 25."),
    ("other_article", "Explain the right to rectification under Article 19."),
    ("other_article", "Explain the right to erasure under Article 7."),
    ("other_article", "Explain the right to restriction of processing under Article 8."),
    ("other_article", "Explain the right to data portability under Article 12."),
    ("other_article", "Explain the right to object under Article 26."),
    ("other_article", "Explain the rules on automated decision-making under Article 24."),
    ("other_article", "Explain processor obligations under Article 38."),
    ("other_article", "What processing records does Article 40 make mandatory?"),
    ("other_article", "What measures for security of processing does Article 25 require?"),
    ("other_article", "When does Article 37 require prior consultation with the supervisory authority?"),
    ("other_article", "When does Article 39 require a data protection impact assessment?"),
    ("other_article", "Explain the rules for international transfers under Articles 54-59."),
    ("other_article", "Explain what a purchase contract is under BGB Section 443."),
    ("other_article", "Explain when a defect exists under BGB Section 633."),
    ("other_article", "Explain the remedies for defects under BGB Section 536."),
    ("other_article", "Explain when damages are owed for breach of duty under BGB Section 283."),
    ("other_article", "Explain how a contract is formed under BGB Section 154."),
    ("other_article", "Explain the withdrawal rights under BGB Section 346."),
    ("other_article", "Explain the core obligations of a lease under BGB Section 581."),
    ("other_article", "Explain what defines a work contract under BGB Section 632."),
    ("other_article", "Explain the agency rules under BGB Section 662."),
    ("other_article", "Explain when the standard limitation period begins under BGB Section 198."),
    ("other_article", "Explain which transfer tools are relevant under GDPR Article 47."),
    ("other_law", "Explain the right of access under BDSG Section 57."),
    ("other_law", "Explain the right to erasure under BDSG Section 58."),
    ("other_law", "What processing records does BDSG Section 70 make mandatory?"),
    ("other_law", "Explain lawful processing as defined in BDSG Section 3."),
    ("other_law", "Explain processor obligations under BDSG Section 62."),
    ("other_law", "When does BDSG Section 67 require a data protection impact assessment?"),
    ("other_law", "Explain the obligations of providers under AI Act Article 16."),
    ("other_point", "When are legitimate interests a lawful basis under Article 6(1)(a)?"),
    ("other_point", "When does contract performance serve as a lawful basis under Article 6(1)(d)?"),
    ("other_point", "When does a legal obligation serve as a lawful basis under Article 6(1)(f)?"),
    ("other_point", "When can vital interests be relied on for processing under Article 6(1)(c)?"),
    ("other_point", "When is public task a lawful basis under Article 6(1)(b)?"),
    ("other_point", "Explain what lawfulness, fairness and transparency require under Article 5(1)(a)."),
    ("other_point", "Explain what integrity and confidentiality require under Article 5(1)(f)."),
    ("other_point", "Explain what accountability requires under Article 5(2)."),
    ("other_point", "Explain the conditions in Article 6(4) for processing for another purpose."),
    ("other_point", "Explain what Article 6(3) says about the legal basis for public tasks."),
    ("other_point", "Explain how legitimate interests are balanced under GDPR Article 6(1)(d)."),
    ("same_provision_other_question", "Is consent under GDPR Article 7 valid if it is bundled with terms of service?"),
    ("same_provision_other_question", "What must a controller be able to show about consent under GDPR Article 7?"),
    ("same_provision_other_question", "Which member states lowered the age of consent under GDPR Article 8?"),
    ("same_provision_other_question", "Is biometric data a special category under Article 9?"),
    ("same_provision_other_question", "Who keeps registers of criminal convictions under Article 10?"),
    ("same_provision_other_question", "In what form must information be given under Article 12?"),
    ("same_provision_other_question", "Must the controller name its DPO in the information under Article 13?"),
    ("same_provision_other_question", "Within what period must information be given under Article 14?"),
    ("same_provision_other_question", "What information about recipients is included in the right of access under Article 15?"),
    ("same_provision_other_question", "Does the right to erasure under Article 17 cover backups?"),
    ("same_provision_other_question", "Must recipients be told about erasure under Article 17?"),
    ("same_provision_other_question", "Does the right to data portability under Article 20 cover inferred data?"),
    ("same_provision_other_question", "Can the controller refuse an objection on compelling grounds under Article 21?"),
    ("same_provision_other_question", "Does profiling fall under Article 22?"),
    ("same_provision_other_question", "Must a processor keep data confidential under Article 28?"),
    ("same_provision_other_question", "Must a processor delete data at the end of the contract under Article 28?"),
    ("same_provision_other_question", "Does Article 30 require records to be in writing?"),
    ("same_provision_other_question", "Does Article 32 require regular testing of security measures?"),
    ("same_provision_other_question", "Must a processor tell the controller about a breach under Article 33?"),
    ("same_provision_other_question", "Must a controller document breaches it did not report under Article 33?"),
    ("same_provision_other_question", "Who must be consulted on a DPIA under Article 35?"),
    ("same_provision_other_question", "Can a group of companies share one DPO under Articles 37-39?"),
    ("same_provision_other_question", "What derogations for specific situations exist under Articles 44-49?"),
    ("same_provision_other_question", "Can a newsletter rely on legitimate interests under Article 6(1)(f)?"),
    ("same_provision_other_question", "Does pre-contractual processing fall under Article 6(1)(b)?"),
    ("same_provision_other_question", "Does a foreign legal obligation count under Article 6(1)(c)?"),
    ("same_provision_other_question", "Who decides what counts as a public task under Article 6(1)(e)?"),
    ("same_provision_other_question", "Does data minimization under Article 5(1)(c) forbid keeping data for analytics?"),
    ("same_provision_other_question", "When does ownership pass under a purchase contract under BGB Section 433?"),
    ("same_provision_other_question", "Does a wrong delivery count as a defect under BGB Section 434?"),
    ("same_provision_other_question", "In what order can buyer remedies be used under BGB Section 437?"),
    ("same_provision_other_question", "What counts as a duty under BGB Section 280?"),
    ("same_provision_other_question", "Is an advertisement an offer under BGB Section 145?"),
    ("same_provision_other_question", "Who bears the cost of returning goods after withdrawal under BGB Section 355?"),
    ("same_provision_other_question", "Can a landlord raise the rent under BGB Section 535?"),
    ("same_provision_other_question", "When is payment due under a work contract under BGB Section 631?"),
    ("same_provision_other_question", "Is an agent liable for mistakes under BGB Section 675?"),
    ("same_provision_other_question", "Does lack of knowledge delay the limitation period under BGB Section 199?"),
    ("same_provision_other_question", "Who is liable to data subjects when a processor breaches GDPR?"),
    ("same_provision_other_question", "Which law governs a master services agreement with processor terms under GDPR?"),
    ("same_provision_other_question", "Which documents must accompany standard contractual clauses under GDPR Article 46?"),
    ("same_provision_other_question", "Can employee monitoring rely on consent under GDPR?"),
    ("same_provision_other_question", "Is a works council agreement a legal basis for employee data under GDPR?"),
    ("same_provision_other_question", "What is the difference between a processor and a sub-processor under GDPR?"),
    ("same_provision_other_question", "Who is a third party as opposed to a processor under GDPR?"),
    ("same_provision_other_question", "Is a DPIA mandatory for employee monitoring under Article 35?"),
    ("same_provision_other_question", "Can the right of access under Article 15 be refused as excessive?"),
    ("same_provision_other_question", "What fee may be charged for repeated requests under Article 12?"),
    ("same_provision_other_question", "How quickly must rectification happen under Article 16?"),
    ("same_provision_other_question", "Can a data subject demand restriction while accuracy is checked under Article 18?"),
    ("same_provision_other_question", "Does Article 11 require the controller to collect extra data to identify a person?"),
    ("same_provision_other_question", "Is health data used for research a special category under Article 9?"),
    ("same_provision_other_question", "Is there a limit on damages under BGB Section 280?"),
    ("same_provision_other_question", "Can withdrawal rights be waived under BGB Section 355?"),
]


def main() -> int:
    golden = {json.loads(line)["id"]: json.loads(line)["question"]
              for line in (ROOT / "eval" / "golden" / "law_qa.jsonl").read_text().splitlines() if line.strip()}
    v1 = {json.loads(line)["probe"] for line in (ROOT / "eval" / "load" / "cache_pairs.jsonl").read_text().splitlines()}
    rows = [{"probe": p, "answer_id": a, "kind": "paraphrase"} for p, a in HITS.items()]
    rows += [{"probe": p, "answer_id": None, "kind": k} for k, p in MISSES]
    assert not v1 & {r["probe"] for r in rows}, "probes must be new"
    assert all(r["answer_id"] in golden for r in rows if r["answer_id"])
    out = ROOT / "eval" / "load" / "cache_pairs_v2.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} probes: {len(HITS)} with an answer, {len(MISSES)} without")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
