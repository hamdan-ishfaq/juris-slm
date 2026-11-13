"""The citation graph over the shared statutes: built from their text, read when a question cites a provision (D-016)."""
from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.law_references import NUMBER, parse_references, provision_numbers

LAWS = ("gdpr", "bdsg", "bgb", "eu_ai_act")
LAW_LABELS = {"gdpr": "GDPR", "bdsg": "BDSG", "bgb": "BGB", "eu_ai_act": "AI Act"}
_PROVISION_WORD = {"gdpr": "Art.", "eu_ai_act": "Art.", "bdsg": "§", "bgb": "§"}
# Names a question may use for each law, searched near the citation.
_LAW_NAMES = {
    "gdpr": r"GDPR|DSGVO|DS-GVO|General Data Protection Regulation|Datenschutz-Grundverordnung|2016/679",
    "bdsg": r"BDSG|Bundesdatenschutzgesetz|Federal Data Protection Act",
    "bgb": r"BGB|Civil Code|Bürgerliche[sn]? Gesetzbuch",
    "eu_ai_act": r"AI Act|AI-Act|KI-Verordnung|Artificial Intelligence Act|2024/1689",
}
_QUESTION_CITATION = re.compile(
    rf"(?P<marker>\bArt(?:icles?|ikeln?|ikels|\.)|\bSections?|§§?)\s*(?P<numbers>{NUMBER}(?:\s*\(\s*\w{{1,4}}\s*\))*"
    rf"(?:\s*(?:,|and|or|to|und|oder|bis)\s*{NUMBER}(?:\s*\(\s*\w{{1,4}}\s*\))*)*)",
    re.IGNORECASE,
)
_NEAR = 40


def provision_label(law: str, article: str) -> str:
    return f"{LAW_LABELS[law]} {_PROVISION_WORD[law]} {article}"


async def rebuild_law_graph(db: AsyncSession) -> dict[str, int]:
    """Replace the graph with the provisions and references read from the shared law chunks now in the database."""
    rows = (
        await db.execute(
            text(
                """
                SELECT id, metadata->>'source' AS law, metadata->>'article' AS article,
                       COALESCE(metadata->>'section_title', '') AS title, content
                FROM document_chunks
                WHERE metadata->>'kind' = 'law' AND metadata->>'org_id' IS NULL
                  AND metadata->>'source' = ANY(:laws) AND COALESCE(metadata->>'article', '') <> ''
                ORDER BY id
                """
            ),
            {"laws": list(LAWS)},
        )
    ).mappings().all()
    titles: dict[tuple[str, str], str] = {}
    for row in rows:
        titles.setdefault((row["law"], row["article"]), row["title"])
    references: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        for ref in parse_references(row["content"], source=row["law"], article=row["article"], known=set(titles)):
            references.setdefault((row["law"], row["article"], ref.law, ref.article), row["id"])
    await db.execute(text("DELETE FROM law_references"))
    await db.execute(text("DELETE FROM law_provisions"))
    if titles:
        await db.execute(
            text("INSERT INTO law_provisions (law, article, title) VALUES (:law, :article, :title)"),
            [{"law": law, "article": article, "title": title} for (law, article), title in titles.items()],
        )
    if references:
        await db.execute(
            text(
                """
                INSERT INTO law_references (from_law, from_article, to_law, to_article, chunk_id)
                VALUES (:from_law, :from_article, :to_law, :to_article, :chunk_id)
                """
            ),
            [
                {"from_law": a, "from_article": b, "to_law": c, "to_article": d, "chunk_id": chunk}
                for (a, b, c, d), chunk in references.items()
            ],
        )
    await db.commit()
    return {"provisions": len(titles), "references": len(references)}


def cited_in_question(question: str) -> list[tuple[str | None, str]]:
    """Provisions a question cites, each with its law when the question names one near it, in order of appearance."""
    found: list[tuple[str | None, str]] = []
    for match in _QUESTION_CITATION.finditer(question):
        nearby = question[max(0, match.start() - _NEAR) : match.end() + _NEAR]
        named = [law for law, names in _LAW_NAMES.items() if re.search(rf"(?<!\w)(?:{names})(?!\w)", nearby, re.IGNORECASE)]
        marker = match.group("marker").lower()
        if not named:
            # Without a name, only the provision word narrows it down: "§" and "Section" aren't GDPR or AI Act provisions.
            named = ["bdsg", "bgb"] if marker.startswith(("§", "sec")) else []
        for number in provision_numbers(match.group("numbers")):
            if len(named) == 1:
                found.append((named[0], number))
            elif named:
                found.extend((law, number) for law in named)
            else:
                found.append((None, number))
    return list(dict.fromkeys(found))


async def existing_provisions(db: AsyncSession, candidates: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The candidates that are provisions in the graph, in the order given."""
    wanted = list(dict.fromkeys(candidates))
    if not wanted:
        return []
    rows = await db.execute(
        text("SELECT law, article FROM law_provisions WHERE (law, article) IN (SELECT * FROM unnest(:laws, :articles))"),
        {"laws": [law for law, _ in wanted], "articles": [article for _, article in wanted]},
    )
    present = {(row[0], row[1]) for row in rows}
    return [provision for provision in wanted if provision in present]


async def linked_provisions(db: AsyncSession, provisions: list[tuple[str, str]]) -> list[tuple[str, str, str, str]]:
    """References to and from the given provisions: (law, article, linked law, linked article), outgoing first."""
    if not provisions:
        return []
    params = {"laws": [law for law, _ in provisions], "articles": [article for _, article in provisions]}
    rows = await db.execute(
        text(
            """
            WITH cited AS (SELECT * FROM unnest(:laws, :articles) AS c(law, article))
            SELECT r.from_law, r.from_article, r.to_law, r.to_article, 0 AS incoming
            FROM law_references r JOIN cited c ON (r.from_law, r.from_article) = (c.law, c.article)
            UNION ALL
            SELECT r.to_law, r.to_article, r.from_law, r.from_article, 1 AS incoming
            FROM law_references r JOIN cited c ON (r.to_law, r.to_article) = (c.law, c.article)
            ORDER BY incoming
            """
        ),
        params,
    )
    return [(row[0], row[1], row[2], row[3]) for row in rows]


async def provision_chunks(db: AsyncSession, provisions: list[tuple[str, str]]) -> list[dict]:
    """Every shared law chunk of the given provisions, found by their law and article rather than by text search."""
    if not provisions:
        return []
    rows = await db.execute(
        text(
            """
            SELECT id, document_id, content, metadata
            FROM document_chunks
            WHERE metadata->>'kind' = 'law' AND metadata->>'org_id' IS NULL
              AND (metadata->>'source', metadata->>'article') IN (SELECT * FROM unnest(:laws, :articles))
            ORDER BY id
            """
        ),
        {"laws": [law for law, _ in provisions], "articles": [article for _, article in provisions]},
    )
    return [dict(row) for row in rows.mappings()]
