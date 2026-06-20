"""Export Q&A sessions for counsel-facing audit packs."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"_([^_]+)_", r"\1", s)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*[-*+]\s+", "• ", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*\d+\.\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _pdf_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _strip_markdown(text).replace("\r\n", "\n").replace("\t", " ")
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    # Break very long tokens (URLs, hashes) so fpdf can wrap
    cleaned = re.sub(r"(\S{55,})", lambda m: " ".join(m.group(1)[i : i + 40] for i in range(0, len(m.group(1)), 40)), cleaned)
    return cleaned.encode("latin-1", errors="replace").decode("latin-1")


def _brand_logo_path() -> Path | None:
    for candidate in (
        Path(__file__).resolve().parent.parent / "data" / "branding" / "logo.png",
        Path(__file__).resolve().parents[2] / "data" / "branding" / "logo.png",
    ):
        if candidate.is_file():
            return candidate
    return None


class ExportMetadata:
    def __init__(
        self,
        *,
        user_email: str,
        matter_name: str,
        document_name: str,
        prepared_for: str,
        matter_reference: str,
        author_name: str,
        firm_name: str = "JurisGuard",
        classification: str = "Attorney work product — confidential",
        exported_at: datetime | None = None,
    ):
        self.user_email = user_email.strip() or user_email
        self.matter_name = matter_name.strip() or "Unspecified matter"
        self.document_name = document_name.strip() or "General research"
        self.prepared_for = prepared_for.strip() or user_email
        self.matter_reference = matter_reference.strip() or "N/A"
        self.author_name = author_name.strip() or user_email
        self.firm_name = firm_name.strip() or "JurisGuard"
        self.classification = classification.strip()
        self.exported_at = exported_at or datetime.now(timezone.utc)


class _LegalPdf:
    """Counsel-facing research memorandum layout (one query per page)."""

    MARGIN = 22

    def __init__(self, *, brand_name: str = "JurisGuard", accent_rgb: tuple[int, int, int] = (13, 148, 136)):
        from fpdf import FPDF

        brand = brand_name
        accent = accent_rgb
        margin = self.MARGIN

        class _Doc(FPDF):
            def header(self):
                if self.page_no() == 1:
                    return
                self.set_font("Helvetica", style="I", size=8)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, _pdf_text(f"{brand} — Research Memorandum"), align="L")
                self.ln(8)

            def footer(self):
                self.set_y(-14)
                self.set_font("Helvetica", style="I", size=8)
                self.set_text_color(120, 120, 120)
                self.cell(0, 6, _pdf_text(f"Confidential — {brand} — Page {self.page_no()}/{{nb}}"), align="C")

        self.brand = brand_name
        self.accent = accent_rgb
        self.pdf = _Doc()
        self.pdf.set_auto_page_break(auto=True, margin=margin)
        self.pdf.set_margins(margin, margin, margin)
        self.pdf.alias_nb_pages()

    def _w(self) -> float:
        return self.pdf.epw

    def _write_paragraphs(self, text: str, *, size: int = 10, style: str = "", line_h: float = 5.2) -> None:
        pdf = self.pdf
        w = self._w()
        pdf.set_x(self.MARGIN)
        pdf.set_font("Helvetica", style=style, size=size)
        pdf.set_text_color(0, 0, 0)
        blocks = [b.strip() for b in _pdf_text(text).split("\n\n") if b.strip()]
        if not blocks:
            pdf.multi_cell(w, line_h, "—")
            return
        for block in blocks:
            pdf.set_x(self.MARGIN)
            lines = block.split("\n")
            for line in lines:
                pdf.set_x(self.MARGIN)
                pdf.multi_cell(w, line_h, line.strip() or " ")
            pdf.ln(2)

    def _meta_row(self, label: str, value: str) -> None:
        pdf = self.pdf
        w = self._w()
        label_w = w * 0.34
        value_w = w * 0.66
        y0 = pdf.get_y()
        pdf.set_font("Helvetica", style="B", size=9)
        pdf.set_x(self.MARGIN)
        pdf.multi_cell(label_w, 5.5, _pdf_text(label), border="LTR")
        y1 = pdf.get_y()
        pdf.set_xy(self.MARGIN + label_w, y0)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(value_w, 5.5, _pdf_text(value), border="TR")
        pdf.set_y(max(y1, pdf.get_y()))

    def add_cover(self, meta: ExportMetadata, *, title: str, subtitle: str) -> None:
        pdf = self.pdf
        pdf.add_page()
        logo = _brand_logo_path()
        if logo:
            try:
                pdf.image(str(logo), x=self.MARGIN, y=16, h=16)
                pdf.ln(24)
            except Exception:
                pdf.ln(4)
        pdf.set_font("Helvetica", style="B", size=14)
        pdf.set_text_color(*self.accent)
        pdf.cell(0, 8, _pdf_text(meta.firm_name), ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)
        pdf.set_font("Helvetica", style="B", size=20)
        pdf.multi_cell(self._w(), 10, _pdf_text(title))
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)
        pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(self._w(), 6, _pdf_text(subtitle))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(10)

        ts = meta.exported_at.strftime("%d %B %Y, %H:%M UTC")
        pdf.set_fill_color(245, 247, 250)
        pdf.set_font("Helvetica", style="B", size=10)
        pdf.set_x(self.MARGIN)
        pdf.cell(self._w(), 7, "Matter information", ln=True, fill=True)
        pdf.ln(1)
        for label, value in [
            ("Prepared for", meta.prepared_for),
            ("Author", meta.author_name),
            ("Matter / case name", meta.matter_name),
            ("Matter reference", meta.matter_reference),
            ("Document reviewed", meta.document_name),
            ("Export date", ts),
            ("Classification", meta.classification),
        ]:
            self._meta_row(label, value)
        pdf.ln(6)
        pdf.set_font("Helvetica", style="I", size=9)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(self._w(), 5, _pdf_text(
            "This memorandum summarizes AI-assisted legal research with cited authorities. "
            "It is intended for internal review and must be independently verified by qualified counsel."
        ))
        pdf.set_text_color(0, 0, 0)

    def add_query_page(
        self,
        *,
        index: int,
        total: int,
        meta: ExportMetadata,
        question: str,
        answer: str,
        sources: list[dict] | None = None,
    ) -> None:
        pdf = self.pdf
        pdf.add_page()

        # Page header strip
        pdf.set_fill_color(*self.accent)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", style="B", size=9)
        pdf.cell(self._w() * 0.5, 7, _pdf_text(f"Query {index} of {total}"), fill=True)
        pdf.cell(self._w() * 0.5, 7, _pdf_text(meta.matter_reference[:40]), fill=True, align="R", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

        pdf.set_font("Helvetica", style="B", size=11)
        pdf.set_text_color(*self.accent)
        pdf.cell(0, 6, "QUESTION PRESENTED", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_x(self.MARGIN)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(self._w(), 5.5, _pdf_text(question), fill=True)
        pdf.ln(6)

        pdf.set_font("Helvetica", style="B", size=11)
        pdf.set_text_color(*self.accent)
        pdf.cell(0, 6, "ANALYSIS", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        self._write_paragraphs(answer, size=10, line_h=5.4)

        srcs = sources or []
        if srcs:
            pdf.ln(4)
            pdf.set_font("Helvetica", style="B", size=11)
            pdf.set_text_color(*self.accent)
            pdf.cell(0, 6, "AUTHORITIES CITED", ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)
            pdf.set_font("Helvetica", size=9)
            for i, s in enumerate(srcs[:15], 1):
                label = s.get("label") or s.get("source") or s.get("title") or "Source"
                excerpt = (s.get("snippet") or s.get("content") or "")[:220]
                score = s.get("rerank_score")
                line = f"{i}. {label}"
                if isinstance(score, (int, float)):
                    line += f"  [relevance {score:.2f}]"
                pdf.set_x(self.MARGIN)
                pdf.multi_cell(self._w(), 4.5, _pdf_text(line))
                if excerpt:
                    pdf.set_x(self.MARGIN + 4)
                    pdf.set_font("Helvetica", style="I", size=8)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(self._w() - 4, 4, _pdf_text(excerpt))
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Helvetica", size=9)

    def add_clause_table(self, rows: list[dict[str, str]]) -> None:
        if not rows:
            return
        pdf = self.pdf
        w = self._w()
        col1, col2 = w * 0.30, w * 0.70
        pdf.set_font("Helvetica", style="B", size=9)
        pdf.set_fill_color(245, 247, 250)
        pdf.cell(col1, 7, "Clause / topic", border=1, fill=True)
        pdf.cell(col2, 7, "Summary", border=1, fill=True, ln=True)
        pdf.set_font("Helvetica", size=9)
        for row in rows[:25]:
            y0 = pdf.get_y()
            pdf.set_x(self.MARGIN)
            pdf.multi_cell(col1, 5, _pdf_text(str(row.get("topic", "—"))[:80]), border="LTR")
            y1 = pdf.get_y()
            pdf.set_xy(self.MARGIN + col1, y0)
            pdf.multi_cell(col2, 5, _pdf_text(str(row.get("summary", "—"))[:400]), border="TR")
            pdf.set_y(max(y1, pdf.get_y()))

    def bytes_out(self) -> bytes:
        out = self.pdf.output()
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return str(out).encode("latin-1", errors="replace")


def _meta_from_kwargs(**kwargs: Any) -> ExportMetadata:
    return ExportMetadata(
        user_email=kwargs.get("user_email") or "",
        matter_name=kwargs.get("matter_name") or "Unspecified matter",
        document_name=kwargs.get("document_name") or kwargs.get("filename") or "General research",
        prepared_for=kwargs.get("prepared_for") or kwargs.get("user_email") or "",
        matter_reference=kwargs.get("matter_reference") or "N/A",
        author_name=kwargs.get("author_name") or kwargs.get("user_email") or "",
        firm_name=kwargs.get("firm_name") or kwargs.get("brand_name") or "JurisGuard",
        classification=kwargs.get("classification") or "Attorney work product — confidential",
    )


def build_audit_export(
    *,
    user_email: str,
    matter_name: str,
    items: list[dict[str, Any]],
) -> bytes:
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user_email,
        "matter": matter_name,
        "items": items,
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def build_pdf_export(
    *,
    user_email: str,
    matter_name: str,
    items: list[dict[str, Any]],
    document_name: str | None = None,
    brand_name: str = "JurisGuard",
    report_title: str = "Legal Research Memorandum",
    prepared_for: str | None = None,
    matter_reference: str | None = None,
    author_name: str | None = None,
    firm_name: str | None = None,
) -> bytes:
    meta = _meta_from_kwargs(
        user_email=user_email,
        matter_name=matter_name,
        document_name=document_name,
        prepared_for=prepared_for,
        matter_reference=matter_reference,
        author_name=author_name,
        firm_name=firm_name or brand_name,
        brand_name=brand_name,
    )
    doc = _LegalPdf(brand_name=meta.firm_name)
    doc.add_cover(
        meta,
        title=report_title,
        subtitle="Structured research record with cited authorities for matter review.",
    )
    if not items:
        doc.add_query_page(index=1, total=1, meta=meta, question="No queries exported.", answer="No research items were included.", sources=[])
    else:
        total = len(items)
        for i, item in enumerate(items, 1):
            doc.add_query_page(
                index=i,
                total=total,
                meta=meta,
                question=(item.get("question") or "—")[:2000],
                answer=(item.get("answer") or "—")[:20000],
                sources=item.get("sources") or [],
            )
    return doc.bytes_out()


def build_analyze_pdf(
    *,
    user_email: str,
    matter_name: str,
    filename: str,
    question: str,
    answer: str,
    structured: dict | None = None,
    risk: dict | None = None,
    brand_name: str = "JurisGuard",
    prepared_for: str | None = None,
    matter_reference: str | None = None,
    author_name: str | None = None,
    firm_name: str | None = None,
) -> bytes:
    meta = _meta_from_kwargs(
        user_email=user_email,
        matter_name=matter_name,
        document_name=filename,
        prepared_for=prepared_for,
        matter_reference=matter_reference,
        author_name=author_name,
        firm_name=firm_name or brand_name,
    )
    doc = _LegalPdf(brand_name=meta.firm_name)
    doc.add_cover(meta, title="Contract Analysis Memorandum", subtitle="Clause review and regulatory risk assessment.")
    if risk:
        doc.pdf.add_page()
        doc.pdf.set_font("Helvetica", style="B", size=11)
        doc.pdf.set_text_color(*doc.accent)
        doc.pdf.cell(0, 6, "RISK ASSESSMENT", ln=True)
        doc.pdf.set_text_color(0, 0, 0)
        doc.pdf.ln(2)
        doc._write_paragraphs(f"Overall risk level: {risk.get('risk_level', '—')}")
    clauses = (structured or {}).get("clauses") or []
    if clauses:
        doc.pdf.add_page()
        doc.pdf.set_font("Helvetica", style="B", size=11)
        doc.pdf.set_text_color(*doc.accent)
        doc.pdf.cell(0, 6, "CLAUSE SUMMARY", ln=True)
        doc.pdf.set_text_color(0, 0, 0)
        doc.pdf.ln(3)
        doc.add_clause_table(clauses)
    doc.add_query_page(index=1, total=1, meta=meta, question=question, answer=answer, sources=[])
    return doc.bytes_out()


def build_markdown_export(
    *,
    user_email: str,
    matter_name: str,
    items: list[dict[str, Any]],
) -> str:
    lines = [
        "# JurisGuard Audit Export",
        "",
        f"- **User:** {user_email}",
        f"- **Matter:** {matter_name}",
        f"- **Exported:** {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for i, item in enumerate(items, 1):
        lines.append(f"## Q{i}: {_strip_markdown(item.get('question', ''))}")
        lines.append("")
        lines.append(_strip_markdown(item.get("answer", "")))
        lines.append("")
        sources = item.get("sources") or []
        if sources:
            lines.append("### Sources")
            for s in sources:
                score = s.get("rerank_score")
                suffix = f" (score {score:.2f})" if score is not None else ""
                lines.append(f"- {s.get('label', s.get('source', 'source'))}{suffix}")
        lines.append("")
    return "\n".join(lines)


def build_analyze_report_markdown(*, filename: str, structured: dict | None, risk: dict | None, answer: str) -> str:
    lines = [f"# Document analysis — {filename}", ""]
    if risk:
        lines.append(f"**Risk level:** {risk.get('risk_level', '—')}")
        lines.append("")
    if structured and structured.get("clauses"):
        lines.append("## Clauses")
        lines.append("| Topic | Summary |")
        lines.append("| --- | --- |")
        for row in structured["clauses"]:
            lines.append(f"| {row.get('topic', '—')} | {row.get('summary', '—')} |")
        lines.append("")
    lines.append("## Narrative")
    lines.append(_strip_markdown(answer or "—"))
    return "\n".join(lines)


def build_compare_report_markdown(*, filename: str, comparison: str, sources: list[dict] | None = None) -> str:
    lines = [f"# Regulatory comparison — {filename}", "", _strip_markdown(comparison or "—"), ""]
    if sources:
        lines.append("## Sources")
        for s in sources:
            lines.append(f"- {s.get('label', s.get('source', 'source'))}")
    return "\n".join(lines)
