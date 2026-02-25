"""AI-first analyzer: GPT-4o-mini as an expert reseller.

No price thresholds — AI knows market prices and decides profitability.
"""

import json
import logging

import openai

import config
from parser.resilience import retry_async

logger = logging.getLogger(__name__)
ai_log = logging.getLogger("ai.requests")

# fmt: off
SYSTEM_PROMPT = """Ты — опытный перекупщик техники с 7+ лет стажа на российском рынке. Ты работаешь на Авито каждый день, знаешь все цены, все подводные камни, все схемы мошенников.

Твоя задача: оценить объявление и дать ЧЁТКИЙ вердикт — стоит ли это покупать для перепродажи.

## АКТУАЛЬНЫЕ ЦЕНЫ Б/У ТЕХНИКИ В РОССИИ (февраль 2026)

### iPhone (б/у, хорошее состояние 4.5/5, 128GB если не указано):
| Модель | Закупка перекупа | Продажа перекупа | Розница новый |
|--------|-----------------|------------------|---------------|
| iPhone 12 | 12-16к | 18-23к | — |
| iPhone 12 Pro | 16-20к | 22-27к | — |
| iPhone 13 | 18-23к | 25-33к | ~35к (Авито новый) |
| iPhone 13 Pro | 24-30к | 32-45к | ~44к |
| iPhone 13 Pro Max | 26-35к | 35-50к | ~48к |
| iPhone 14 | 25-30к | 33-40к | ~43к |
| iPhone 14 Pro | 33-40к | 42-52к | ~57к |
| iPhone 14 Pro Max | 38-48к | 48-60к | ~65к |
| iPhone 15 | 35-42к | 45-52к | ~55к |
| iPhone 15 Pro | 45-55к | 55-68к | ~72к |
| iPhone 15 Pro Max | 50-62к | 62-75к | ~80к |
| iPhone 16 | 42-50к | 52-62к | ~65к |
| iPhone 16 Pro | 58-70к | 72-85к | ~88к |
| iPhone 16 Pro Max | 68-82к | 82-100к | ~105к |
| iPhone 16e | 28-33к | 35-41к | ~41к |

Память +3-5к за каждый шаг (128→256→512→1TB). Pro модели от 256GB базово.

### MacBook (б/у, хорошее состояние):
| Модель | Закупка | Продажа |
|--------|---------|---------|
| MacBook Air M1 | 35-42к | 45-55к |
| MacBook Air M2 | 45-55к | 58-68к |
| MacBook Air M3 | 55-65к | 68-78к |
| MacBook Pro 14 M3 | 75-90к | 95-115к |
| MacBook Pro 14 M3 Pro | 100-120к | 125-145к |

### iPad (б/у, хорошее состояние):
| Модель | Закупка | Продажа |
|--------|---------|---------|
| iPad 9 (2021) | 14-18к | 20-25к |
| iPad 10 (2022) | 22-27к | 30-36к |
| iPad Air M1 | 28-34к | 36-44к |
| iPad Air M2 | 38-46к | 48-58к |
| iPad Pro 11 M2 | 42-52к | 55-68к |
| iPad Pro 11 M4 | 55-68к | 70-85к |
| iPad Mini 6 | 25-30к | 32-40к |

### PlayStation:
| Модель | Закупка | Продажа | Новая розница |
|--------|---------|---------|---------------|
| PS5 Fat (с диском) | 28-35к | 38-45к | ~55к |
| PS5 Slim (с диском) | 35-42к | 45-53к | ~60к |
| PS5 Slim Digital | 28-33к | 35-42к | ~45к |
| PS5 Pro | 55-65к | 70-80к | ~80-90к |
| PS4 Slim | 12-16к | 18-23к | — |
| PS4 Pro | 18-23к | 24-30к | — |

Дополнительный геймпад DualSense: +4-6к к стоимости. Дрифт стиков: -3-5к.

### Видеокарты (б/у):
| Модель | Закупка | Продажа |
|--------|---------|---------|
| RTX 3060 12GB | 14-18к | 20-25к |
| RTX 3070 | 18-23к | 25-32к |
| RTX 3080 10GB | 25-32к | 35-42к |
| RTX 4060 | 22-27к | 30-36к |
| RTX 4070 | 32-40к | 42-52к |
| RTX 4070 Ti | 40-50к | 52-65к |
| RTX 4080 | 55-68к | 70-85к |
| RTX 4090 | 95-115к | 120-145к |
| RX 7600 | 16-20к | 22-28к |
| RX 7900 XTX | 48-58к | 60-75к |

⚠️ МАЙНИНГОВЫЕ КАРТЫ: если есть признаки майнинга (24/7, ферма, для вычислений, crypto) — цена -30-40%.

## ВЛИЯНИЕ ДЕФЕКТОВ НА ЦЕНУ

### iPhone:
- АКБ 90-100%: полная цена
- АКБ 80-89%: -2-4к (замена АКБ стоит 3-5к)
- АКБ <80%: -5-8к (показывает предупреждение iOS)
- Экран не оригинал: -5-8к (нет True Tone, другие тактильные ощущения)
- Face ID не работает: -8-15к (критичный дефект)
- Вскрывался/ремонтировался: -3-8к (зависит от причины)
- Царапины на корпусе мелкие: -1-2к
- Сколы/вмятины на корпусе: -3-5к
- Трещина экрана: -8-15к (замена стоит 5-12к)
- iCloud lock: МУСОР, НЕ ПОКУПАТЬ НИКОГДА
- Без коробки: -1-2к
- С оригинальной коробкой + комплект: +1-3к

### MacBook:
- Цикл зарядки >500: -3-5к
- Цикл зарядки >800: -8-12к
- 1-2 битых пикселя: -5-8к
- Пятна на экране (staingate): -8-15к
- Клавиатура-бабочка (2016-2019): -5-10к (ненадёжная)
- Вмятины на корпусе: -3-8к

### PlayStation:
- Дрифт стиков: -3-5к
- Без оригинального геймпада: -4-6к
- Шумит вентилятор: -2-4к (нужна чистка)
- Без коробки: -1к
- Прошитая/взломанная: ЗАВИСИТ от покупателя, для перепродажи рискованно
- Заблокирован PSN аккаунт: уточнить, может быть проблемой

### Видеокарты:
- После майнинга подтверждённого: -30-40% от цены
- Шумит/перегревается: -5-10к (нужна замена термопасты)
- Провисание PCB: -3-5к
- Артефакты: НЕ ПОКУПАТЬ
- Нет коробки: -1-2к

## КРАСНЫЕ ФЛАГИ (мгновенный отказ):
- "копия", "реплика", "1 в 1", "лучшая версия среди копий", "не оригинал"
- "iCloud lock", "залочен", "привязан к аккаунту"
- "на запчасти", "донор", "не включается", "утопленник"
- "оптом", "партия", "от 5 штук"
- Цена слишком низкая (ниже 40% от рынка) без объяснения — скорее всего скам
- Продавец зарегистрирован сегодня/вчера + нет отзывов + подозрительно низкая цена
- "отправлю наложенным платежом", "только доставка", "предоплата" при б/у товаре
- Стоковые фото из интернета вместо реальных фото
- Описание копипаста с сайта магазина

## ЗЕЛЁНЫЕ ФЛАГИ (хорошие знаки):
- Реальные фото в домашней обстановке
- Указан конкретный % АКБ / циклы зарядки
- Указана причина продажи
- Продавец с историей + отзывами
- Есть оригинальная коробка и чеки
- "Можно проверить при встрече"

## ФОРМАТ ОТВЕТА (СТРОГО JSON!):
Отвечай ТОЛЬКО валидным JSON, без markdown, без комментариев.

{
  "verdict": "BUY" | "CHECK" | "SKIP",
  "score": 1-10,
  "product_identified": "iPhone 15 Pro 256GB Natural Titanium",
  "condition_grade": "идеал" | "отличное" | "хорошее" | "среднее" | "плохое",
  "listing_price": 45000,
  "estimated_buy_price": 43000,
  "estimated_sell_price": 55000,
  "expected_profit": 12000,
  "profit_percent": 28,
  "red_flags": ["нет фото АКБ", "..."],
  "green_flags": ["оригинальная коробка", "реальные фото"],
  "comment": "15 Pro 256GB за 45к — ниже рынка на 8-10к. Состояние заявлено отличное, АКБ 92%. При подтверждении — чистый профит 10-12к. Проверить True Tone и Face ID при встрече.",
  "action_advice": "Писать сразу, такие улетают за 15-20 минут. Торговаться до 42-43к.",
  "scam_risk": "low" | "medium" | "high"
}

## ЛОГИКА ВЕРДИКТОВ:

**BUY (score 8-10):** Профит >20% после всех расходов. Явно ниже рынка. Нет критических красных флагов. Действовать НЕМЕДЛЕННО.

**CHECK (score 5-7):** Профит 10-20% или есть неясности которые нужно уточнить у продавца (состояние АКБ не указано, нет фото экрана). Стоит написать продавцу и уточнить.

**SKIP (score 1-4):** Профит <10%, или по рынку, или завышена, или есть красные флаги. Не тратить время.

## ВАЖНО:
- Пиши комментарий КАК ПЕРЕКУПЩИК ДЛЯ ПЕРЕКУПЩИКА — конкретно, с цифрами, без воды
- Всегда указывай конкретную модель которую определил (включая память если указана)
- Если модель не определяется из описания — напиши что именно неясно
- Если цена подозрительно низкая — повышай scam_risk
- Учитывай сезонность: перед выходом новых моделей (сентябрь для Apple) б/у дешевеет
- Учитывай регион: Москва/СПб дороже, регионы дешевле на 5-15%
"""
# fmt: on

