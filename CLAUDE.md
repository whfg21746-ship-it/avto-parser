# Avito Flipper Bot

Telegram-бот для поиска выгодных объявлений на Авито с целью перепродажи. Автоматически мониторит заданные поисковые запросы, фильтрует мусор, отправляет объявления на анализ GPT-4o-mini и присылает алерты о выгодных сделках.

## Запуск

```bash
cd /root/avto-parser
source venv/bin/activate
PYTHONPATH=/root/avto-parser python bot/main.py
```

Требуется `.env` файл в корне (см. `.env.example`):
- `TELEGRAM_BOT_TOKEN` — токен Telegram-бота
- `OPENAI_API_KEY` — ключ OpenAI API (используется gpt-4o-mini)
- `PROXY_LIST` — JSON-массив HTTP-прокси (опционально)
- `SCAN_INTERVAL` — интервал сканирования в секундах (по умолчанию 60)
- `MAX_SELLER_ITEMS` — макс. активных объявлений у продавца (фильтр перекупов)
- `DATABASE_PATH` — путь к базе (по умолчанию `./data/flipper.db`)
- `SEARCH_PAGES` — количество страниц поиска Авито (по умолчанию 3)
- `ALLOWED_USERS` — whitelist Telegram ID через запятую (пустое = без ограничений)

Зависимости: `pip install -r requirements.txt && playwright install chromium`

Тесты: `PYTHONPATH=. pytest tests/ -v`

## Архитектура

```
avto-parser/
├── bot/                        # Telegram-бот (aiogram 3)
│   ├── main.py                 # Точка входа: Bot + Dispatcher + APScheduler
│   ├── handlers/
│   │   ├── start.py            # /start, главное меню, вкл/выкл мониторинга
│   │   ├── items.py            # CRUD товаров: добавление (URL/конструктор), редактирование, удаление
│   │   ├── categories.py       # CRUD категорий: создание, переименование, удаление, AI-подсказки
│   │   ├── settings.py         # Настройки: город, интервал, прокси, фильтр продавцов
│   │   └── stats.py            # /stats, export CSV/JSON, очистка старых seen_ads
│   ├── keyboards/
│   │   └── menus.py            # Все InlineKeyboardMarkup (главное меню, навигация, подтверждения)
│   ├── states/
│   │   └── item_states.py      # FSM-состояния (AddItemFSM, EditItemFSM, SettingsFSM и др.)
│   └── middlewares/
│       └── user_db.py          # UserDBMiddleware — устанавливает per-user контекст БД
├── parser/                     # Парсинг Авито
│   ├── avito_api.py            # AvitoAPI — скрапинг HTML, извлечение JSON из <script type="mime/invalid">
│   ├── cookie_provider.py      # CookieProvider — Playwright headless browser для получения ft-куки
│   ├── proxy_manager.py        # ProxyManager — ротация прокси с авто-порогом
│   ├── filters.py              # Пре-фильтры: regex-паттерны (копии, запчасти, лок) + фильтр продавцов
│   └── scheduler.py            # Основной цикл сканирования: pipeline обработки объявлений
├── ai/
│   └── analyzer.py             # GPT-4o-mini анализ: оценка сделки, профит, рекомендация (BUY/CHECK/SKIP)
├── db/
│   ├── database.py             # Подключение к SQLite (aiosqlite), per-user контекст, миграции
│   ├── models.py               # CRUD-операции: categories, items, seen_ads, settings
│   └── schema.sql              # DDL-схема: settings, categories, items, seen_ads
├── tests/                      # Unit-тесты (pytest, 94 теста)
│   ├── test_filters.py         # Тесты фильтров (reject, seller, model_pattern)
│   ├── test_avito_api.py       # Тесты парсинга (JSON, HTML, цены, описания)
│   └── test_analyzer.py        # Тесты AI (валидация, промпты)
├── config.py                   # Загрузка .env через python-dotenv
├── requirements.txt            # Зависимости
└── .env.example                # Шаблон переменных окружения
```

