"""A question's citations are read with their law, so a bare number isn't looked up in every statute (D-016)."""
from services.law_graph import cited_in_question, provision_label


def test_the_law_named_near_a_citation_is_kept():
    assert cited_in_question("Under GDPR Article 6(1)(f), what must controllers say?") == [("gdpr", "6")]
    assert cited_in_question("What does Article 12 of the AI Act require?") == [("eu_ai_act", "12")]
    assert cited_in_question("Welche Daten meint § 26 Absatz 3 BDSG?") == [("bdsg", "26")]
    assert cited_in_question("Was regelt Art. 9 DSGVO?") == [("gdpr", "9")]


def test_a_bare_article_number_has_no_law_yet():
    assert cited_in_question("What does Article 12 require?") == [(None, "12")]


def test_a_section_sign_without_a_name_is_bdsg_or_bgb():
    assert cited_in_question("What does § 26 say?") == [("bdsg", "26"), ("bgb", "26")]


def test_ranges_and_lists_are_read():
    assert cited_in_question("the rights in GDPR Articles 15 to 17") == [("gdpr", "15"), ("gdpr", "16"), ("gdpr", "17")]
    assert cited_in_question("BGB sections 280 and 281") == [("bgb", "280"), ("bgb", "281")]


def test_labels_read_as_lawyers_write_them():
    assert provision_label("gdpr", "6") == "GDPR Art. 6"
    assert provision_label("bgb", "437") == "BGB § 437"


def test_a_law_name_must_fit_the_provision_word_and_the_nearest_wins():
    assert cited_in_question("Von welcher Vorschrift der DSGVO weicht § 22 BDSG ab?") == [("bdsg", "22")]
    assert cited_in_question("Which BDSG section adds to GDPR Article 37?") == [("gdpr", "37")]
    assert cited_in_question("Does Article 9 GDPR or Article 5 of the AI Act apply?") == [("gdpr", "9"), ("eu_ai_act", "5")]


def _chunk(id_, law, article):
    return {"id": id_, "content": f"{law} {article} text {id_}", "metadata": {"kind": "law", "source": law, "article": article}}


def test_linked_provisions_are_added_once_each_after_the_ranked_chunks(monkeypatch):
    import asyncio

    from services import law_graph

    ranked = [_chunk(1, "gdpr", "30")]

    async def existing(_db, candidates):
        return [c for c in candidates if c == ("gdpr", "30")]

    async def linked(_db, provisions):
        return [("gdpr", "30", "gdpr", "9", False), ("gdpr", "30", "gdpr", "10", False), ("gdpr", "30", "gdpr", "49", False)]

    async def chunks(_db, provisions):
        out = []
        for n, (law, article) in enumerate(provisions):
            out += [_chunk(100 + 2 * n, law, article), _chunk(101 + 2 * n, law, article)]
        return out

    monkeypatch.setattr(law_graph, "existing_provisions", existing)
    monkeypatch.setattr(law_graph, "linked_provisions", linked)
    monkeypatch.setattr(law_graph, "provision_chunks", chunks)
    monkeypatch.setattr("services.reranker.rerank", lambda _q, hits, top_k: hits[:top_k])
    out = asyncio.run(law_graph.expand_with_links(None, "Which data does GDPR Article 30(5) mean?", ranked))
    assert out[0] is ranked[0]
    added = out[1:]
    assert [c["metadata"]["graph_path"] for c in added] == ["GDPR Art. 30 → GDPR Art. 9", "GDPR Art. 30 → GDPR Art. 10"]
    assert len({(c["metadata"]["source"], c["metadata"]["article"]) for c in added}) == len(added)


def test_a_question_citing_nothing_is_left_alone(monkeypatch):
    import asyncio

    from services import law_graph

    ranked = [_chunk(1, "gdpr", "6")]
    assert asyncio.run(law_graph.expand_with_links(None, "When is processing lawful?", ranked)) is ranked


def test_a_cited_provision_retrieval_missed_is_added(monkeypatch):
    import asyncio

    from services import law_graph

    async def existing(_db, candidates):
        return [c for c in candidates if c == ("bdsg", "38")]

    async def no_links(_db, _provisions):
        return []

    async def chunks(_db, provisions):
        return [_chunk(7, *provisions[0])] if provisions else []

    monkeypatch.setattr(law_graph, "existing_provisions", existing)
    monkeypatch.setattr(law_graph, "linked_provisions", no_links)
    monkeypatch.setattr(law_graph, "provision_chunks", chunks)
    out = asyncio.run(law_graph.expand_with_links(None, "When does BDSG § 38 require a DPO?", [_chunk(1, "gdpr", "37")]))
    assert out[-1]["metadata"]["graph_path"] == "cited: BDSG § 38"