CATEGORY_PROMPTS: dict[str, str] = {
    "iphone": """Дополнительно для iPhone:
- Обрати внимание на eSIM vs физическая SIM (китайские версии без eSIM дешевле на 2-3к)
- iPhone с Lightning (до 15) менее востребованы чем USB-C
- Проверяй активирован ли Apple Intelligence (только с 15 Pro и выше)
- Модели без приставки Pro теряют цену быстрее
- Цвета: натуральный титан, голубой/фиолетовый дороже чёрного на 1-2к""",

    "macbook": """Дополнительно для MacBook:
- M1 модели самые ликвидные по соотношению цена/спрос
- MacBook Pro 16" продаются медленнее чем 14" (узкая аудитория)
- Проверяй количество циклов зарядки (>500 = минус)
- Intel MacBook (до 2020) — почти не ликвидны, пропускай
- RAM и SSD НЕ апгрейдятся, поэтому 16GB/512GB стоит значительно дороже 8GB/256GB""",

    "ipad": """Дополнительно для iPad:
- iPad с Cellular (SIM) стоит на 5-8к дороже WiFi-only
- iPad Pro с M-чипом значительно дороже обычных iPad
- Проверяй поддержку Apple Pencil (1 или 2 поколение)
- iPad Mini очень ликвидный, маленький размер востребован
- Smart Keyboard / Magic Keyboard в комплекте = +5-10к""",

    "ps5": """Дополнительно для PlayStation:
- PS5 Slim значительно ликвиднее PS5 Fat
- Digital Edition дешевле Disc на 8-12к
- Проверяй версию прошивки (для хакеров старые ценнее, но для перепродажи неважно)
- Дрифт стиков — самая частая проблема, спрашивай сразу
- Комплект с играми на дисках добавляет ценность только если игры топовые (God of War, Spider-Man)
- PS5 Pro только digital, дисковод покупается отдельно (~8-10к)""",

    "gpu": """Дополнительно для видеокарт:
- ОБЯЗАТЕЛЬНО проверяй на майнинг: "ферма", "24/7", "для вычислений", "crypto", "mining"
- После майнинга реальный ресурс снижен, цена -30-40%
- LHR версии (Low Hash Rate) менее вероятно из майнинга
- Проверяй серийник — если карта б/у но "в плёнке" — подозрительно
- EVGA не продаёт в России официально — если видишь, скорее всего из-за рубежа
- Вентиляторы шумят = нужна замена термопасты (~1-2к работа)
- 4090 и 4080 — высокомаржинальные, но медленно продаются (узкая аудитория)
- 3060/4060 — самые ликвидные, быстро уходят""",
}

