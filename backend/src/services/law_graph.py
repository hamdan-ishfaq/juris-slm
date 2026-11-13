"""The citation graph over the shared statutes: built from their text, read when a question cites a provision (D-016)."""
from __future__ import annotations

import json
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


def _named_law(question: str, match: re.Match, previous_end: int, next_start: int, fitting: tuple[str, ...]) -> str | None:
    """The law named for one citation. Citations usually name it after the number ("Article 5 of the AI Act", "§ 26
    BDSG") and sometimes before it ("GDPR Article 6"), so the nearest name after wins, then the nearest before, never
    reaching past a neighbouring citation."""
    after_end = min(next_start, match.end() + _NEAR)
    before_start = max(previous_end, match.start() - _NEAR)
    best: tuple[int, int, str] | None = None
    for law in fitting:
        for name in re.finditer(rf"(?<!\w)(?:{_LAW_NAMES[law]})(?!\w)", question, re.IGNORECASE):
            if match.end() <= name.start() < after_end:
                rank = (0, name.start() - match.end(), law)
            elif before_start <= name.start() and name.end() <= match.start():
                rank = (1, match.start() - name.end(), law)
            else:
                continue
            best = min(best, rank) if best else rank
    return best[2] if best else None


def cited_in_question(question: str) -> list[tuple[str | None, str]]:
    """Provisions a question cites, each with its law when the question names one near it, in order of appearance."""
    matches = list(_QUESTION_CITATION.finditer(question))
    found: list[tuple[str | None, str]] = []
    for i, match in enumerate(matches):
        marker = match.group("marker").lower()
        # "§" and "Section" are BDSG and BGB provisions; "Article" and "Artikel" are GDPR and AI Act ones.
        fitting = ("bdsg", "bgb") if marker.startswith(("§", "sec")) else ("gdpr", "eu_ai_act")
        previous_end = matches[i - 1].end() if i else 0
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(question)
        law = _named_law(question, match, previous_end, next_start, fitting)
        laws = [law] if law else list(fitting) if marker.startswith(("§", "sec")) else [None]
        for number in provision_numbers(match.group("numbers")):
            found.extend((candidate, number) for candidate in laws)
    return list(dict.fromkeys(found))


async def existing_provisions(db: AsyncSession, candidates: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The candidates that are provisions in the graph, in the order given."""
    wanted = list(dict.fromkeys(candidates))
    if not wanted:
        return []
    rows = await db.execute(
        text("SELECT law, article FROM law_provisions WHERE (law, article) IN (SELECT * FROM unnest(CAST(:laws AS text[]), CAST(:articles AS text[])))"),
        {"laws": [law for law, _ in wanted], "articles": [article for _, article in wanted]},
    )
    present = {(row[0], row[1]) for row in rows}
    return [provision for provision in wanted if provision in present]


async def linked_provisions(
    db: AsyncSession, provisions: list[tuple[str, str]]
) -> list[tuple[str, str, str, str, bool]]:
    """References to and from the given provisions: (law, article, linked law, linked article, incoming), outgoing first."""
    if not provisions:
        return []
    params = {"laws": [law for law, _ in provisions], "articles": [article for _, article in provisions]}
    rows = await db.execute(
        text(
            """
            WITH cited AS (SELECT * FROM unnest(CAST(:laws AS text[]), CAST(:articles AS text[])) AS c(law, article))
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
    return [(row[0], row[1], row[2], row[3], bool(row[4])) for row in rows]


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
              AND (metadata->>'source', metadata->>'article') IN (SELECT * FROM unnest(CAST(:laws AS text[]), CAST(:articles AS text[])))
            ORDER BY id
            """
        ),
        {"laws": [law for law, _ in provisions], "articles": [article for _, article in provisions]},
    )
    chunks = [dict(row) for row in rows.mappings()]
    for chunk in chunks:
        if isinstance(chunk.get("metadata"), str):
            chunk["metadata"] = json.loads(chunk["metadata"])
    return chunks


_MAX_LINKED_CHUNKS = 2
_MAX_LINKED_PROVISIONS = 12


def _provision_of(hit: dict) -> tuple[str, str] | None:
    meta = hit.get("metadata") or {}
    if meta.get("kind") != "law" or not meta.get("article"):
        return None
    return meta.get("source"), meta.get("article")


async def _resolve(db: AsyncSession, question: str, ranked: list[dict]) -> list[tuple[str, str]]:
    """The provisions a question cites. A number with no law named takes the first retrieved law that has it."""
    cites = cited_in_question(question)
    named = [(law, number) for law, number in cites if law]
    bare = [number for law, number in cites if not law]
    retrieved_laws = list(dict.fromkeys(p[0] for p in map(_provision_of, ranked) if p)) or list(LAWS)
    found = await existing_provisions(db, named + [(law, number) for number in bare for law in retrieved_laws])
    resolved = [provision for provision in found if provision in named]
    for number in bare:
        resolved.extend(next(([p] for p in found if p[1] == number and p not in named), []))
    return list(dict.fromkeys(resolved))[:3]


async def _best(question: str, chunks: list[dict], k: int) -> list[dict]:
    """The k chunks closest to the question: the reranker for English, embeddings for German, which it can't read (D-006)."""
    if len(chunks) <= k:
        return chunks
    from services.rag import looks_german

    if looks_german(question):
        import numpy as np

        from services.embeddings import embed_texts

        vectors = embed_texts([question] + [chunk["content"] for chunk in chunks])
        scores = vectors[1:] @ vectors[0]
        return [chunks[i] for i in np.argsort(-scores)[:k]]
    from services.reranker import rerank

    return rerank(question, chunks, top_k=k)


async def expand_with_links(db: AsyncSession, question: str, ranked: list[dict]) -> list[dict]:
    """Add what a cited provision depends on: the provision itself if retrieval missed it, and the best chunks of the
    provisions it cites or is cited by. Added chunks carry their path and get their own room in the context (D-016)."""
    cited = await _resolve(db, question, ranked)
    if not cited:
        return ranked
    in_ranked = {p for p in map(_provision_of, ranked) if p}
    added: list[dict] = []
    for provision in cited:
        if provision not in in_ranked:
            chunks = await provision_chunks(db, [provision])
            for chunk in (await _best(question, chunks, 1)):
                chunk["metadata"] = {**(chunk.get("metadata") or {}), "graph_path": f"cited: {provision_label(*provision)}"}
                added.append(chunk)
    # Each linked provision once, with the path as the text reads: "GDPR Art. 13 → GDPR Art. 6" when Art. 13 cites Art. 6.
    paths: dict[tuple[str, str], str] = {}
    for law, article, other_law, other_article, incoming in await linked_provisions(db, cited):
        other = (other_law, other_article)
        if other in in_ranked or other in cited:
            continue
        ends = (provision_label(other_law, other_article), provision_label(law, article))
        paths.setdefault(other, " → ".join(ends if incoming else reversed(ends)))
    linked = list(paths)[:_MAX_LINKED_PROVISIONS]
    candidates = await provision_chunks(db, linked)
    for chunk in await _best(question, candidates, _MAX_LINKED_CHUNKS):
        provision = _provision_of(chunk)
        chunk["metadata"] = {**(chunk.get("metadata") or {}), "graph_path": paths.get(provision, "")}
        added.append(chunk)
    if not added:
        return ranked
    seen = {hit.get("id") for hit in ranked}
    added = [chunk for chunk in added if chunk.get("id") not in seen]
    return ranked + added
