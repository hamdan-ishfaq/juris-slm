# utils.py
# src/utils.py - Shared utilities
import re
from typing import List
from pathlib import Path
import torch

def smart_chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Break text into chunks of roughly chunk_size chars, prefer sentence boundaries.
    """
    if not text:
        return []
    sentences = re.split(r'(?<=[\.\?\!]\s)', text)  # keep punctuation
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) <= chunk_size:
            current += s
        else:
            if current:
                chunks.append(current.strip())
            # if sentence is larger than chunk_size, split it
            if len(s) > chunk_size:
                start = 0
                while start < len(s):
                    sub = s[start:start+chunk_size]
                    chunks.append(sub.strip())
                    start += (chunk_size - overlap)
                current = ""
            else:
                current = s
    if current:
        chunks.append(current.strip())
    
    # Apply overlap: each chunk should include the last 'overlap' chars from previous chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]  # First chunk stays as-is
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            curr_chunk = chunks[i]
            # Prepend last 'overlap' chars from previous chunk to current
            overlap_text = prev_chunk[-overlap:] if len(prev_chunk) >= overlap else prev_chunk
            overlapped.append(overlap_text + " " + curr_chunk)
        chunks = overlapped
    
    return chunks

def get_gpu_status() -> str:
    if torch.cuda.is_available():
        mem = torch.cuda.memory_allocated() / 1024**3
        return f"{mem:.2f} GB"
    return "N/A"