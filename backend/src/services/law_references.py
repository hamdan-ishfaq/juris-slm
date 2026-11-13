"""Read the references one provision of a law makes to others, by rule. See docs/DECISIONS.md, D-016.

Covers the four statutes in the corpus and the forms their texts use: "Article 6(1), point (f)", "Articles 13 and 14",
"Articles 12 to 22 of Regulation (EU) 2016/679", "§ 26 Absatz 1", "§§ 32 bis 37", "Artikel 9 der Verordnung (EU)
2016/679", "sections 636, 280, 281, 283 and 311a". References to laws outside the corpus are dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

GDPR_NUMBER = "2016/679"
# The word each law uses for its own provisions. The AI Act's "SECTION 3" and the GDPR's "Section 2" are chapter headings.
_OWN_MARKER = {"gdpr": "article", "eu_ai_act": "article", "bdsg": "paragraph", "bgb": "section"}
_MAX_RANGE = 30

_NUMBER = r"\d+[a-z]?"
# A number with its subdivisions: 6(1)(f), 26 Absatz 1, 358 subsections (2) and (4).
_SUBDIVISION = r"(?:\s*\(\s*\w{1,4}\s*\))*"
_SEPARATOR = r"\s*(?:,\s*(?:and\s+|or\s+)?|\s(?:and/or|and|or|to|und|oder|bis)\s)\s*"
_REFERENCE = re.compile(
    rf"(?P<marker>\bArt(?:icles?|ikeln?|ikels|\.)|\bSections?|§§?)\s*"
    rf"(?P<numbers>{_NUMBER}{_SUBDIVISION}(?:{_SEPARATOR}{_NUMBER}{_SUBDIVISION})*)",
    re.IGNORECASE,
)
_NUMBER_IN_LIST = re.compile(rf"(?P<sep>\b(?:to|bis)\s+)?(?P<number>{_NUMBER})")
# What follows the numbers names the law, if anything does: "of Regulation (EU) 2016/679", "der Richtlinie (EU) 2016/680".
# A chain such as "§ 2 Absatz 3, § 4 und § 10 des Akkreditierungsstellengesetzes" names its law once, at the end.
_CHAIN = (
    r"(?:[\s,]*(?:und|oder|and|or|sowie)?\s*"
    r"(?:(?:Abs\.|Absatz|Absätze|Satz|Sätze|Nr\.|Nummer|Buchstabe|points?|sentences?|subsections?|subparagraphs?)\s*\(?\w{1,4}\)?"
    r"|(?:first|second|third|fourth)\s+subparagraph|§§?\s*\d+[a-z]?|\(\s*\w{1,4}\s*\)))*"
)
_LAW_AFTER = re.compile(rf"^{_CHAIN}[\s,]*(?P<law>\b(?:of|der|des)\s+(?P<word>[\w-]+)[^.;]{{0,60}})?", re.IGNORECASE)
# Words after "of", "der" or "des" that keep a reference inside the citing law: "of this Regulation", and "point (a) of
# Article 9(2)" or "of section 1037", where another provision of the same law follows.
_SAME_LAW = frozenset(
    {"this", "these", "dieses", "diesem", "dieser", "article", "articles", "artikel", "artikels", "section", "sections",
     "chapter", "annex", "paragraph", "point", "points", "subparagraph"}
)


@dataclass(frozen=True)
class Reference:
    law: str
    article: str


def _target_law(source: str, marker: str, law_phrase: str | None, law_word: str | None) -> str | None:
    """The law a reference points to, or None when it is outside the corpus."""
    if law_phrase and GDPR_NUMBER in law_phrase:
        return "gdpr"
    same = law_word and (
        law_word.lower() in _SAME_LAW or re.match(r"(?:of|der|des)\s+the\s+(?:present|same)\b", law_phrase or "", re.I)
    )
    if law_word and not same:
        return None  # another regulation, directive, treaty or act, or "of that Directive"
    word = "section" if marker.lower().startswith("sec") else "paragraph" if marker.startswith("§") else "article"
    if word == _OWN_MARKER[source]:
        return source
    if source == "bdsg" and word == "article":
        return "gdpr"  # the BDSG has no articles; its "Artikel" are the GDPR's
    return None


def _numbers(listing: str) -> list[str]:
    """Every provision number in a list, with short ranges expanded and subdivisions skipped."""
    # Subdivisions such as (1) or (f) aren't provisions, so remove them before reading the numbers.
    listing = re.sub(r"\(\s*\w{1,4}\s*\)", " ", listing)
    listing = re.sub(r"\b(?:Absatz|Satz|Nummer|subsections?|paragraphs?)\s+\d+", " ", listing, flags=re.IGNORECASE)
    found: list[str] = []
    for match in _NUMBER_IN_LIST.finditer(listing):
        number = match.group("number")
        if match.group("sep") and found and found[-1].isdigit() and number.isdigit():
            start, end = int(found[-1]), int(number)
            if 0 < end - start <= _MAX_RANGE:
                found.extend(str(n) for n in range(start + 1, end + 1))
                continue
        found.append(number)
    return found


def parse_references(text: str, *, source: str, article: str, known: set[tuple[str, str]]) -> set[Reference]:
    """The provisions of corpus laws that `text`, from `article` of `source`, refers to."""
    refs: set[Reference] = set()
    for match in _REFERENCE.finditer(text):
        after = _LAW_AFTER.match(text[match.end():])
        law = _target_law(
            source, match.group("marker"), after.group("law") if after else None, after.group("word") if after else None
        )
        if law is None:
            continue
        for number in _numbers(match.group("numbers")):
            if (law, number) in known and (law, number) != (source, article):
                refs.add(Reference(law, number))
    return refs
