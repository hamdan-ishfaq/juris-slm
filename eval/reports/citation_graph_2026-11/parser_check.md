# Reference parser, checked by hand

`backend/src/services/law_references.py` reads which provisions a provision refers to. Each sample chunk's text (first 700
characters) was read and every reference to a provision of the four corpus laws listed; the parser's output was compared
with that list. Chunks were drawn by seed, 8 per law, from chunks with an article and a reference word ("Article",
"Artikel", "Section", "§"). Chunk ids are in `parser_dev_chunk_ids.json` and `parser_test_chunk_ids.json`.

## Development sample (seed 20261113), read before the last parser changes

| Law | Correct | Wrong | Missed |
|---|---|---|---|
| GDPR | 5 | 4 | 0 |
| AI Act | 13 | 0 | 0 |
| BDSG | 6 | 4 | 0 |
| BGB | 2 | 0 | 0 |
| All | 26 | 8 | 0 |

Two causes, both fixed afterwards: "Articles 12 to 15 **of that Directive**" was read as the GDPR, and in "§ 2 Absatz 3, § 4
und § 10 **des Akkreditierungsstellengesetzes**" the law named at the end of the chain was missed. One more wrong reference,
"§ 1 Absatz 2 Satz 2" belonging to that act by the previous sentence, needs context no rule here reads.

## Test sample (seed 20261114), different chunks, read after the changes

| Law | Correct | Wrong | Missed |
|---|---|---|---|
| GDPR | 20 | 0 | 0 |
| AI Act | 9 | 2 | 0 |
| BDSG | 10 | 0 | 0 |
| BGB | 1 | 0 | 4 |
| All | **40** | **2** | **4** |

**Precision 95.2% (40 of 42), recall 90.9% (40 of 44)**, on 32 chunks. Too few to give a tight interval; read it as "most
references are right, a few are missed".

- Wrong: AI Act Article 108 amends another regulation, and "in Article 43, the following paragraph is added" means that
  regulation's Article 43. Articles 102 to 110 of the AI Act all amend other acts in this way.
- Missed: BGB section 586's "sections 536 (1) to (3) and of 536a to 536d", a range of lettered sections after "and of".

## The graph

With the final parser: 2,766 provisions (BGB 2,455, AI Act 126, GDPR 99, BDSG 86) and 3,620 references read from provision
text (BGB 2,797, AI Act 320, GDPR 318, BDSG 185); recitals and unnumbered text aren't provisions. 80 references cross laws:
BDSG to GDPR 68, AI Act to GDPR 8, BGB to GDPR 4. The most cited provision is GDPR Article 9, special categories of data,
with 22 references.