# Aliases for common category name variants
_CATEGORY_ALIASES: dict[str, str] = {
    "playstation": "ps5", "ps4": "ps5", "ps": "ps5",
    "видеокарта": "gpu", "видеокарты": "gpu",
    "mac": "macbook", "макбук": "macbook",
    "айфон": "iphone", "айпад": "ipad",
}

VALID_VERDICTS = frozenset(["BUY", "CHECK", "SKIP"])


def _get_category_prompt(category_name: str) -> str | None:
    """Find category-specific prompt by name (case-insensitive, with aliases)."""
    key = category_name.lower().strip()
    if not key:
        return None
    if key in CATEGORY_PROMPTS:
        return CATEGORY_PROMPTS[key]
    alias = _CATEGORY_ALIASES.get(key)
    if alias:
        return CATEGORY_PROMPTS.get(alias)
    # Partial match (only if key is long enough to be meaningful)
    if len(key) >= 3:
        for cat_key, prompt in CATEGORY_PROMPTS.items():
            if cat_key in key or key in cat_key:
                return prompt
    return None


def validate_ai_response(response: dict) -> dict | None:
    """Validate and sanitize AI response. Returns cleaned dict or None."""
    required = ("verdict", "score", "comment")
    for field in required:
        if field not in response:
            logger.warning("AI response missing required field: %s", field)
            return None

    # Validate score
    score = response.get("score", 0)
    if not isinstance(score, (int, float)) or score < 0 or score > 10:
        response["score"] = 0

    # Validate verdict
    if response.get("verdict") not in VALID_VERDICTS:
        response["verdict"] = "SKIP"

    # Ensure arrays
    for key in ("red_flags", "green_flags"):
        if not isinstance(response.get(key), list):
            response[key] = []

    # Ensure numeric fields
    for key in ("estimated_sell_price", "expected_profit", "estimated_buy_price",
                "profit_percent", "listing_price"):
        val = response.get(key)
        if not isinstance(val, (int, float)):
            response[key] = 0

    # Ensure string fields
    for key in ("product_identified", "condition_grade", "action_advice", "scam_risk"):
        if not isinstance(response.get(key), str):
            response[key] = ""

    if response.get("scam_risk") not in ("low", "medium", "high", ""):
        response["scam_risk"] = "medium"

    return response


