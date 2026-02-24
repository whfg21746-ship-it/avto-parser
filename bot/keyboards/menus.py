from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

ITEMS_PER_PAGE = 10


def main_menu(monitoring_active: bool = False) -> InlineKeyboardMarkup:
    toggle_text = "\u23f8 Пауза мониторинга" if monitoring_active else "\u25b6\ufe0f Старт мониторинга"
    toggle_cb = "monitoring_off" if monitoring_active else "monitoring_on"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f4e6 Мои товары", callback_data="items_list"),
            InlineKeyboardButton(text="\u2795 Добавить товар", callback_data="item_add"),
        ],
        [
            InlineKeyboardButton(text="\U0001f50d Поисковые запросы", callback_data="search_queries_list"),
            InlineKeyboardButton(text="\U0001f4c1 Категории", callback_data="categories_list"),
        ],
        [
            InlineKeyboardButton(text="\u2699\ufe0f Настройки", callback_data="settings"),
            InlineKeyboardButton(text="\U0001f52c Тест API", callback_data="test_api"),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
        ],
    ])


def categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Category picker for the 'Add Item' flow."""
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for cat in categories:
        pair.append(InlineKeyboardButton(
            text=cat["name"],
            callback_data=f"cat_select_{cat['id']}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(
        text="\u2795 Новая категория",
        callback_data="category_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_list_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """'Категории' screen — shows categories, click opens items inside."""
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([InlineKeyboardButton(
            text=f"{cat['name']} ({cat['items_count']} тов.)",
            callback_data=f"cat_view_{cat['id']}_0",
        )])
    rows.append([InlineKeyboardButton(
        text="\u2795 Добавить категорию",
        callback_data="category_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_nav_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """'Мои товары' screen — shows categories as folders to browse items."""
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        active = cat.get("active_count", 0)
        rows.append([InlineKeyboardButton(
            text=f"{cat['name']} — {active}/{cat['items_count']} акт.",
            callback_data=f"cat_items_{cat['id']}_0",
        )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_items_keyboard(
    items: list[dict],
    category_id: int,
    page: int,
    total: int,
    source: str = "cat_items",
) -> InlineKeyboardMarkup:
    """Paginated list of items within a category."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        status = "\u2705" if item["is_active"] else "\u23f8"
        text = f"{status} {item['name']} — {item['threshold_price']:,}\u20bd"
        if len(text) > 60:
            text = text[:57] + "..."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"item_view_{item['id']}",
        )])

    # Pagination controls
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="\u25c0\ufe0f",
            callback_data=f"{source}_{category_id}_{page - 1}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="noop",
    ))
    if (page + 1) * ITEMS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(
            text="\u25b6\ufe0f",
            callback_data=f"{source}_{category_id}_{page + 1}",
        ))
    if total_pages > 1:
        rows.append(nav)

    back_cb = "items_list" if source == "cat_items" else "categories_list"
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Подтвердить", callback_data="item_confirm"),
            InlineKeyboardButton(text="\u270f\ufe0f Изменить", callback_data="item_edit_restart"),
            InlineKeyboardButton(text="\u274c Отмена", callback_data="item_cancel"),
        ],
    ])


def items_list_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """Flat list fallback (used after delete, etc)."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:20]:
        status = "\u2705" if item["is_active"] else "\u23f8"
        text = f"{status} {item['name']} — {item['threshold_price']:,}\u20bd"
        if len(text) > 60:
            text = text[:57] + "..."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"item_view_{item['id']}",
        )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_detail_keyboard(item: dict) -> InlineKeyboardMarkup:
    toggle_text = "\u23f8 Выключить" if item["is_active"] else "\u25b6\ufe0f Включить"
    toggle_cb = f"item_deactivate_{item['id']}" if item["is_active"] else f"item_activate_{item['id']}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u270f\ufe0f Порог",
                callback_data=f"item_edit_threshold_{item['id']}",
            ),
            InlineKeyboardButton(
                text="\u270f\ufe0f Рыночная",
                callback_data=f"item_edit_market_{item['id']}",
            ),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
            InlineKeyboardButton(
                text="\U0001f5d1 Удалить",
                callback_data=f"item_delete_{item['id']}",
            ),
        ],
        [InlineKeyboardButton(
            text="\u2b05\ufe0f Назад к категории",
            callback_data=f"cat_items_{item['category_id']}_0",
        )],
    ])


# --- Search Queries keyboards ---

def search_queries_list_keyboard(queries: list[dict]) -> InlineKeyboardMarkup:
    """List of search queries with item counts."""
    rows: list[list[InlineKeyboardButton]] = []
    for sq in queries:
        status = "\u2705" if sq["is_active"] else "\u23f8"
        count = sq.get("items_count", 0)
        text = f'{status} "{sq["keyword"]}" — {count} мод.'
        if len(text) > 60:
            text = text[:57] + "..."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"sq_view_{sq['id']}",
        )])
    rows.append([InlineKeyboardButton(
        text="\u2795 Добавить запрос",
        callback_data="sq_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_query_detail_keyboard(sq: dict) -> InlineKeyboardMarkup:
    """Detail view for a search query."""
    toggle_text = "\u23f8 Выключить" if sq["is_active"] else "\u25b6\ufe0f Включить"
    toggle_cb = f"sq_deactivate_{sq['id']}" if sq["is_active"] else f"sq_activate_{sq['id']}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
            InlineKeyboardButton(
                text="\U0001f5d1 Удалить",
                callback_data=f"sq_delete_{sq['id']}",
            ),
        ],
        [InlineKeyboardButton(
            text="\u2b05\ufe0f Назад",
            callback_data="search_queries_list",
        )],
    ])


def search_query_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Подтвердить", callback_data="sq_confirm"),
            InlineKeyboardButton(text="\u274c Отмена", callback_data="sq_cancel"),
        ],
    ])


def search_queries_picker_keyboard(queries: list[dict]) -> InlineKeyboardMarkup:
    """Search query picker for the 'Add Item' flow."""
    rows: list[list[InlineKeyboardButton]] = []
    for sq in queries:
        text = f'"{sq["keyword"]}" ({sq.get("category_name", "?")})'
        if len(text) > 60:
            text = text[:57] + "..."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"sq_pick_{sq['id']}",
        )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_sq_keyboard(query_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u2705 Да, удалить",
                callback_data=f"sq_delete_confirm_{query_id}",
            ),
            InlineKeyboardButton(text="\u274c Отмена", callback_data=f"sq_view_{query_id}"),
        ],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f504 Интервал", callback_data="setting_interval"),
            InlineKeyboardButton(text="\U0001f4e1 Прокси", callback_data="setting_proxy"),
        ],
        [
            InlineKeyboardButton(text="\U0001f464 Фильтр продавцов", callback_data="setting_max_seller"),
        ],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


def back_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


def ad_alert_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f517 Открыть объявление", url=url)],
    ])


def confirm_delete_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u2705 Да, удалить",
                callback_data=f"item_delete_confirm_{item_id}",
            ),
            InlineKeyboardButton(text="\u274c Отмена", callback_data=f"item_view_{item_id}"),
        ],
    ])