## Как работает

### Основной цикл (parser/scheduler.py)

APScheduler запускает `run_scan_cycle()` каждые N секунд (по умолчанию 60). Цикл:

1. **Обнаружение пользователей** — сканирует `data/user_*/` директории
2. **Параллельный запуск** — `asyncio.gather()` для всех пользователей
3. **Per-user pipeline** для каждого активного товара:
   - Загрузка прокси и куков из настроек пользователя
   - Запрос к Авито через `AvitoAPI.search_by_keyword()`
   - **Baseline scan** — первый запуск сохраняет все текущие объявления как "виденные"
   - Для каждого нового объявления — pipeline фильтрации:
     - (a) Дедупликация по `ad_id`
     - (b) Проверка порога цены
     - (c) Regex-фильтр заголовка (копии, запчасти, лок аккаунта)
     - (d) Извлечение деталей из поисковой выдачи
     - (e) Фильтр продавца (магазины, перекупы с >N объявлений)
     - (f) Regex-фильтр описания
     - (g) **AI-анализ** через GPT-4o-mini → оценка 0-10, BUY/CHECK/SKIP
   - Отправка алерта в Telegram если рекомендация BUY или CHECK

### Парсинг Авито (parser/avito_api.py)

- Использует `curl_cffi` с имперсонацией браузеров (Chrome/Safari профили)
- Авито встраивает данные каталога в `<script type="mime/invalid">` теги как JSON
- Fallback: `window.__initialData__` паттерн
- Обрабатывает embedded-редиректы (301/302 внутри JSON)
- Retry-логика: 3 попытки с ротацией прокси и пересозданием сессии

### Куки (parser/cookie_provider.py)

- Авито требует `ft` (fingerprint) куку, которая ставится клиентским JavaScript
- Playwright + playwright-stealth запускает headless Chromium
- Заходит на рандомную несуществующую страницу, ждёт до 50 сек пока JS поставит куку
- Куки кешируются на 25 минут
- Circuit breaker: если Playwright не может запуститься (missing libs), больше не пытается

### AI-анализ (ai/analyzer.py)

- Модель: `gpt-4o-mini` (temperature=0.3, json mode)
- Системный промпт: роль "опытный перекупщик", правила мгновенного отказа, шкала оценки
- Поддержка кастомных AI-подсказок на уровне категории и товара
- Ответ: `{score, condition, recommendation, defects, red_flags, estimated_sell_price, estimated_profit, comment}`

### База данных (db/)

Per-user SQLite базы: `data/user_{telegram_id}/flipper.db`

**Таблицы:**
- `settings` — key/value настройки (город, прокси, интервал, мониторинг)
- `categories` — категории товаров (name, custom_prompt, is_active)
- `items` — отслеживаемые товары (category_id, name, avito_url, threshold_price, custom_prompt)
- `seen_ads` — виденные объявления (ad_id, item_id, price, ai_verdict, was_alerted, skip_reason)

Миграции в `database.py`: автоудаление старой схемы (search_queries), добавление custom_prompt, удаление market_price.

### Telegram-бот (bot/)

- aiogram 3 + FSM (MemoryStorage)
- Middleware `UserDBMiddleware` устанавливает per-user контекст БД через `contextvars`
- Хэндлеры: /start, CRUD товаров и категорий, настройки
- Два способа добавления товара: вставить ссылку с Авито или собрать ссылку в боте (город + запрос + цена)
- Пагинация списка товаров (10 на страницу)
- Inline-клавиатуры для всей навигации

## Известные проблемы и ограничения

### Критические

1. **ft-кука часто не получается** — ~~Playwright не всегда успевает дождаться JS-fingerprinting.~~ **УЛУЧШЕНО**: увеличена частота опросов (15×3с), retry с разными страницами (случайная, главная, поиск), CookieProvider кешируется между циклами. Мониторинг success rate.

2. **Нет описания из поисковой выдачи** — ~~AI-анализ работает без описания.~~ **ИСПРАВЛЕНО**: добавлен `fetch_ad_extra()` — загружает страницу объявления, извлекает описание из embedded JSON + данные о продавце.

