# sentiment_analyzer.py
# Uses LLaMA-3 8B via Hugging Face Inference API
# Dynamically improves scores using user feedback stored in PostgreSQL

import os
import re
import logging
import aiohttp

logger = logging.getLogger("crypto_news_bot")

HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

SCORE_EMOJI = {
    1: "🔴 Very Bearish",
    2: "🟠 Bearish",
    3: "🟡 Neutral",
    4: "🟢 Bullish",
    5: "🚀 Very Bullish"
}

# ==============================
# FETCH FEW-SHOT EXAMPLES FROM DB
# ==============================
async def get_few_shot_examples(pool, limit: int = 5) -> str:
    """
    Pull top-rated and bottom-rated news from feedback table
    to use as few-shot examples in the prompt.
    """
    if pool is None:
        return ""

    try:
        async with pool.acquire() as conn:
            # Get highest and lowest rated news with their AI scores
            rows = await conn.fetch("""
                SELECT s.title, s.sentiment AS ai_score, 
                       ROUND(AVG(f.rating)) AS user_score
                FROM sent_news s
                JOIN feedback f ON s.news_id = f.news_id
                WHERE s.title IS NOT NULL
                GROUP BY s.news_id, s.title, s.sentiment
                HAVING COUNT(f.rating) >= 2
                ORDER BY ABS(AVG(f.rating) - s.sentiment) DESC
                LIMIT %s
            """ % limit)

            if not rows:
                return ""

            examples = "\n\nExamples based on community feedback:\n"
            for row in rows:
                examples += (
                    f'- "{row["title"]}"\n'
                    f'  → Community rated: {int(row["user_score"])}/5\n'
                )
            return examples

    except Exception as e:
        logger.warning(f"⚠️ Could not fetch few-shot examples: {e}")
        return ""


# ==============================
# ANALYZE SENTIMENT
# ==============================
async def analyze_sentiment(title: str, pool=None) -> int:
    """
    Analyze crypto news sentiment using LLaMA-3 8B via HuggingFace API.
    Uses dynamic few-shot examples from user feedback in PostgreSQL.
    Returns integer score 1-5.
    """
    if not HF_API_KEY:
        logger.warning("⚠️ HF_API_KEY not set, defaulting to 3 (Neutral)")
        return 3

    # Get few-shot examples from DB
    few_shot = await get_few_shot_examples(pool) if pool else ""

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a professional crypto market analyst. Analyze the sentiment of crypto news headlines.

Score scale:
1 = Very Bearish (strongly negative for crypto prices)
2 = Bearish (somewhat negative)
3 = Neutral (no clear market impact)
4 = Bullish (somewhat positive)
5 = Very Bullish (strongly positive for crypto prices)

Rules:
- Reply with ONLY a single digit: 1, 2, 3, 4, or 5
- No explanation, no punctuation, just the digit
- Consider: regulatory tone, adoption signals, macro factors, market sentiment
{few_shot}<|eot_id|><|start_header_id|>user<|end_header_id|>
News headline: "{title}"

Score:<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 2,
            "temperature": 0.1,
            "return_full_text": False
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.warning(f"⚠️ HF API error {resp.status}: {error}")
                    return 3

                data = await resp.json()
                raw = data[0]["generated_text"].strip()

                # Extract first digit found
                match = re.search(r"[1-5]", raw)
                if match:
                    return int(match.group())
                else:
                    logger.warning(f"⚠️ Could not parse score from: '{raw}'")
                    return 3

    except Exception as e:
        logger.warning(f"⚠️ Sentiment analysis failed for '{title}': {e}")
        return 3  # default to neutral


# ==============================
# FORMAT SIGNAL
# ==============================
def format_signal(score: int) -> str:
    """Return formatted signal string for Telegram message."""
    return f"📊 Signal: {score}/5 — {SCORE_EMOJI.get(score, '🟡 Neutral')}"