from __future__ import annotations
import io
from pathlib import Path

def parse_pdf(file_path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "Error: pypdf not installed. Run pip install pypdf"
    
    reader = PdfReader(str(file_path))
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n\n".join(text)

def parse_docx(file_path: str | Path) -> str:
    try:
        import docx
    except ImportError:
        return "Error: python-docx not installed. Run pip install python-docx"
    
    doc = docx.Document(str(file_path))
    return "\n".join([p.text for p in doc.paragraphs])

def parse_document(file_path: str | Path, filename: str) -> str:
    path_str = str(file_path).lower()
    if path_str.endswith(".pdf"):
        return parse_pdf(file_path)
    elif path_str.endswith(".docx"):
        return parse_docx(file_path)
    elif path_str.endswith(".txt"):
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {filename}")
