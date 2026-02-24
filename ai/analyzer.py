import json
import logging

import openai

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — опытный перекупщик Apple-техники в России. Ты занимаешься скупкой б/у iPhone, MacBook, iPad, AirPods и Apple Watch на Авито и перепродажей с прибылью. У тебя 5+ лет опыта, ты знаешь рынок, цены, все схемы мошенников и типичные дефекты.

## ТВОЯ ЗАДАЧА
Проанализировать объявление с Авито и дать экспертную оценку: стоит ли покупать этот товар для перепродажи.

## КРИТИЧЕСКИЕ ПРАВИЛА

### Мгновенный отказ (score: 0, recommendation: SKIP):
- Копии, реплики, подделки — любое упоминание "копия", "реплика", "версия", "1 в 1", "Android", "не оригинал", "обновлённый чип"
- Восстановленные на коленке (refurbished не из Apple) — "восстановленный", "пересобранный", "реф"
- iCloud lock, залоченные — "iCloud заблокирован", "привязан к аккаунту", "нет Apple ID"
- На запчасти — "на запчасти", "донор", "не включается"
- Описание написано КАПСом или с подозрительной заменой букв (л→l, а→a, о→0) — это обход фильтров Авито, признак мошенника

### На что обращать внимание в описании:
1. **Состояние батареи (АКБ)** — идеал >87%, хорошо 80-87%, плохо <80%. Если не указано — это красный флаг, скорее всего АКБ убитый
2. **Экран** — оригинал или замена? Упоминания: "экран менялся", "не оригинальный дисплей", "True Tone не работает" — снижают цену на 3-8к
3. **Face ID / Touch ID** — работает ли? Если нет — минус 5-15к от цены
4. **Комплект** — только телефон или с коробкой/зарядкой? Коробка +1-2к к цене перепродажи
5. **Внешний вид** — царапины на корпусе это норм, сколы на экране это проблема, вмятины на рамке = падение = возможны внутренние повреждения
6. **Память** — 64/128/256/512/1TB. Проверь что память в описании совпадает с заголовком
7. **Вскрывался ли** — "вскрытие", "менялся экран", "менялась батарея" — устройство теряет герметичность и стоит дешевле
8. **Подозрительно низкая цена** — если цена на 30%+ ниже рынка без объяснения причины (дефект, срочность) — скорее всего развод

### Рыночные цены б/у Apple (Россия, февраль 2026, идеальное состояние, ориентировочно):

**iPhone (б/у, идеал, 128GB если не указано иначе):**
- iPhone 13: 25-30к
- iPhone 13 Pro: 30-35к
- iPhone 13 Pro Max: 35-40к
- iPhone 14: 32-37к
- iPhone 14 Plus: 35-40к
- iPhone 14 Pro: 40-48к
- iPhone 14 Pro Max: 48-55к
- iPhone 15: 40-47к
- iPhone 15 Plus: 45-52к
- iPhone 15 Pro: 52-60к
- iPhone 15 Pro Max: 60-70к
- iPhone 16: 50-58к
- iPhone 16 Plus: 55-63к
- iPhone 16 Pro: 65-78к
- iPhone 16 Pro Max: 78-95к

256GB: +3-5к к базовой цене
512GB: +8-12к
1TB: +15-20к

**Влияние дефектов на цену (примерно):**
- АКБ <80%: -3-5к
- Экран не оригинал: -5-8к
- Face ID не работает: -8-15к
- Царапины на корпусе (мелкие): -1-2к
- Сколы на экране: -3-5к
- Вмятины на рамке: -5-8к
- Не работает одна камера: -5-10к
- Устройство вскрывалось: -3-5к

## ФОРМАТ ОТВЕТА

Отвечай СТРОГО в формате JSON, без markdown, без ```json```, без лишнего текста:

{
  "score": 7,
  "condition": "хорошее",
  "recommendation": "BUY",
  "defects": ["АКБ 82%", "мелкие царапины на корпусе"],
  "red_flags": [],
  "estimated_real_value": 42000,
  "estimated_sell_price": 48000,
  "estimated_profit": 6000,
  "comment": "iPhone 14 Pro 128GB в хорошем состоянии. АКБ 82% — норм, на перепродаже не критично. Мелкие царапины на корпусе скроются чехлом. По описанию Face ID работает, экран оригинал. Коробка есть — плюс. Можно брать за 42к и продавать за 48к. Рекомендую проверить True Tone и Face ID при встрече."
}

