from services.rag import (
    _boost_art6_basis_hits,
    _extractive_fallback,
    _is_model_refusal,
    _short_query_refusal,
)


def test_extractive_fallback_from_context():
    context = "[1] (GDPR)\nprocessing is necessary for compliance with a legal obligation to which the controller is subject"
    answer = _extractive_fallback(context, "When is legal obligation a lawful basis under Article 6(1)(c)?")
    assert "legal obligation" in answer.lower()


def test_model_refusal_detection():
    assert _is_model_refusal("As an AI developed by Microsoft, I cannot assist.")
    assert not _is_model_refusal("Disclosure is permitted when required by law.")


def test_boost_art6_legal_obligation():
    hits = [
        {"content": "unrelated preamble about data protection"},
        {"content": "processing is necessary for compliance with a legal obligation to which the controller is subject"},
    ]
    boosted = _boost_art6_basis_hits(
        "When is legal obligation a lawful basis under Article 6(1)(c)?",
        hits,
    )
    assert "legal obligation" in boosted[0]["content"]


def test_short_query_refusal():
    result = _short_query_refusal("law", document_id=None)
    assert result is not None
    assert "too short" in result["answer"].lower()


def test_short_query_allowed_with_document():
    assert _short_query_refusal("law", document_id="doc-uuid") is None


def test_normal_query_not_short_refusal():
    assert _short_query_refusal("What is GDPR Article 6?", document_id=None) is None
