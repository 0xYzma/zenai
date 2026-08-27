"""
Conversation Compressor — §5.4

Generates a running session summary (1-2 sentences) after each turn.
Updated cheaply alongside the main answer.
"""
import httpx
import json
from app.core.config import get_settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SUMMARY_PROMPT = """You are a conversation compressor for a business analytics tool.

Given the current session summary and the latest question + answer, produce an updated 1-2 sentence summary of what the user is currently analyzing.

RULES:
- Keep it under 30 words
- Focus on the topic/entity being analyzed, not the technical details
- Example: "User is analyzing Tuesday's revenue drop across stores" or "User is comparing monthly refund rates by category"

Current summary: {current_summary}

Latest question: {question}
Short answer: {short_answer}

Updated summary (just the text, no quotes):"""


async def generate_summary(current_summary: str, question: str, short_answer: str) -> str:
    """
    Generate an updated session summary from the latest turn.
    Returns 1-2 sentence summary.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        # Fallback: simple summary without LLM
        return _fallback_summary(current_summary, question)

    prompt = SUMMARY_PROMPT.format(
        current_summary=current_summary or "(new session)",
        question=question,
        short_answer=short_answer[:300],
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GEMINI_API_URL,
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 60,
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0]["content"]["parts"][0]["text"].strip()
                    # Clean up quotes
                    text = text.strip('"').strip("'")
                    return text[:200]

        return _fallback_summary(current_summary, question)

    except Exception:
        return _fallback_summary(current_summary, question)


def _fallback_summary(current_summary: str, question: str) -> str:
    """Simple fallback summary without LLM."""
    if not current_summary:
        return f"User is asking about: {question[:100]}"
    return current_summary
