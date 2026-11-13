"""References between provisions are read by rule; laws outside the corpus and chapter headings are left out (D-016)."""
from services.law_references import Reference, parse_references

KNOWN = (
    {("gdpr", str(n)) for n in range(1, 100)}
    | {("eu_ai_act", str(n)) for n in range(1, 114)}
    | {("bdsg", str(n)) for n in range(1, 86)}
    | {("bgb", n) for n in ("280", "281", "283", "311a", "636", "437", "1373", "1374", "1375")}
)


def refs(text, source, article="1"):
    return parse_references(text, source=source, article=article, known=KNOWN)


def test_a_point_and_paragraph_stay_with_their_article():
    assert refs("processing based on Article 6(1), point (f), or Article 9(2)", "gdpr") == {
        Reference("gdpr", "6"), Reference("gdpr", "9")
    }


def test_paragraphs_after_and_are_not_articles():
    assert refs("as referred to in Article 6(1) and (4)", "gdpr") == {Reference("gdpr", "6")}


def test_lists_and_short_ranges_are_expanded():
    assert refs("Articles 13 and 14", "gdpr") == {Reference("gdpr", "13"), Reference("gdpr", "14")}
    assert refs("the rights in Articles 15 to 18", "gdpr", article="12") == {
        Reference("gdpr", n) for n in ("15", "16", "17", "18")
    }


def test_another_law_is_resolved_or_dropped():
    assert refs("Article 9(1) of Regulation (EU) 2016/679", "eu_ai_act") == {Reference("gdpr", "9")}
    assert refs("Article 24 of Regulation (EU) No 1025/2012", "eu_ai_act") == set()
    assert refs("Article 10 of Directive (EU) 2016/680", "eu_ai_act") == set()


def test_ai_act_section_headings_are_not_references():
    assert refs("SECTION 3 Obligations of providers", "eu_ai_act") == set()


def test_bdsg_paragraphs_and_its_gdpr_articles():
    assert refs("nach § 26 Absatz 1 und §§ 32 bis 34", "bdsg") == {
        Reference("bdsg", n) for n in ("26", "32", "33", "34")
    }
    assert refs("im Sinne des Artikels 9 Absatz 1 der Verordnung (EU) 2016/679", "bdsg") == {Reference("gdpr", "9")}
    assert refs("abweichend von Artikel 13 Absatz 3", "bdsg") == {Reference("gdpr", "13")}


def test_bgb_sections_with_letters_and_lists():
    assert refs("under sections 636, 280, 281, 283 and 311a", "bgb", article="437") == {
        Reference("bgb", n) for n in ("636", "280", "281", "283", "311a")
    }
    assert refs("Article 229 of the Introductory Act to the Civil Code", "bgb") == set()


def test_a_provision_does_not_refer_to_itself_or_to_unknown_numbers():
    assert refs("paragraph 2 of this Article, and Article 6", "gdpr", article="6") == set()
    assert refs("Article 999", "gdpr") == set()


def test_of_that_directive_is_another_law():
    assert refs("the liability rules in Articles 12 to 15 of that Directive", "gdpr") == set()


def test_a_chain_names_its_law_once_at_the_end():
    text = "§ 2 Absatz 3 Satz 2, § 4 Absatz 3 und § 10 Absatz 1 Satz 1 Nummer 3 des Akkreditierungsstellengesetzes"
    assert refs(text, "bdsg", article="39") == set()


def test_of_followed_by_another_provision_stays_in_the_law():
    assert refs("based on Article 6(1) or point (a) of Article 9(2)", "gdpr") == {Reference("gdpr", "6"), Reference("gdpr", "9")}
    assert refs("sections 280 and 281, of section 437", "bgb", article="1") == {
        Reference("bgb", n) for n in ("280", "281", "437")
    }
    assert refs("section 280 of the present Code", "bgb", article="1") == {Reference("bgb", "280")}
    assert refs("section 90 of the Book 12 of the Social Code", "bgb") == set()
