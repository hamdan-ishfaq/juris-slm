from __future__ import annotations
import re

def hierarchical_chunk(text: str) -> list[dict]:
    """
    Implements a simple Parent-Child chunking strategy.
    Splits document by major sections (Parent) and then by paragraphs (Child).
    Returns a list of dicts: {"content": child_text, "parent_content": parent_text}
    """
    # A naive legal document splitter: assuming major sections look like "Article X" or "1. Title"
    # For a robust implementation, this would use a more sophisticated parser.
    # Here we split by "Article " or "

1. ", etc.
    
    # Split into sections (Parents)
    section_pattern = re.compile(r"\n(?=Article \d+|Section \d+|[1-9]\.\s+[A-Z])", re.IGNORECASE)
    sections = section_pattern.split(text)
    
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Split section into paragraphs (Children)
        paragraphs = re.split(r"\n\n+", section)
        for para in paragraphs:
            para = para.strip()
            if len(para) > 50:  # Ignore very short fragments
                chunks.append({
                    "content": para,            # Child goes to embedding
                    "parent_content": section   # Parent goes to LLM context
                })
    return chunks
