"""Find a document named in a question, and the part of the question that is really being asked.

A document's name in the query pulls vector search towards every chunk that mentions similar names, and away from the
clause being asked about. See docs/DECISIONS.md, D-005, D-007 and D-015.
"""
from __future__ import annotations

import math
import re
from collections.abc import Hashable, Mapping
from urllib.parse import unquote

# A route needs a clear lead over the next document, and evidence that grows with the number of documents. Set on
# LegalBench queries over 714 documents, where 1 of 320 routed queries went to the wrong document.
_MIN_LEAD = 3.0
_MIN_SCORE_PER_LOG_DOCUMENT = 0.5
# A word in more titles than this doesn't identify a document, however large the collection.
_MAX_TITLES_FOR_A_NAME = 5
_MIN_FOCUSED_WORDS = 3
_STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from has have how i if in into is it its may me must my no not of
    on or our shall should so such that the their them then there these they this to under was we were what when where
    which who whom why will with would you your""".split()
)
_WORD = re.compile(r"[a-z0-9]+")
_CLAUSE_END = re.compile(r"[;:,?]\s+")
# Names can hold commas ("Acme, Inc."), so only stronger breaks mark where the name ends.
_NAME_ENDS = re.compile(r"[;:?]\s")
_DESCRIPTION_CHARS = 600


def document_description(title: str, text: str) -> str:
    """What a user is likely to call a document by: its filename's words and its first and last paragraphs."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    first = paragraphs[0][:_DESCRIPTION_CHARS] if paragraphs else ""
    last = paragraphs[-1][:_DESCRIPTION_CHARS] if len(paragraphs) > 1 else ""
    return "\n".join((_title_words(title), first, last))


def naming_clause(question: str) -> str | None:
    """The clause before the question's first ";", ":" or "?", if there is a later part to ask about.

    A question asked across every document ("Which contracts cap liability?") has no such clause, so it isn't pulled
    towards a few documents that merely look similar.
    """
    parts = _NAME_ENDS.split(question, maxsplit=1)
    return parts[0] if len(parts) == 2 else None


def _title_words(title: str) -> str:
    return unquote(title.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]).lower()


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _name_terms(question: str) -> list[str]:
    """Capitalised words, leaving out the first: names look like this, and words such as "audit" don't."""
    words = re.findall(r"[A-Za-z0-9]+", question)[1:]
    names = (word.lower() for word in words if word[0].isupper() or word[0].isdigit())
    return [word for word in dict.fromkeys(names) if word not in _STOPWORDS and len(word) >= 3]


def route_to_document(question: str, titles: Mapping[Hashable, str]) -> Hashable | None:
    """Return the key of the document the question names, or None unless one stands out."""
    if len(titles) < 2:
        return None
    squashed = {key: _squash(_title_words(title)) for key, title in titles.items()}
    whole_words = {key: set(_WORD.findall(_title_words(title))) for key, title in titles.items()}
    # Words in the question itself, such as "confidential", would otherwise match titles that use them.
    terms = _name_terms(_NAME_ENDS.split(question, maxsplit=1)[0])
    matches = {term: sum(term in title for title in squashed.values()) for term in terms}
    scores: dict[Hashable, float] = {}
    for key, title in squashed.items():
        found = [term for term in terms if 0 < matches[term] <= _MAX_TITLES_FOR_A_NAME and term in title]
        # Rare words identify a document, and a substring is weaker evidence than a whole word.
        evidence = sum(
            math.log(1 + len(titles) / matches[term]) * (1.0 if term in whole_words[key] else 0.5) for term in found
        )
        coverage = min(1.0, sum(map(len, found)) / max(len(title), 1))
        scores[key] = evidence * (0.5 + coverage)
    best, second = sorted(scores, key=scores.__getitem__, reverse=True)[:2]
    floor = _MIN_SCORE_PER_LOG_DOCUMENT * math.log(1 + len(titles))
    if scores[best] >= floor and scores[best] > scores[second] * _MIN_LEAD:
        return best
    return None


def focus_question(question: str, title: str) -> str:
    """Keep what follows the clause naming the document. With no such clause, just remove the name."""
    squashed = _squash(_title_words(title))

    def names_document(word: str) -> bool:
        plain = _squash(word)
        return len(plain) >= 3 and plain not in _STOPWORDS and plain in squashed

    name_end = 0
    for match in re.finditer(r"\S+", question):
        if names_document(match.group()):
            name_end = match.end()
    boundary = _CLAUSE_END.search(question, max(name_end - 1, 0))
    if boundary:
        rest = question[boundary.end() :].strip()
        if len(rest.split()) >= _MIN_FOCUSED_WORDS:
            return rest
    return " ".join(word for word in question.split() if not names_document(word))
