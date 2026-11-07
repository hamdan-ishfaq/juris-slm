from __future__ import annotations
from services.llm_client import generate_aux

HYDE_SYSTEM_PROMPT = """You are a legal expert. 
Given the user's legal question, write a hypothetical legal contract snippet or law article that would directly answer it.
Do not provide explanations or reasoning. ONLY output the hypothetical text, written in formal legal language (legalese).
Keep it under 150 words."""

def build_hyde_prompt(question: str) -> str:
    return f"""<|system|>
{HYDE_SYSTEM_PROMPT}
<|end|>
<|user|>
Question: {question}
<|end|>
<|assistant|>
"""

async def generate_hypothetical_document(question: str) -> str:
    """
    Uses the LLM to generate a hypothetical answer to the query.
    This text will be embedded and used for vector search to improve recall.
    """
    prompt = build_hyde_prompt(question)
    try:
        hypothetical_doc = await generate_aux(prompt, task="hyde")
        return hypothetical_doc
    except Exception as e:
        print(f"HyDE generation failed: {e}")
        # Fallback to the original question if generation fails
        return question
