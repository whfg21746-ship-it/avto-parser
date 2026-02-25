import json
import logging

import openai

import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — опытный перекупщик товаров с Авито в России. Ты покупаешь б/у товары дешево и перепродаёшь с прибылью. У тебя большой опыт оценки состояния товаров по описанию.

## ТВОЯ ЗАДАЧА
Проанализировать объявление с Авито и дать экспертную оценку: стоит ли покупать этот товар для перепродажи.

## КРИТИЧЕСКИЕ ПРАВИЛА — МГНОВЕННЫЙ ОТКАЗ (score: 0):
- Копии, реплики, подделки — "копия", "реплика", "не оригинал", "1 в 1", "версия", "по мотивам"
- Товар заблокирован / привязан к аккаунту (iCloud lock, Google lock, MI account и т.д.)
- На запчасти, нерабочий, "донор"
- Описание написано с заменой букв (а→a, о→0) — обход фильтров, признак мошенника
- Оптовая продажа — "оптом", "партия", "от 10 штук"

## НА ЧТО ОБРАЩАТЬ ВНИМАНИЕ:

### Для электроники (смартфоны, ноутбуки, планшеты, наушники, часы):
- Состояние батареи/АКБ — процент износа, циклы
- Экран — оригинал или замена, царапины, сколы, битые пиксели
- Биометрия — Face ID, Touch ID, сканер отпечатка — работает ли
- Комплект — коробка, зарядка, кабель, документы
- Вскрывался ли — следы ремонта, замены деталей
- Память/конфигурация — совпадает ли с заголовком
- Гарантия — остаток, есть ли чек

### Для игровых консолей (PlayStation, Xbox, Nintendo):
- Ревизия/модель — PS5 Slim vs обычная, Digital vs Disc
- Прошивка — если прошита, это плюс для некоторых покупателей
- Комплект — джойстики (сколько), игры, подписки
- Дрифт стиков — частая проблема, снижает цену

### Для видеокарт и PC-компонентов:
- Был ли майнинг — "использовалась для вычислений", "ферма" = красный флаг
- Термопаста менялась ли, температуры
- Гарантия — остаток
- Артефакты — "иногда полосы" = серьёзная проблема

### Для любой другой категории:
- Общее состояние — новый, б/у, после ремонта
- Дефекты — что сломано, поцарапано, не работает
- Комплектация — что есть, чего нет
- Подозрительно низкая цена без объяснения причины

## ФОРМАТ ОТВЕТА

Отвечай СТРОГО в JSON, без markdown, без блоков кода:

{
  "score": 7,
  "condition": "хорошее",
  "recommendation": "BUY",
  "defects": ["АКБ 82%", "мелкие царапины"],
  "red_flags": [],
  "estimated_sell_price": 32000,
  "estimated_profit": 7000,
  "comment": "Конкретный экспертный комментарий на русском. Что хорошо, что плохо, за сколько реально продать, на что обратить внимание при встрече."
}

### Шкала оценки:
- 9-10: Идеал, бери не думая
- 7-8: Хорошая сделка, мелкие нюансы
- 5-6: Средняя, профит маленький или риски
- 3-4: Сомнительно, серьёзные дефекты
- 1-2: Плохо, почти нет смысла
- 0: Мусор — копия, фейк, лок, на запчасти

### Рекомендации:
- BUY: Профит >= 5000₽, приемлемые риски
- CHECK: Потенциально выгодно, но надо проверить вживую
- SKIP: Не выгодно или слишком рискованно

### Поле "comment":
Пиши как перекупщик для перекупщика. Кратко, конкретно, по делу. Укажи: что хорошо, что плохо, реальная цена перепродажи, что проверить при встрече.
"""

USER_PROMPT_TEMPLATE = """Товар: {item_name}
Максимальная цена покупки: {threshold_price}₽

{custom_instructions}

Объявление на Авито:
Заголовок: {ad_title}
Цена: {ad_price}₽
Город: {city}

Описание продавца:
---
{ad_description}
---

Характеристики: {ad_params}

Дай экспертную оценку. Оцени за сколько реально перепродать и какой будет профит."""

VALID_RECOMMENDATIONS = frozenset(["BUY", "CHECK", "SKIP"])


def _build_custom_instructions(item: dict) -> str:
    """Build custom instructions block from item and category prompts.

    Priority: item custom_prompt overrides category custom_prompt.
    """
    item_prompt = item.get("custom_prompt")
    cat_prompt = item.get("category_custom_prompt")

    prompt = item_prompt or cat_prompt
    if not prompt:
        return ""
    return f"\nДополнительные инструкции от пользователя:\n{prompt}\n"


def validate_ai_response(response: dict) -> dict | None:
    """Validate and sanitize AI response. Returns cleaned dict or None."""
    required = ("score", "recommendation", "comment")
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

    # Ensure arrays
    if not isinstance(response.get("defects"), list):
        response["defects"] = []
    if not isinstance(response.get("red_flags"), list):
        response["red_flags"] = []

    # Ensure numeric fields
    for key in ("estimated_sell_price", "estimated_profit"):
        val = response.get(key)
        if not isinstance(val, (int, float)):
            response[key] = 0

    return response


# Separate logger for AI request/response logging (can be directed to a file)
ai_log = logging.getLogger("ai.requests")


async def analyze_ad(item: dict, ad_data: dict) -> dict | None:
    """Send listing to GPT-4o-mini for analysis. Returns parsed verdict dict or None."""
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    custom_instructions = _build_custom_instructions(item)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        item_name=item["name"],
        threshold_price=item["threshold_price"],
        ad_price=ad_data.get("price", 0),
        city=ad_data.get("city", "Не указан"),
        ad_title=ad_data.get("title", ""),
        ad_description=ad_data.get("description", "Описание отсутствует"),
        ad_params=ad_data.get("params_str", "N/A"),
        custom_instructions=custom_instructions,
    )

    ad_id = ad_data.get("ad_id", "?")

    # Log full request for debugging
    ai_log.debug(
        "AI REQUEST ad_id=%s item=%s\n--- USER PROMPT ---\n%s\n--- END ---",
        ad_id, item["name"], user_prompt,
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

        # Log full response
        ai_log.debug(
            "AI RESPONSE ad_id=%s\n--- RAW ---\n%s\n--- END ---",
            ad_id, content,
        )

        # Log token usage
        usage = response.usage
        if usage:
            ai_log.info(
                "AI USAGE ad_id=%s tokens: prompt=%d completion=%d total=%d",
                ad_id, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
            )

        raw_verdict = json.loads(content)
        verdict = validate_ai_response(raw_verdict)

        if verdict is None:
            logger.error("AI response failed validation for ad %s", ad_id)
            ai_log.warning("AI VALIDATION FAILED ad_id=%s raw=%s", ad_id, content)
            return None

        logger.info(
            "AI verdict for ad %s: %s (score %s, profit %s)",
            ad_id,
            verdict.get("recommendation"),
            verdict.get("score"),
            verdict.get("estimated_profit"),
        )
        return verdict

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from GPT: %s", e)
        ai_log.error("AI JSON ERROR ad_id=%s error=%s", ad_id, e)
        return None
    except openai.APIError as e:
        logger.error("OpenAI API error: %s", e)
        ai_log.error("AI API ERROR ad_id=%s error=%s", ad_id, e)
        return None
    except Exception as e:
        logger.error("Unexpected error in AI analysis: %s", e)
        ai_log.error("AI UNEXPECTED ERROR ad_id=%s error=%s", ad_id, e)
        return None
