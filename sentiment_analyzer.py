# sentiment_analyzer.py

import os
import re
import logging
import aiohttp

logger = logging.getLogger("crypto_news_bot")

# HuggingFace Router — for LLaMA (chat completions)
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"

# HuggingFace Inference API — for BERT models (classification)
HF_INFERENCE_URL = "https://router.huggingface.co/hf-inference/models"
SCORE_EMOJI = {
    0-24: "🔴 Very Bearish",
    25-49: "🟠 Bearish",
    50-74: "🟡 Neutral",
    75-89: "🟢 Bullish",
    90-100: "🚀 Very Bullish"
}

# ==============================
# Few-shot examples from DB
# ==============================
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

# ==============================
# MODEL 1: LLaMA-3.1 (General LLM)
# Scores 1-5 directly via chat prompt
# ==============================
async def analyze_llama(title: str, pool=None) -> int:
    HF_API_KEY = os.getenv("HF_API_KEY")
    if not HF_API_KEY:
        logger.warning("⚠️ HF_API_KEY not set")
        return 3

    few_shot = await get_few_shot_examples(pool) if pool else ""

    system_prompt = (
    "You are a professional crypto market analyst.\n"
    "Based on this news headline, predict how the crypto market "
    "will move in the NEXT 15 MINUTES.\n\n"
    "Score scale:\n"
    "1 = Strong drop expected in 15 min\n"
    "2 = Slight drop expected in 15 min\n"
    "3 = No significant movement in 15 min\n"
    "4 = Slight rise expected in 15 min\n"
    "5 = Strong rise expected in 15 min\n\n"
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
            {"role": "user", "content": f'Headline: "{title}"\nScore:'}
        ],
        "max_tokens": 2,
        "temperature": 0.1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_ROUTER_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ LLaMA API error {resp.status}")
                    return 3
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                logger.info(f"🤖 LLaMA: '{raw}' | {title[:40]}")
                match = re.search(r"[1-5]", raw)
                return int(match.group()) if match else 3
    except Exception as e:
        logger.warning(f"⚠️ LLaMA failed: {e}")
        return 3

# ==============================
# MODEL 2: FinBERT (Finance-specific BERT)
# Trained on financial news — returns positive/negative/neutral
# Converts to 1-5 scale: positive=5, neutral=3, negative=1
# ==============================
async def analyze_finbert(title: str) -> int:
    HF_API_KEY = os.getenv("HF_API_KEY")
    if not HF_API_KEY:
        return 3

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": title,
        "options": {"wait_for_model": True}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HF_INFERENCE_URL}/ProsusAI/finbert",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ FinBERT API error {resp.status}")
                    return 3
                data = await resp.json()
                # Response: [[{"label": "positive", "score": 0.95}, ...]]
                if isinstance(data, list) and len(data) > 0:
                    results = data[0] if isinstance(data[0], list) else data
                    # Find highest scoring label
                    best = max(results, key=lambda x: x["score"])
                    label = best["label"].lower()
                    score = best["score"]
                    logger.info(f"📈 FinBERT: '{label}' ({score:.2f}) | {title[:40]}")
                    # Convert to 1-5
                    if label == "positive":
                        return 5 if score > 0.75 else 3
                    elif label == "negative":
                        return 1 if score > 0.75 else 3
                    else:
                        return 3
                return 3
    except Exception as e:
        logger.warning(f"⚠️ FinBERT failed: {e}")
        return 3

# ==============================
# MODEL 3: CryptoBERT (Crypto-specific BERT)
# Trained on 3.2M crypto social media posts
# Returns: Bullish / Neutral / Bearish
# Converts to 1-5 scale
# ==============================
async def analyze_cryptobert(title: str) -> int:
    HF_API_KEY = os.getenv("HF_API_KEY")
    if not HF_API_KEY:
        return 3

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": title,
        "options": {"wait_for_model": True}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HF_INFERENCE_URL}/ElKulako/cryptobert",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ CryptoBERT API error {resp.status}")
                    return 3
                data = await resp.json()
                # Response: [[{"label": "Bullish", "score": 0.87}, ...]]
                if isinstance(data, list) and len(data) > 0:
                    results = data[0] if isinstance(data[0], list) else data
                    best = max(results, key=lambda x: x["score"])
                    label = best["label"].lower()
                    score = best["score"]
                    logger.info(f"🪙 CryptoBERT: '{label}' ({score:.2f}) | {title[:40]}")
                    # Convert to 1-5
                    if label == "bullish":
                        return 5 if score > 0.75 else 3
                    elif label == "bearish":
                        return 1 if score > 0.75 else 3
                    else:
                        return 3
                return 3
    except Exception as e:
        logger.warning(f"⚠️ CryptoBERT failed: {e}")
        return 3

# ==============================
# MAJORITY VOTE — Run all 3 models
# Returns scores + hot verdict (2/3 must say hot)
# ==============================
async def analyze_all(title: str, pool=None) -> dict:
    """
    Runs all 3 models and uses majority vote to decide if news is hot.
    Returns a dict with all scores, verdict, and formatted text.
    """
    # Run all 3 models
    llama_score = await analyze_llama(title, pool)
    finbert_score = await analyze_finbert(title)
    cryptobert_score = await analyze_cryptobert(title)

    # Vote: is each model saying it's hot? (score >= 4)
    llama_hot = llama_score >= 4
    finbert_hot = finbert_score >= 4
    cryptobert_hot = cryptobert_score >= 4

    votes = [llama_hot, finbert_hot, cryptobert_hot]
    hot_count = sum(votes)
    is_hot = hot_count >= 2  # Majority vote: 2 out of 3

    # Average score
    avg_score = round((llama_score + finbert_score + cryptobert_score) / 3)

    logger.info(
        f"📊 Verdict: {'🔥 HOT' if is_hot else '❄️ NOT HOT'} ({hot_count}/3) | "
        f"LLaMA={llama_score} FinBERT={finbert_score} CryptoBERT={cryptobert_score} | {title[:40]}"
    )

    return {
        "is_hot": is_hot,
        "hot_count": hot_count,
        "avg_score": avg_score,
        "llama": llama_score,
        "finbert": finbert_score,
        "cryptobert": cryptobert_score,
    }

def format_scores(scores: dict) -> str:
    verdict = "🔥 Strong Move" if scores["is_hot"] else "➡️ No Move"
    return (
        f"🔮 15-min Market Prediction:\n"
        f"🤖 LLaMA-3.1:  {scores['llama']}/5 — {SCORE_EMOJI.get(scores['llama'], '🟡 Neutral')}\n"
        f"📈 FinBERT:    {scores['finbert']}/5 — {SCORE_EMOJI.get(scores['finbert'], '🟡 Neutral')}\n"
        f"🪙 CryptoBERT: {scores['cryptobert']}/5 — {SCORE_EMOJI.get(scores['cryptobert'], '🟡 Neutral')}\n"
        f"📊 Verdict: {verdict} ({scores['hot_count']}/3 models agree)"
    )

# Keep backward compatibility with old analyze_sentiment calls
async def analyze_sentiment(title: str, pool=None) -> int:
    return await analyze_llama(title, pool)

def format_signal(score: int) -> str:
    return f"📊 Signal: {score}/5 — {SCORE_EMOJI.get(score, '🟡 Neutral')}"