import json
import logging

import openai

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at evaluating used electronics for resale. You receive Avito listings and must quickly assess them.

Rules:
1. Determine the real condition from the description
2. List ALL defects and issues mentioned or implied
3. Watch for red flags (suspiciously cheap, iCloud lock, stolen, no photos, vague description, "as-is" language)
4. Rate the item 1-10 (10 = perfect mint condition, 1 = junk/parts only)
5. Calculate estimated profit based on the market price provided

CRITICAL: Respond ONLY with valid JSON, no markdown, no code blocks, no extra text:
{
  "condition": "mint" | "good" | "defects" | "parts_only",
  "defects": ["defect1", "defect2"],
  "red_flags": ["flag1", "flag2"],
  "score": 7,
  "estimated_sell_price": 55000,
  "estimated_profit": 8000,
  "recommendation": "BUY" | "CHECK" | "SKIP",
  "comment": "Brief 1-2 sentence summary in Russian"
}

The "comment" field MUST be in Russian — it will be shown directly to the user in Telegram.
If defects list is empty, use [].
If red_flags list is empty, use [].
"""

USER_PROMPT_TEMPLATE = """Product: {item_name}
Market resale price: {market_price}\u20bd
Listing price: {ad_price}\u20bd
City: {city}

Listing title: {ad_title}

Seller's description:
{ad_description}

Item attributes: {ad_params}"""


async def analyze_ad(item: dict, ad_data: dict) -> dict | None:
    """Send listing to GPT-4o-mini for analysis. Returns parsed verdict dict or None."""
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        item_name=item["name"],
        market_price=item["market_price"],
        ad_price=ad_data.get("price", 0),
        city=ad_data.get("city", "Unknown"),
        ad_title=ad_data.get("title", ""),
        ad_description=ad_data.get("description", "No description"),
        ad_params=ad_data.get("params_str", "N/A"),
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        verdict = json.loads(content)
        logger.info(
            "AI verdict for ad %s: %s (score %s)",
            ad_data.get("ad_id", "?"),
            verdict.get("recommendation"),
            verdict.get("score"),
        )
        return verdict

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from GPT: %s", e)
        return None
    except openai.APIError as e:
        logger.error("OpenAI API error: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error in AI analysis: %s", e)
        return None
