import logging
from urllib.parse import urlparse, urlencode

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    ITEMS_PER_PAGE,
    add_item_method_keyboard,
    back_main_keyboard,
    categories_nav_keyboard,
    category_items_keyboard,
    category_picker_keyboard,
    city_picker_keyboard,
    confirm_built_url_keyboard,
    confirm_delete_keyboard,
    item_confirm_keyboard,
    item_detail_keyboard,
    main_menu,
)
from bot.states.item_states import AddItemFSM, EditItemFSM
from db.models import (
    add_category,
    add_item,
    delete_item,
    get_active_items_count_by_category,
    get_all_categories,
    get_all_items,
    get_category,
    get_item,
    get_item_stats,
    get_items_by_category,
    get_items_count_by_category,
    get_setting,
    update_item_field,
)

logger = logging.getLogger(__name__)
router = Router()


def _is_avito_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
        return parsed.scheme in ("http", "https") and "avito.ru" in (parsed.netloc or "")
    except Exception:
        return False


def _shorten_url(url: str, max_len: int = 50) -> str:
    parsed = urlparse(url)
    short = parsed.netloc + parsed.path
    if len(short) > max_len:
        short = short[:max_len - 3] + "..."
    return short


def _item_detail_text(item: dict, stats: dict) -> str:
    status = "\u2705 Активен" if item["is_active"] else "\u23f8 Выключен"
    profit = item["market_price"] - item["threshold_price"]
    url_short = _shorten_url(item.get("avito_url", ""))
    return (
        f"\U0001f4e6 {item['name']}\n\n"
        f"Статус: {status}\n"
        f"Категория: {item.get('category_name', 'N/A')}\n"
        f"Ссылка: {url_short}\n"
        f"Порог: {item['threshold_price']:,}\u20bd\n"
        f"Перепродажа: {item['market_price']:,}\u20bd\n"
        f"Профит: ~{profit:,}\u20bd\n"
        f"Найдено: {stats['total']}  |  Алертов: {stats['alerted']}"
    )


# --- Items List (categories as navigation) ---

@router.callback_query(F.data == "items_list")
async def show_items_list(callback: CallbackQuery) -> None:
    categories = await get_all_categories()
    cats_data = []
    for cat in categories:
        count = await get_items_count_by_category(cat["id"])
        active = await get_active_items_count_by_category(cat["id"])
        cats_data.append({**cat, "items_count": count, "active_count": active})

    # Filter out empty categories in items view
    cats_data = [c for c in cats_data if c["items_count"] > 0]

    if not cats_data:
        await callback.message.edit_text(
            "\U0001f4e6 Нет товаров.\n\n"
            'Нажмите "Добавить товар" чтобы начать.',
            reply_markup=back_main_keyboard(),
        )
        await callback.answer()
        return

    total = sum(c["items_count"] for c in cats_data)
    active = sum(c["active_count"] for c in cats_data)
    text = f"\U0001f4e6 Мои товары ({active}/{total} активных)\n\nВыбери категорию:"
    await callback.message.edit_text(text, reply_markup=categories_nav_keyboard(cats_data))
    await callback.answer()


# --- Category Items ---

