import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    back_main_keyboard,
    categories_keyboard,
    confirm_delete_sq_keyboard,
    search_queries_list_keyboard,
    search_query_confirm_keyboard,
    search_query_detail_keyboard,
)
from bot.states.item_states import AddSearchQueryFSM
from db.models import (
    add_search_query,
    delete_search_query,
    get_active_categories,
    get_all_search_queries,
    get_category,
    get_items_count_by_search_query,
    get_search_query,
    get_setting,
    update_search_query_field,
)

logger = logging.getLogger(__name__)
router = Router()


# --- Search Queries List ---

@router.callback_query(F.data == "search_queries_list")
async def show_search_queries(callback: CallbackQuery) -> None:
    queries = await get_all_search_queries()
    for sq in queries:
        sq["items_count"] = await get_items_count_by_search_query(sq["id"])

    total = sum(sq["items_count"] for sq in queries)
    active = sum(1 for sq in queries if sq["is_active"])

    text = (
        f"\U0001f50d Поисковые запросы ({active}/{len(queries)} активных)\n"
        f"Всего моделей: {total}\n\n"
        "Каждый запрос — одно обращение к Avito API."
    )
    await callback.message.edit_text(
        text, reply_markup=search_queries_list_keyboard(queries)
    )
    await callback.answer()


# --- Search Query Detail ---

@router.callback_query(F.data.startswith("sq_view_"))
async def show_sq_detail(callback: CallbackQuery) -> None:
    query_id = int(callback.data.split("_")[-1])
    sq = await get_search_query(query_id)
    if not sq:
        await callback.answer("Запрос не найден")
        return

    items_count = await get_items_count_by_search_query(query_id)
    status = "\u2705 Активен" if sq["is_active"] else "\u23f8 Выключен"
    cat_name = sq.get("category_name", "N/A")
    avito_cat = sq.get("avito_category_id") or "не задан"
    price_max = f"{sq['price_max']:,}\u20bd" if sq.get("price_max") else "не задан"

    text = (
        f'\U0001f50d Запрос: "{sq["keyword"]}"\n\n'
        f"Статус: {status}\n"
        f"Категория: {cat_name}\n"
        f"Avito categoryId: {avito_cat}\n"
        f"Макс. цена: {price_max}\n"
        f"Моделей: {items_count}"
    )
    await callback.message.edit_text(
        text, reply_markup=search_query_detail_keyboard(sq)
    )
    await callback.answer()


# --- Toggle Search Query ---

@router.callback_query(F.data.startswith("sq_activate_"))
async def activate_sq(callback: CallbackQuery) -> None:
    query_id = int(callback.data.split("_")[-1])
    await update_search_query_field(query_id, "is_active", 1)
    sq = await get_search_query(query_id)
    if not sq:
        await callback.answer("Запрос не найден")
        return
    items_count = await get_items_count_by_search_query(query_id)
    sq["items_count"] = items_count
    status = "\u2705 Активен"
    text = (
        f'\U0001f50d Запрос: "{sq["keyword"]}"\n\n'
        f"Статус: {status}\n"
        f"Моделей: {items_count}"
    )
    await callback.message.edit_text(
        text, reply_markup=search_query_detail_keyboard(sq)
    )
    await callback.answer("\u25b6\ufe0f Запрос включён")


@router.callback_query(F.data.startswith("sq_deactivate_"))
async def deactivate_sq(callback: CallbackQuery) -> None:
    query_id = int(callback.data.split("_")[-1])
    await update_search_query_field(query_id, "is_active", 0)
    sq = await get_search_query(query_id)
    if not sq:
        await callback.answer("Запрос не найден")
        return
    items_count = await get_items_count_by_search_query(query_id)
    sq["items_count"] = items_count
    status = "\u23f8 Выключен"
    text = (
        f'\U0001f50d Запрос: "{sq["keyword"]}"\n\n'
        f"Статус: {status}\n"
        f"Моделей: {items_count}"
    )
    await callback.message.edit_text(
        text, reply_markup=search_query_detail_keyboard(sq)
    )
    await callback.answer("\u23f8 Запрос выключен")


# --- Delete Search Query ---