3. **Seller active items не извлекается** — ~~данные не присутствуют в поисковой выдаче.~~ **УЛУЧШЕНО**: при загрузке страницы объявления (п.2) извлекаются данные о продавце с повторной проверкой фильтра.

### Средние

4. **Интервал сканирования не динамический** — ~~APScheduler использует значение из config.py.~~ **ИСПРАВЛЕНО**: scheduler теперь тикает каждые 30 сек и проверяет per-user `scan_interval_seconds`.

5. **Одна сессия Playwright на все запросы** — ~~CookieProvider создаётся заново на каждый scan cycle.~~ **ИСПРАВЛЕНО**: `get_cookie_provider()` кеширует инстансы по proxy URL.

6. **Нет ограничения на количество пользователей** — ~~любой может /start.~~ **ИСПРАВЛЕНО**: `ALLOWED_USERS` env variable (whitelist Telegram ID), проверка в middleware.

7. **model_pattern не используется** — ~~поле заполняется как NULL.~~ **ИСПРАВЛЕНО**: regex-фильтрация по title+params в pipeline, fail-open при невалидном regex.

### Мелкие

8. **Каждая DB-операция открывает/закрывает соединение** — ~~`get_db()` создаёт новое соединение на каждый вызов.~~ **ИСПРАВЛЕНО**: connection pool per user с health check.

9. **Нет тестов** — ~~ни unit, ни integration тестов.~~ **ИСПРАВЛЕНО**: 94 unit-теста (filters, avito_api, analyzer).

10. **Translit для городов неполный** — `_CITY_SLUGS` содержит ~27 городов. Для остальных используется автоматическая транслитерация, которая может не совпадать с URL-ами Авито.

## Что было доделано

### Высокий приоритет (все выполнено)

- [x] **Получение описания объявления** — `fetch_ad_extra()` загружает страницу объявления, извлекает описание + данные продавца из embedded JSON.
- [x] **Стабилизация ft-куки** — увеличена частота опросов (15×3с), retry с разными страницами, кеширование CookieProvider между циклами, мониторинг success rate.
- [x] **Авторизация пользователей** — `ALLOWED_USERS` env var (whitelist Telegram ID), проверка в `UserDBMiddleware`.

### Средний приоритет (все выполнено)

- [x] **Пагинация поисковых результатов** — `search_by_keyword()` загружает до `SEARCH_PAGES` (default 3) страниц с дедупликацией.
- [x] **Динамический интервал сканирования** — scheduler тикает каждые 30 сек, проверяет per-user `scan_interval_seconds`.
- [x] **Connection pooling для SQLite** — `get_db()` кеширует соединения per user с health check, `close_all_connections()` на shutdown.
- [x] **Логирование AI-запросов** — отдельный логгер `ai.requests` с полным prompt/response (DEBUG) и usage stats (INFO).
- [x] **Фото в алертах** — `send_photo()` с первой картинкой, fallback на `send_message()`.

### Низкий приоритет (все выполнено)

- [x] **Тесты** — 94 unit-теста (pytest): filters.py, avito_api.py, analyzer.py.
- [x] **Статистика** — `/stats` команда + inline кнопка: просмотрено, алерты, конверсия.
- [x] **Export** — CSV/JSON экспорт алертов через Telegram (BufferedInputFile).
- [x] **Удаление старых seen_ads** — `delete_old_seen_ads(days=30)` из экрана статистики.
- [x] **Использование model_pattern** — regex фильтрация по title+params в pipeline, fail-open.

## Что ещё можно улучшить

- [ ] **Integration тесты** — тесты с реальной БД для models.py.
- [ ] **Translit для городов** — расширить `_CITY_SLUGS` или найти API для маппинга.
- [ ] **Grafana/Prometheus метрики** — экспорт метрик сканирования для мониторинга.
- [ ] **Загрузка нескольких фото** — Telegram media group с несколькими фотографиями.