@router.callback_query(F.data.startswith("cat_items_"))
async def show_category_items(callback: CallbackQuery) -> None:
    parts = callback.data.split("_")
    category_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    category = await get_category(category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    total = await get_items_count_by_category(category_id)
    items = await get_items_by_category(category_id, offset=page * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)
    text = f"\U0001f4c1 {category['name']} ({total} тов.)"
    await callback.message.edit_text(
        text,
        reply_markup=category_items_keyboard(items, category_id, page, total),
    )
    await callback.answer()


# --- Item Detail ---

@router.callback_query(F.data.startswith("item_view_"))
async def show_item_detail(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    if not item:
        await callback.answer("Товар не найден")
        return
    stats = await get_item_stats(item_id)
    await callback.message.edit_text(
        _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )
    await callback.answer()


# --- Toggle Item ---

@router.callback_query(F.data.startswith("item_activate_"))
async def activate_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    await update_item_field(item_id, "is_active", 1)
    item = await get_item(item_id)
    if not item:
        await callback.answer("Товар не найден")
        return
    stats = await get_item_stats(item_id)
    await callback.message.edit_text(
        _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )
    await callback.answer("\u25b6\ufe0f Товар включён")


@router.callback_query(F.data.startswith("item_deactivate_"))
async def deactivate_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    await update_item_field(item_id, "is_active", 0)
    item = await get_item(item_id)
    if not item:
        await callback.answer("Товар не найден")
        return
    stats = await get_item_stats(item_id)
    await callback.message.edit_text(
        _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )
    await callback.answer("\u23f8 Товар выключен")


# --- Delete Item ---

@router.callback_query(F.data.startswith("item_delete_") & ~F.data.startswith("item_delete_confirm_"))
async def confirm_delete(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    if not item:
        await callback.answer("Товар не найден")
        return
    await callback.message.edit_text(
        f"Удалить товар \u00ab{item['name']}\u00bb?\n\nВсе найденные объявления тоже будут удалены.",
        reply_markup=confirm_delete_keyboard(item_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item_delete_confirm_"))
async def do_delete_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    cat_id = item["category_id"] if item else None
    await delete_item(item_id)
    await callback.answer("\U0001f5d1 Товар удалён")

    if cat_id:
        total = await get_items_count_by_category(cat_id)
        items = await get_items_by_category(cat_id, offset=0, limit=ITEMS_PER_PAGE)
        category = await get_category(cat_id)
        text = f"\U0001f4c1 {category['name']} ({total} тов.)" if category else "\U0001f4e6 Товары"
        await callback.message.edit_text(
            text,
            reply_markup=category_items_keyboard(items, cat_id, 0, total),
        )
    else:
        await callback.message.edit_text("\U0001f5d1 Товар удалён.", reply_markup=back_main_keyboard())


# --- Edit Threshold ---

@router.callback_query(F.data.startswith("item_edit_threshold_"))
async def start_edit_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    await state.set_state(EditItemFSM.entering_threshold)
    await state.update_data(edit_item_id=item_id)
    current = f"{item['threshold_price']:,}\u20bd" if item else "?"
    await callback.message.edit_text(
        f"Текущий порог: {current}\n\nВведи новую пороговую цену (в \u20bd):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(EditItemFSM.entering_threshold)
async def process_edit_threshold(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Некорректная цена. Введи число:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]
    await update_item_field(item_id, "threshold_price", price)
    await state.clear()

    item = await get_item(item_id)
    stats = await get_item_stats(item_id)
    await message.answer(
        f"\u2705 Порог обновлён!\n\n" + _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )


# --- Edit Market Price ---

@router.callback_query(F.data.startswith("item_edit_market_"))
async def start_edit_market(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    await state.set_state(EditItemFSM.entering_market_price)
    await state.update_data(edit_item_id=item_id)
    current = f"{item['market_price']:,}\u20bd" if item else "?"
    await callback.message.edit_text(
        f"Текущая перепродажа: {current}\n\nВведи новую цену перепродажи (в \u20bd):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(EditItemFSM.entering_market_price)
async def process_edit_market(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Некорректная цена. Введи число:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]
    await update_item_field(item_id, "market_price", price)
    await state.clear()

    item = await get_item(item_id)
    stats = await get_item_stats(item_id)
    await message.answer(
        f"\u2705 Цена перепродажи обновлена!\n\n" + _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )


# --- Edit URL ---

@router.callback_query(F.data.startswith("item_edit_url_"))
async def start_edit_url(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split("_")[-1])
    await state.set_state(EditItemFSM.entering_url)
    await state.update_data(edit_item_id=item_id)
    await callback.message.edit_text(
        "Вставь новую ссылку с Авито:",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(EditItemFSM.entering_url)
async def process_edit_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not _is_avito_url(url):
        await message.answer("Это не ссылка на Авито. Попробуй ещё раз:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]
    await update_item_field(item_id, "avito_url", url)
    await state.clear()

    item = await get_item(item_id)
    stats = await get_item_stats(item_id)
    await message.answer(
        f"\u2705 Ссылка обновлена!\n\n" + _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
        disable_web_page_preview=True,
    )


# =============================================================
# Add Item Flow
# =============================================================

@router.callback_query(F.data == "item_add")
async def start_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddItemFSM.choosing_method)
    await callback.message.edit_text(
        "\U0001f4e6 Добавление нового товара\n\nВыберите способ:",
        reply_markup=add_item_method_keyboard(),
    )
    await callback.answer()


# --- Method A: Paste URL ---

@router.callback_query(F.data == "add_method_url", AddItemFSM.choosing_method)
async def method_url(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddItemFSM.waiting_url)
    await callback.message.edit_text(
        "Откройте Авито, настройте фильтры (город, категория, модель, цена и т.д.) "
        "и скопируйте ссылку из адресной строки.\n\n"
        "Отправьте мне ссылку:"
    )
    await callback.answer()


@router.message(AddItemFSM.waiting_url)
async def url_pasted(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not _is_avito_url(url):
        await message.answer(
            "Это не ссылка на Авито. Ссылка должна начинаться с https://www.avito.ru/ или https://avito.ru/\n\n"
            "Попробуй ещё раз:"
        )
        return

    await state.update_data(avito_url=url)
    await state.set_state(AddItemFSM.entering_name)
    await message.answer("Введите название товара (для отображения в боте):")


# --- Method B: Build URL ---

@router.callback_query(F.data == "add_method_build", AddItemFSM.choosing_method)
async def method_build(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddItemFSM.entering_search_query)
    await callback.message.edit_text(
        "Что ищем? Введите поисковый запрос:"
    )
    await callback.answer()


@router.message(AddItemFSM.entering_search_query)
async def search_query_entered(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    if not query:
        await message.answer("Запрос не может быть пустым:")
        return
    await state.update_data(search_query=query)

    city = await get_setting("city")
    has_city = bool(city)
    await state.set_state(AddItemFSM.choosing_city)
    await message.answer(
        "Город/регион:",
        reply_markup=city_picker_keyboard(has_city_setting=has_city),
    )


@router.callback_query(F.data == "city_all", AddItemFSM.choosing_city)
async def city_all_russia(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(build_city_slug="rossiya")
    await state.set_state(AddItemFSM.entering_search_price_max)
    await callback.message.edit_text(
        "Максимальная цена в поиске (фильтр Авито) в \u20bd:"
    )
    await callback.answer()


@router.callback_query(F.data == "city_from_settings", AddItemFSM.choosing_city)
async def city_from_settings(callback: CallbackQuery, state: FSMContext) -> None:
    slug = await get_setting("city_slug") or "rossiya"
    await state.update_data(build_city_slug=slug)
    await state.set_state(AddItemFSM.entering_search_price_max)
    await callback.message.edit_text(
        "Максимальная цена в поиске (фильтр Авито) в \u20bd:"
    )
    await callback.answer()


@router.callback_query(F.data == "city_enter", AddItemFSM.choosing_city)
async def city_enter(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddItemFSM.entering_city)
    await callback.message.edit_text(
        "Введите название города латиницей (как в URL Авито).\n"
        "Примеры: moskva, sankt-peterburg, stavropol, krasnodar"
    )
    await callback.answer()


@router.message(AddItemFSM.entering_city)
async def city_entered(message: Message, state: FSMContext) -> None:
    slug = message.text.strip().lower().replace(" ", "-")
    if not slug:
        await message.answer("Город не может быть пустым:")
        return
    await state.update_data(build_city_slug=slug)
    await state.set_state(AddItemFSM.entering_search_price_max)
    await message.answer("Максимальная цена в поиске (фильтр Авито) в \u20bd:")


@router.message(AddItemFSM.entering_search_price_max)
async def search_price_max_entered(message: Message, state: FSMContext) -> None:
    try:
        pmax = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    data = await state.get_data()
    slug = data["build_city_slug"]
    query = data["search_query"]
    params = urlencode({"q": query, "pmax": str(pmax)})
    url = f"https://www.avito.ru/{slug}?{params}"

    await state.update_data(avito_url=url)
    await state.set_state(AddItemFSM.confirming_built_url)
    await message.answer(
        f"Собранная ссылка:\n{url}\n\n"
        "\u26a0\ufe0f Рекомендуем открыть эту ссылку в браузере и убедиться что результаты правильные.",
        reply_markup=confirm_built_url_keyboard(),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "built_url_ok", AddItemFSM.confirming_built_url)
async def built_url_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddItemFSM.entering_name)
    await callback.message.edit_text("Введите название товара (для отображения в боте):")
    await callback.answer()


@router.callback_query(F.data == "built_url_edit", AddItemFSM.confirming_built_url)
async def built_url_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddItemFSM.entering_search_query)
    await callback.message.edit_text("Что ищем? Введите поисковый запрос:")
    await callback.answer()


# --- Common steps (name -> category -> threshold -> market -> confirm) ---

@router.message(AddItemFSM.entering_name)
async def item_name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуй снова:")
        return

    await state.update_data(item_name=name)

    categories = await get_all_categories()
    await state.set_state(AddItemFSM.choosing_category)
    await message.answer(
        "Выберите или создайте категорию:",
        reply_markup=category_picker_keyboard(categories),
    )


@router.callback_query(F.data.startswith("cat_pick_"), AddItemFSM.choosing_category)
async def category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.split("cat_pick_")[1]
    if raw == "new":
        await state.set_state(AddItemFSM.entering_new_category)
        await callback.message.edit_text("Введите название категории:")
        await callback.answer()
        return

    category_id = int(raw)
    category = await get_category(category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    await state.update_data(category_id=category_id, category_name=category["name"])
    await state.set_state(AddItemFSM.entering_threshold)
    await callback.message.edit_text(
        "Введите максимальную цену покупки (порог) в \u20bd:"
    )
    await callback.answer()


@router.message(AddItemFSM.entering_new_category)
async def new_category_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым:")
        return

    cat_id = await add_category(name)
    await state.update_data(category_id=cat_id, category_name=name)
    await state.set_state(AddItemFSM.entering_threshold)
    await message.answer(
        f"\u2705 Категория \u00ab{name}\u00bb создана!\n\n"
        "Введите максимальную цену покупки (порог) в \u20bd:"
    )


@router.message(AddItemFSM.entering_threshold)
async def threshold_entered(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Некорректная цена. Введи число:")
        return
    await state.update_data(threshold_price=price)
    await state.set_state(AddItemFSM.entering_market_price)
    await message.answer("Введите примерную цену перепродажи в \u20bd:")


@router.message(AddItemFSM.entering_market_price)
async def market_price_entered(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Некорректная цена. Введи число:")
        return
    await state.update_data(market_price=price)
    await state.set_state(AddItemFSM.confirming)

    data = await state.get_data()
    profit = data["market_price"] - data["threshold_price"]
    url_short = _shorten_url(data["avito_url"])
    text = (
        f"\U0001f4e6 Новый товар:\n\n"
        f"Название: {data['item_name']}\n"
        f"Категория: {data['category_name']}\n"
        f"Ссылка: {url_short}\n"
        f"Порог: {data['threshold_price']:,}\u20bd\n"
        f"Перепродажа: ~{data['market_price']:,}\u20bd\n"
        f"Профит: ~{profit:,}\u20bd"
    )
    await message.answer(text, reply_markup=item_confirm_keyboard())


@router.callback_query(F.data == "item_confirm", AddItemFSM.confirming)
async def confirm_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await add_item(
        category_id=data["category_id"],
        name=data["item_name"],
        avito_url=data["avito_url"],
        threshold_price=data["threshold_price"],
        market_price=data["market_price"],
    )

    await state.clear()
    await callback.message.edit_text("\u2705 Товар добавлен!")
    await callback.answer()

    cat_id = data["category_id"]
    total = await get_items_count_by_category(cat_id)
    items = await get_items_by_category(cat_id, offset=0, limit=ITEMS_PER_PAGE)
    category = await get_category(cat_id)
    text = f"\U0001f4c1 {category['name']} ({total} тов.)"
    await callback.message.answer(
        text,
        reply_markup=category_items_keyboard(items, cat_id, 0, total),
    )


@router.callback_query(F.data == "item_edit_restart", AddItemFSM.confirming)
async def restart_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddItemFSM.choosing_method)
    await callback.message.edit_text(
        "\U0001f4e6 Добавление нового товара\n\nВыберите способ:",
        reply_markup=add_item_method_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "item_cancel")
async def cancel_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    monitoring = await get_setting("monitoring_enabled")
    is_active = monitoring == "true"
    items = await get_all_items()
    has_items = len(items) > 0

    if has_items:
        text = "\U0001f50d Avito Flipper Bot"
    else:
        text = (
            "\U0001f50d Avito Flipper Bot\n\n"
            "У вас пока нет отслеживаемых товаров.\n"
            'Нажмите "Добавить товар" чтобы начать.'
        )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu(is_active, has_items=has_items),
    )
    await callback.answer("\u274c Отменено")