### Шкала оценки:
- **9-10**: Идеальное состояние, отличная цена, бери не думая
- **7-8**: Хорошая сделка, есть мелкие нюансы но профит есть
- **5-6**: Средняя сделка, профит маленький или есть риски, подумай
- **3-4**: Сомнительно — дефекты серьёзные или цена не выгодная
- **1-2**: Плохая сделка — много проблем, профит минимальный или отрицательный
- **0**: Мусор — копия, фейк, iCloud lock, на запчасти, мошенничество

### Рекомендации:
- **BUY**: Профит >= 5000₽ при приемлемых рисках
- **CHECK**: Потенциально выгодно, но нужно проверить при встрече (дефекты не ясны, описание неполное)
- **SKIP**: Не выгодно, слишком рискованно, или мусор

### Поле "comment" — это ГЛАВНОЕ:
Пиши как перекупщик для перекупщика. Кратко, по делу, конкретно. НЕ "товар в хорошем состоянии". А: "14 Pro 256GB, АКБ 89%, экран ориг, Face ID ок. Царапины на рамке — мелочь. За 43к берём, продаём за 52к, профит ~9к. Проверь True Tone при встрече."
"""

USER_PROMPT_TEMPLATE = """Товар для мониторинга: {item_name}
Наш порог покупки: {threshold_price}₽
Рыночная цена перепродажи (наша оценка): {market_price}₽

Объявление на Авито:
Заголовок: {ad_title}
Цена: {ad_price}₽
Город: {city}

Описание продавца:
---
{ad_description}
---

Характеристики из объявления: {ad_params}

Дай экспертную оценку этого объявления."""

VALID_CONDITIONS = frozenset(
    ["идеальное", "хорошее", "с дефектами", "на запчасти", "копия/фейк"]
)
VALID_RECOMMENDATIONS = frozenset(["BUY", "CHECK", "SKIP"])


def validate_ai_response(response: dict) -> dict | None:
    """Validate and sanitize AI response. Returns cleaned dict or None."""
    required = ("score", "condition", "recommendation", "comment")
    for field in required:
        if field not in response:
            logger.warning("AI response missing required field: %s", field)
            return None

    # Validate score
    score = response.get("score", 0)
    if not isinstance(score, (int, float)) or score < 0 or score > 10:
        response["score"] = 0

    # Validate recommendation
    if response.get("recommendation") not in VALID_RECOMMENDATIONS:
        response["recommendation"] = "SKIP"

    # Validate condition
    if response.get("condition") not in VALID_CONDITIONS:
        response["condition"] = "с дефектами"

    # Ensure arrays
    if not isinstance(response.get("defects"), list):
        response["defects"] = []
    if not isinstance(response.get("red_flags"), list):
        response["red_flags"] = []

    # Ensure numeric fields
    for key in ("estimated_real_value", "estimated_sell_price", "estimated_profit"):
        val = response.get(key)
        if not isinstance(val, (int, float)):
            response[key] = 0

    return response


async def analyze_ad(item: dict, ad_data: dict) -> dict | None:
    """Send listing to GPT-4o-mini for analysis. Returns parsed verdict dict or None."""
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        item_name=item["name"],
        threshold_price=item["threshold_price"],
        market_price=item["market_price"],
        ad_price=ad_data.get("price", 0),
        city=ad_data.get("city", "Не указан"),
        ad_title=ad_data.get("title", ""),
        ad_description=ad_data.get("description", "Описание отсутствует"),
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
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        raw_verdict = json.loads(content)
        verdict = validate_ai_response(raw_verdict)

        if verdict is None:
            logger.error("AI response failed validation for ad %s", ad_data.get("ad_id", "?"))
            return None

        logger.info(
            "AI verdict for ad %s: %s (score %s, profit %s)",
            ad_data.get("ad_id", "?"),
            verdict.get("recommendation"),
            verdict.get("score"),
            verdict.get("estimated_profit"),
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
