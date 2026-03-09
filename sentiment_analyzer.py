# sentiment_analyzer.py

import os
import re
import logging
import aiohttp

logger = logging.getLogger("crypto_news_bot")

HF_API_KEY = os.getenv("HF_API_KEY")
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL   = "meta-llama/Llama-3.1-8B-Instruct:cerebras"

SCORE_EMOJI = {
    1: "🔴 Very Bearish",
    2: "🟠 Bearish",
    3: "🟡 Neutral",
    4: "🟢 Bullish",
    5: "🚀 Very Bullish"
}

async def get_few_shot_examples(pool, limit: int = 5) -> str:
    if pool is None:
        return ""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT s.title, ROUND(AVG(f.rating)) AS user_score
                FROM sent_news s
                JOIN feedback f ON s.news_id = f.news_id
                WHERE s.title IS NOT NULL
                GROUP BY s.news_id, s.title
                HAVING COUNT(f.rating) >= 2
                ORDER BY ABS(AVG(f.rating) - s.sentiment) DESC
                LIMIT $1
            """, limit)
            if not rows:
                return ""
            examples = "\n\nExamples based on community feedback:\n"
            for row in rows:
                examples += f'- "{row["title"]}"\n  → Community rated: {int(row["user_score"])}/5\n'
            return examples
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch few-shot examples: {e}")
        return ""

async def analyze_sentiment(title: str, pool=None) -> int:
    if not HF_API_KEY:
        logger.warning("⚠️ HF_API_KEY not set, defaulting to 3")
        return 3

    few_shot = await get_few_shot_examples(pool) if pool else ""

    system_prompt = (
        "You are a professional crypto market analyst.\n"
        "Analyze the sentiment of crypto news headlines.\n\n"
        "Score scale:\n"
        "1 = Very Bearish\n"
        "2 = Bearish\n"
        "3 = Neutral\n"
        "4 = Bullish\n"
        "5 = Very Bullish\n\n"
        "Reply with ONLY a single digit: 1, 2, 3, 4, or 5. Nothing else."
        + few_shot
    )

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Llama-3.1-8B-Instruct:cerebras",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f'Headline: "{title}"\nScore:'}
        ],
        "max_tokens": 2,
        "temperature": 0.1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                HF_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.warning(f"⚠️ HF API error {resp.status}: {error}")
                    return 3
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                logger.info(f"🤖 LLM: '{raw}' for: {title[:50]}")
                match = re.search(r"[1-5]", raw)
                return int(match.group()) if match else 3
    except Exception as e:
        logger.warning(f"⚠️ Sentiment failed: {e}")
        return 3

def format_signal(score: int) -> str:
    return f"📊 Signal: {score}/5 — {SCORE_EMOJI.get(score, '🟡 Neutral')}"
