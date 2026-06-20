"""Document text extraction with OCR fallback — Phase 10B."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import settings


@dataclass
class ParseResult:
    text: str
    ocr_used: bool = False


def _ocr_pdf_pages(file_path: str | Path) -> str:
    """Rasterize PDF pages and run Tesseract OCR."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("OCR dependencies missing: pip install pytesseract pdf2image") from exc

    pages = convert_from_path(str(file_path), dpi=200)
    parts: list[str] = []
    for img in pages:
        text = pytesseract.image_to_string(img, lang="eng+deu")
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def parse_pdf_ex(file_path: str | Path) -> ParseResult:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ParseResult(text="Error: pypdf not installed. Run pip install pypdf")

    reader = PdfReader(str(file_path))
    text_parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_parts.append(t)
    text = "\n\n".join(text_parts).strip()
    ocr_used = False

    min_expected = settings.ocr_min_chars_per_page * max(len(reader.pages), 1)
    if settings.ocr_enabled and len(text) < min_expected:
        try:
            ocr_text = _ocr_pdf_pages(file_path)
            if len(ocr_text) > len(text):
                return ParseResult(text=ocr_text, ocr_used=True)
        except Exception as exc:
            if not text:
                raise ValueError(f"PDF text extraction failed and OCR unavailable: {exc}") from exc
    return ParseResult(text=text, ocr_used=ocr_used)


def parse_pdf(file_path: str | Path) -> str:
    return parse_pdf_ex(file_path).text


def parse_docx(file_path: str | Path) -> str:
    try:
        import docx
    except ImportError:
        return "Error: python-docx not installed. Run pip install python-docx"

    doc = docx.Document(str(file_path))
    return "\n".join([p.text for p in doc.paragraphs])


def parse_eml(file_path: str | Path) -> str:
    import email
    from email import policy

    raw = Path(file_path).read_bytes()
    msg = email.message_from_bytes(raw, policy=policy.default)
    parts: list[str] = []
    if msg.get("Subject"):
        parts.append(f"Subject: {msg['Subject']}")
    if msg.get("From"):
        parts.append(f"From: {msg['From']}")
    if msg.get("To"):
        parts.append(f"To: {msg['To']}")
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        content = body.get_content()
        if isinstance(content, str):
            parts.append(content)
    return "\n\n".join(parts).strip()


def parse_msg(file_path: str | Path) -> str:
    try:
        import extract_msg
    except ImportError as exc:
        raise RuntimeError("MSG parsing requires extract-msg: pip install extract-msg") from exc

    msg = extract_msg.Message(str(file_path))
    parts: list[str] = []
    if msg.subject:
        parts.append(f"Subject: {msg.subject}")
    if msg.sender:
        parts.append(f"From: {msg.sender}")
    if msg.to:
        parts.append(f"To: {msg.to}")
    if msg.body:
        parts.append(msg.body)
    msg.close()
    return "\n\n".join(parts).strip()


def parse_document_ex(file_path: str | Path, filename: str) -> ParseResult:
    path_str = str(file_path).lower()
    name_lower = (filename or "").lower()
    if path_str.endswith(".pdf") or name_lower.endswith(".pdf"):
        return parse_pdf_ex(file_path)
    if path_str.endswith(".docx") or name_lower.endswith(".docx"):
        return ParseResult(text=parse_docx(file_path))
    if path_str.endswith(".txt") or name_lower.endswith(".txt"):
        return ParseResult(text=Path(file_path).read_text(encoding="utf-8", errors="replace"))
    if path_str.endswith(".eml") or name_lower.endswith(".eml"):
        return ParseResult(text=parse_eml(file_path))
    if path_str.endswith(".msg") or name_lower.endswith(".msg"):
        return ParseResult(text=parse_msg(file_path))
    if path_str.endswith(".md") or name_lower.endswith(".md"):
        return ParseResult(text=Path(file_path).read_text(encoding="utf-8", errors="replace"))
    raise ValueError(f"Unsupported file type: {filename}")


def parse_document(file_path: str | Path, filename: str) -> str:
    return parse_document_ex(file_path, filename).text