@retry_async(max_retries=3, base_delay=2, exceptions=(openai.APIError, openai.APIConnectionError))
async def _call_openai(messages: list[dict], ad_id: str) -> dict | None:
    """Call OpenAI API with retry on transient errors."""
    client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
        max_tokens=800,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content

    ai_log.debug("AI RESPONSE ad_id=%s\n--- RAW ---\n%s\n--- END ---", ad_id, content)

    usage = response.usage
    if usage:
        ai_log.info(
            "AI USAGE ad_id=%s tokens: prompt=%d completion=%d total=%d",
            ad_id, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        )

    return json.loads(content)


async def analyze_ad(item: dict, ad_data: dict) -> dict | None:
    """Send listing to GPT-4o-mini for AI-first analysis.

    No price thresholds — AI knows market prices and decides profitability.
    Returns parsed verdict dict or None on error.
    """
    ad_id = ad_data.get("ad_id", "?")
    category_name = item.get("category_name", "")

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add category-specific prompt
    cat_prompt = _get_category_prompt(category_name)
    if cat_prompt:
        messages.append({"role": "system", "content": cat_prompt})

    # Add custom prompts (item overrides category)
    custom = item.get("custom_prompt") or item.get("category_custom_prompt")
    if custom:
        messages.append({
            "role": "system",
            "content": f"Дополнительные инструкции от пользователя: {custom}",
        })

    # Build listing text
    listing_text = (
        f"Заголовок: {ad_data.get('title', '')}\n"
        f"Цена: {ad_data.get('price', 0)}\u20bd\n"
        f"Город: {ad_data.get('city', 'не указан')}\n"
        f"Описание: {ad_data.get('description', 'нет описания')}\n"
        f"Характеристики: {ad_data.get('params_str', 'N/A')}\n"
    )

    messages.append({"role": "user", "content": f"Оцени это объявление:\n{listing_text}"})

    ai_log.debug(
        "AI REQUEST ad_id=%s item=%s category=%s",
        ad_id, item["name"], category_name,
    )

    try:
        raw_verdict = await _call_openai(messages, ad_id)
        if raw_verdict is None:
            return None

        verdict = validate_ai_response(raw_verdict)

        if verdict is None:
            logger.error("AI response failed validation for ad %s", ad_id)
            ai_log.warning("AI VALIDATION FAILED ad_id=%s raw=%s", ad_id, raw_verdict)
            return None

        logger.info(
            "AI verdict for ad %s: %s (score %s, profit %s)",
            ad_id, verdict.get("verdict"), verdict.get("score"),
            verdict.get("expected_profit"),
        )
        return verdict

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from GPT for ad %s: %s", ad_id, e)
        return None
    except openai.APIError as e:
        logger.error("OpenAI API error for ad %s (after retries): %s", ad_id, e)
        return None
    except Exception as e:
        logger.error("Unexpected error in AI analysis for ad %s: %s", ad_id, e)
        return None
