"""The HTML conversion behind the law corpus. Headers it mangles never reach the chunker."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("tqdm")
pytest.importorskip("requests")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from download_assets import decode_html, html_to_plain_text  # noqa: E402


def test_headers_start_their_own_line_without_leading_spaces():
    html = '<a href="#">Inhalt</a><h3><span>§ 1</span>&#160;<span>Anwendungsbereich</span></h3><div><p>Text.</p></div>'
    lines = html_to_plain_text(html).split("\n")
    assert "§ 1 Anwendungsbereich" in lines


def test_entities_are_decoded():
    assert html_to_plain_text("<p>a&#160;b &sect; 2 &amp; c</p>") == "a b § 2 & c"


def test_head_is_removed():
    assert html_to_plain_text("<head><title>L_2016119EN.xml</title></head><p>Body</p>") == "Body"


def test_page_charset_is_respected():
    raw = '<meta charset="iso-8859-1"><p>Beschäftigung</p>'.encode("iso-8859-1")
    assert "Beschäftigung" in decode_html(raw)
