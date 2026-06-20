"""Phase 10B — document parser and OCR fallback tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.document_parser import parse_pdf


@pytest.mark.unit
def test_parse_pdf_uses_ocr_when_text_sparse(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page, mock_page]

    with (
        patch.dict("sys.modules", {"pypdf": MagicMock(PdfReader=MagicMock(return_value=mock_reader))}),
        patch("services.document_parser.settings") as mock_settings,
        patch("services.document_parser._ocr_pdf_pages", return_value="CONFIDENTIALITY clause scanned text") as ocr,
    ):
        mock_settings.ocr_enabled = True
        mock_settings.ocr_min_chars_per_page = 50
        out = parse_pdf(pdf)
    assert "CONFIDENTIALITY" in out
    ocr.assert_called_once()


@pytest.mark.unit
def test_parse_pdf_native_text_skips_ocr(tmp_path):
    pdf = tmp_path / "native.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "A" * 200
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with (
        patch.dict("sys.modules", {"pypdf": MagicMock(PdfReader=MagicMock(return_value=mock_reader))}),
        patch("services.document_parser.settings") as mock_settings,
        patch("services.document_parser._ocr_pdf_pages") as ocr,
    ):
        mock_settings.ocr_enabled = True
        mock_settings.ocr_min_chars_per_page = 50
        out = parse_pdf(pdf)
    assert len(out) >= 200
    ocr.assert_not_called()


@pytest.mark.unit
def test_parse_eml_extracts_body(tmp_path):
    eml = tmp_path / "mail.eml"
    eml.write_bytes(
        b"From: a@b.com\r\nTo: c@d.com\r\nSubject: Test\r\n\r\nBody line one."
    )
    from services.document_parser import parse_document_ex

    result = parse_document_ex(eml, "mail.eml")
    assert "Body line one" in result.text
    assert result.ocr_used is False
