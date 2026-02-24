from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(monitoring_active: bool = False) -> InlineKeyboardMarkup:
    toggle_text = "\u23f8 \u041f\u0430\u0443\u0437\u0430 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433\u0430" if monitoring_active else "\u25b6\ufe0f \u0421\u0442\u0430\u0440\u0442 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433\u0430"
    toggle_cb = "monitoring_off" if monitoring_active else "monitoring_on"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 \u041c\u043e\u0438 \u0442\u043e\u0432\u0430\u0440\u044b", callback_data="items_list"),
            InlineKeyboardButton(text="\u2795 \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0442\u043e\u0432\u0430\u0440", callback_data="item_add"),
        ],
        [
            InlineKeyboardButton(text="📁 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438", callback_data="categories_list"),
            InlineKeyboardButton(text="\u2699\ufe0f \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", callback_data="settings"),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
        ],
    ])


def categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
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
        text="\u2795 \u041d\u043e\u0432\u0430\u044f \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
        callback_data="category_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_list_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([InlineKeyboardButton(
            text=f"{cat['name']} (ID: {cat['avito_category_id']}) \u2014 {cat['items_count']} \u0442\u043e\u0432.",
            callback_data=f"cat_view_{cat['id']}",
        )])
    rows.append([InlineKeyboardButton(
        text="\u2795 \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e",
        callback_data="category_add",
    )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 \u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c", callback_data="item_confirm"),
            InlineKeyboardButton(text="\u270f\ufe0f \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c", callback_data="item_edit_restart"),
            InlineKeyboardButton(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data="item_cancel"),
        ],
    ])


def items_list_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, item in enumerate(items, 1):
        status = "\u2705" if item["is_active"] else "\u23f8"
        suffix = "" if item["is_active"] else " (\u0432\u044b\u043a\u043b)"
        text = f"{idx}. {status} {item['name']} \u2014 \u043f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd{suffix}"
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"item_view_{item['id']}",
        )])
    rows.append([InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_detail_keyboard(item: dict) -> InlineKeyboardMarkup:
    toggle_text = "\u23f8 \u0412\u044b\u043a\u043b\u044e\u0447\u0438\u0442\u044c" if item["is_active"] else "\u25b6\ufe0f \u0412\u043a\u043b\u044e\u0447\u0438\u0442\u044c"
    toggle_cb = f"item_deactivate_{item['id']}" if item["is_active"] else f"item_activate_{item['id']}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u270f\ufe0f \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u043f\u043e\u0440\u043e\u0433",
                callback_data=f"item_edit_threshold_{item['id']}",
            ),
            InlineKeyboardButton(
                text="\u270f\ufe0f \u0418\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u0440\u044b\u043d\u043e\u0447\u043d\u0443\u044e",
                callback_data=f"item_edit_market_{item['id']}",
            ),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb),
            InlineKeyboardButton(
                text="🗑 \u0423\u0434\u0430\u043b\u0438\u0442\u044c",
                callback_data=f"item_delete_{item['id']}",
            ),
        ],
        [InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="items_list")],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 \u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b", callback_data="setting_interval"),
            InlineKeyboardButton(text="📡 \u041f\u0440\u043e\u043a\u0441\u0438", callback_data="setting_proxy"),
            InlineKeyboardButton(text="👤 \u0424\u0438\u043b\u044c\u0442\u0440 \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u043e\u0432", callback_data="setting_max_seller"),
        ],
        [InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="back_main")],
    ])


def back_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="back_main")],
    ])


def ad_alert_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0435", url=url)],
    ])


def confirm_delete_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="\u2705 \u0414\u0430, \u0443\u0434\u0430\u043b\u0438\u0442\u044c",
                callback_data=f"item_delete_confirm_{item_id}",
            ),
            InlineKeyboardButton(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data=f"item_view_{item_id}"),
        ],
    ])
