from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

ITEMS_PER_PAGE = 10


def main_menu(monitoring_active: bool = False, has_items: bool = False) -> InlineKeyboardMarkup:
    toggle_text = "\u23f8 Пауза" if monitoring_active else "\u25b6\ufe0f Старт"
    toggle_cb = "monitoring_off" if monitoring_active else "monitoring_on"

    rows: list[list[InlineKeyboardButton]] = []

    if has_items:
        rows.append([
            InlineKeyboardButton(text="\U0001f4e6 Мои товары", callback_data="items_list"),
            InlineKeyboardButton(text="\u2795 Добавить товар", callback_data="item_add"),
        ])
        rows.append([
            InlineKeyboardButton(text="\U0001f4c1 Категории", callback_data="categories_list"),
            InlineKeyboardButton(text="\u2699\ufe0f Настройки", callback_data="settings"),
        ])
        rows.append([
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="\u2795 Добавить товар", callback_data="item_add"),
        ])
        rows.append([
            InlineKeyboardButton(text="\u2699\ufe0f Настройки", callback_data="settings"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_item_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="\U0001f517 Вставить ссылку с Авито",
            callback_data="add_method_url",
        )],
        [InlineKeyboardButton(
            text="\U0001f6e0 Собрать ссылку в боте",
            callback_data="add_method_build",
        )],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


def category_picker_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for cat in categories:
        pair.append(InlineKeyboardButton(
            text=cat["name"],
            callback_data=f"cat_pick_{cat['id']}",
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(
        text="\u2795 Новая категория",
        callback_data="cat_pick_new",
    )])
    rows.append([InlineKeyboardButton(text="\u274c Отмена", callback_data="item_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def city_picker_keyboard(has_city_setting: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="\U0001f30d Вся Россия", callback_data="city_all")],
    ]
    if has_city_setting:
        rows.append([InlineKeyboardButton(
            text="\U0001f4cd Использовать город из настроек",
            callback_data="city_from_settings",
        )])
    rows.append([InlineKeyboardButton(
        text="\u270f\ufe0f Ввести город",
        callback_data="city_enter",
    )])
    rows.append([InlineKeyboardButton(text="\u274c Отмена", callback_data="item_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_built_url_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Использовать эту ссылку", callback_data="built_url_ok"),
            InlineKeyboardButton(text="\u270f\ufe0f Изменить", callback_data="built_url_edit"),
        ],
        [InlineKeyboardButton(text="\u274c Отмена", callback_data="item_cancel")],
    ])


def item_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Подтвердить", callback_data="item_confirm"),
            InlineKeyboardButton(text="\u270f\ufe0f Изменить", callback_data="item_edit_restart"),
            InlineKeyboardButton(text="\u274c Отмена", callback_data="item_cancel"),
        ],
    ])


# --- Categories screens ---

def categories_list_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        status = "\u2705" if cat.get("is_active", 1) else "\u23f8"
        count = cat.get("items_count", 0)
        text = f"{status} {cat['name']} \u2014 {count} тов."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"cat_manage_{cat['id']}",
        )])
    rows.append([InlineKeyboardButton(
        text="\u2795 Новая категория",
        callback_data="category_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_manage_keyboard(category: dict, items_count: int, active_count: int) -> InlineKeyboardMarkup:
    cat_id = category["id"]
    has_items = items_count > 0
    all_active = active_count == items_count and items_count > 0

    rows: list[list[InlineKeyboardButton]] = []

    if has_items:
        if all_active:
            rows.append([InlineKeyboardButton(
                text="\u23f8 Выключить все",
                callback_data=f"cat_deactivate_all_{cat_id}",
            )])
        else:
            rows.append([InlineKeyboardButton(
                text="\u25b6\ufe0f Включить все",
                callback_data=f"cat_activate_all_{cat_id}",
            )])

    rows.append([InlineKeyboardButton(
        text="\U0001f4cb Список товаров",
        callback_data=f"cat_items_{cat_id}_0",
    )])
    rows.append([
        InlineKeyboardButton(
            text="\u270f\ufe0f Переименовать",
            callback_data=f"cat_rename_{cat_id}",
        ),
        InlineKeyboardButton(
            text="\U0001f5d1 Удалить категорию",
            callback_data=f"cat_delete_{cat_id}",
        ),
    ])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="categories_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_category_keyboard(category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u2705 Да, удалить",
                callback_data=f"cat_delete_confirm_{category_id}",
            ),
            InlineKeyboardButton(
                text="\u274c Отмена",
                callback_data=f"cat_manage_{category_id}",
            ),
        ],
    ])


# --- Items navigation ---

def categories_nav_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        active = cat.get("active_count", 0)
        total = cat.get("items_count", 0)
        rows.append([InlineKeyboardButton(
            text=f"{cat['name']} \u2014 {active}/{total} акт.",
            callback_data=f"cat_items_{cat['id']}_0",
        )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_items_keyboard(
    items: list[dict],
    category_id: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        status = "\u2705" if item["is_active"] else "\u23f8"
        text = f"{status} {item['name']} \u2014 {item['threshold_price']:,}\u20bd"
        if len(text) > 60:
            text = text[:57] + "..."
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"item_view_{item['id']}",
        )])

    # Pagination
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="\u25c0\ufe0f",
            callback_data=f"cat_items_{category_id}_{page - 1}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="noop",
    ))
    if (page + 1) * ITEMS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(
            text="\u25b6\ufe0f",
            callback_data=f"cat_items_{category_id}_{page + 1}",
        ))
    if total_pages > 1:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton(text="\u2795 Добавить товар", callback_data="item_add"),
        InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="items_list"),
    ])
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
                text="\u270f\ufe0f Перепродажа",
                callback_data=f"item_edit_market_{item['id']}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="\U0001f517 Изменить ссылку",
                callback_data=f"item_edit_url_{item['id']}",
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
            text="\u2b05\ufe0f Назад",
            callback_data=f"cat_items_{item['category_id']}_0",
        )],
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


# --- Settings ---

def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f30d Город", callback_data="setting_city"),
            InlineKeyboardButton(text="\u23f1 Интервал", callback_data="setting_interval"),
        ],
        [
            InlineKeyboardButton(text="\U0001f464 Фильтр продавцов", callback_data="setting_max_seller"),
            InlineKeyboardButton(text="\U0001f4e1 Прокси", callback_data="setting_proxy"),
        ],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


# --- Misc ---

def back_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


def ad_alert_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f517 Открыть объявление", url=url)],
    ])