@router.callback_query(F.data.startswith("sq_delete_") & ~F.data.startswith("sq_delete_confirm_"))
async def confirm_delete_sq(callback: CallbackQuery) -> None:
    query_id = int(callback.data.split("_")[-1])
    sq = await get_search_query(query_id)
    if not sq:
        await callback.answer("Запрос не найден")
        return
    items_count = await get_items_count_by_search_query(query_id)
    await callback.message.edit_text(
        f'Удалить запрос \u00ab{sq["keyword"]}\u00bb?\n\n'
        f"Будет удалено {items_count} связанных моделей и все их объявления.",
        reply_markup=confirm_delete_sq_keyboard(query_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sq_delete_confirm_"))
async def do_delete_sq(callback: CallbackQuery) -> None:
    query_id = int(callback.data.split("_")[-1])
    await delete_search_query(query_id)
    await callback.answer("\U0001f5d1 Запрос удалён")

    queries = await get_all_search_queries()
    for sq in queries:
        sq["items_count"] = await get_items_count_by_search_query(sq["id"])
    await callback.message.edit_text(
        "\U0001f50d Поисковые запросы",
        reply_markup=search_queries_list_keyboard(queries),
    )


# --- Add Search Query ---

@router.callback_query(F.data == "sq_add")
async def start_add_sq(callback: CallbackQuery, state: FSMContext) -> None:
    categories = await get_active_categories()
    if not categories:
        await callback.answer("Сначала добавьте категорию!")
        return
    await state.set_state(AddSearchQueryFSM.choosing_category)
    await callback.message.edit_text(
        "Выбери категорию для нового поискового запроса:",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_select_"), AddSearchQueryFSM.choosing_category)
async def sq_category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split("_")[-1])
    category = await get_category(category_id)
    await state.update_data(
        sq_category_id=category_id,
        sq_category_name=category["name"],
    )
    await state.set_state(AddSearchQueryFSM.entering_keyword)
    await callback.message.edit_text(
        'Введи ключевое слово для поиска (например: "iphone", "macbook", "airpods"):',
    )
    await callback.answer()


@router.message(AddSearchQueryFSM.entering_keyword)
async def sq_keyword_entered(message: Message, state: FSMContext) -> None:
    keyword = message.text.strip().lower()
    if not keyword:
        await message.answer("Ключевое слово не может быть пустым:")
        return
    await state.update_data(sq_keyword=keyword)
    await state.set_state(AddSearchQueryFSM.entering_avito_category_id)
    await message.answer(
        "Введи Avito categoryId (число) или отправь 0 для автоопределения:\n\n"
        "Примеры: 84 (телефоны), 17 (ноутбуки), 31 (наушники), 137 (планшеты)"
    )


@router.message(AddSearchQueryFSM.entering_avito_category_id)
async def sq_avito_cat_entered(message: Message, state: FSMContext) -> None:
    try:
        avito_cat = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return
    await state.update_data(sq_avito_category_id=avito_cat if avito_cat > 0 else None)
    await state.set_state(AddSearchQueryFSM.entering_price_max)
    await message.answer(
        "Введи максимальную цену для поискового запроса (в \u20bd).\n"
        "Это потолок цены в API-запросе (ставь с запасом выше самого дорогого товара):"
    )


@router.message(AddSearchQueryFSM.entering_price_max)
async def sq_price_max_entered(message: Message, state: FSMContext) -> None:
    try:
        price_max = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return
    await state.update_data(sq_price_max=price_max)
    await state.set_state(AddSearchQueryFSM.confirming)

    data = await state.get_data()
    avito_cat = data.get("sq_avito_category_id") or "авто"
    text = (
        f"\U0001f50d Новый поисковый запрос:\n\n"
        f'Ключевое слово: "{data["sq_keyword"]}"\n'
        f"Категория: {data['sq_category_name']}\n"
        f"Avito categoryId: {avito_cat}\n"
        f"Макс. цена: {data['sq_price_max']:,}\u20bd"
    )
    await message.answer(text, reply_markup=search_query_confirm_keyboard())


@router.callback_query(F.data == "sq_confirm", AddSearchQueryFSM.confirming)
async def confirm_add_sq(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await add_search_query(
        category_id=data["sq_category_id"],
        keyword=data["sq_keyword"],
        avito_category_id=data.get("sq_avito_category_id"),
        price_max=data.get("sq_price_max"),
    )
    await state.clear()
    await callback.message.edit_text("\u2705 Поисковый запрос добавлен!")
    await callback.answer()

    queries = await get_all_search_queries()
    for sq in queries:
        sq["items_count"] = await get_items_count_by_search_query(sq["id"])
    await callback.message.answer(
        "\U0001f50d Поисковые запросы",
        reply_markup=search_queries_list_keyboard(queries),
    )


@router.callback_query(F.data == "sq_cancel")
async def cancel_add_sq(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    from bot.keyboards.menus import main_menu
    monitoring = await get_setting("monitoring_enabled")
    is_active = monitoring == "true"
    await callback.message.edit_text(
        "\U0001f50d Avito Flipper Bot",
        reply_markup=main_menu(is_active),
    )
    await callback.answer("\u274c Отменено")
