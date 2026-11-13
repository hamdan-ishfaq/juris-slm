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
