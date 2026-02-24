import json
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    ITEMS_PER_PAGE,
    back_main_keyboard,
    categories_keyboard,
    categories_list_keyboard,
    categories_nav_keyboard,
    category_items_keyboard,
    confirm_delete_keyboard,
    item_confirm_keyboard,
    item_detail_keyboard,
    main_menu,
)
from bot.states.item_states import AddCategoryFSM, AddItemFSM, EditItemFSM
from db.models import (
    add_category,
    add_item,
    delete_item,
    get_active_categories,
    get_all_categories,
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


def _item_detail_text(item: dict, stats: dict) -> str:
    status = "\u2705 Активен" if item["is_active"] else "\u23f8 Выключен"
    return (
        f"📦 {item['name']}\n\n"
        f"Статус: {status}\n"
        f"Категория: {item.get('category_name', 'N/A')}\n"
        f"Поиск: {item.get('search_query', item['name'])}\n"
        f"Порог: {item['threshold_price']:,}\u20bd\n"
        f"Рыночная: {item['market_price']:,}\u20bd\n"
        f"Профит: ~{item['market_price'] - item['threshold_price']:,}\u20bd\n"
        f"Найдено: {stats['total']}  |  Алертов: {stats['alerted']}"
    )


# --- Noop (pagination label) ---

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


# --- Items List (categories as navigation) ---

@router.callback_query(F.data == "items_list")
async def show_items_list(callback: CallbackQuery) -> None:
    categories = await get_all_categories()
    cats_data = []
    for cat in categories:
        count = await get_items_count_by_category(cat["id"])
        from db.database import get_db
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT COUNT(*) FROM items WHERE category_id = ? AND is_active = 1",
                (cat["id"],),
            )
            active = (await cur.fetchone())[0]
        finally:
            await db.close()
        cats_data.append({**cat, "items_count": count, "active_count": active})

    total = sum(c["items_count"] for c in cats_data)
    active = sum(c["active_count"] for c in cats_data)
    text = f"📦 Мои товары ({active}/{total} активных)\n\nВыбери категорию:"
    await callback.message.edit_text(text, reply_markup=categories_nav_keyboard(cats_data))
    await callback.answer()


# --- Category Items (from "Мои товары") ---

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
    text = f"📦 {category['name']} ({total} тов.)"
    await callback.message.edit_text(
        text,
        reply_markup=category_items_keyboard(items, category_id, page, total, source="cat_items"),
    )
    await callback.answer()


# --- Category Items (from "Категории") ---

@router.callback_query(F.data.startswith("cat_view_"))
async def show_category_view(callback: CallbackQuery) -> None:
    parts = callback.data.split("_")
    category_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    category = await get_category(category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    total = await get_items_count_by_category(category_id)
    items = await get_items_by_category(category_id, offset=page * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)
    text = f"📁 {category['name']} (avito ID: {category['avito_category_id']}) — {total} тов."
    await callback.message.edit_text(
        text,
        reply_markup=category_items_keyboard(items, category_id, page, total, source="cat_view"),
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
    await callback.answer("🗑 Товар удалён")

    if cat_id:
        total = await get_items_count_by_category(cat_id)
        items = await get_items_by_category(cat_id, offset=0, limit=ITEMS_PER_PAGE)
        category = await get_category(cat_id)
        text = f"📦 {category['name']} ({total} тов.)" if category else "📦 Товары"
        await callback.message.edit_text(
            text,
            reply_markup=category_items_keyboard(items, cat_id, 0, total, source="cat_items"),
        )
    else:
        await callback.message.edit_text("🗑 Товар удалён.", reply_markup=back_main_keyboard())


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
        f"Текущая рыночная: {current}\n\nВведи новую рыночную цену (в \u20bd):",
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
        f"\u2705 Рыночная цена обновлена!\n\n" + _item_detail_text(item, stats),
        reply_markup=item_detail_keyboard(item),
    )


# --- Add Item Flow ---

@router.callback_query(F.data == "item_add")
async def start_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    categories = await get_active_categories()
    if not categories:
        await callback.answer("Сначала добавьте категорию!")
        return
    await state.set_state(AddItemFSM.choosing_category)
    await callback.message.edit_text(
        "Выбери категорию:",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_select_"), AddItemFSM.choosing_category)
async def category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split("_")[-1])
    category = await get_category(category_id)
    await state.update_data(category_id=category_id, category_name=category["name"])
    await state.set_state(AddItemFSM.entering_name)
    await callback.message.edit_text("Введи название товара:")
    await callback.answer()


@router.message(AddItemFSM.entering_name)
async def item_name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуй снова:")
        return
    await state.update_data(item_name=name)
    await state.set_state(AddItemFSM.entering_avito_params)
    await message.answer(
        "Введи параметры фильтра Avito (JSON):\n"
        'Пример: {"params[110012]": "123456"}\n\n'
        'Или отправь "skip" чтобы использовать текстовый поиск.'
    )


@router.message(AddItemFSM.entering_avito_params)
async def avito_params_entered(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.lower() == "skip":
        await state.update_data(avito_params="{}")
    else:
        try:
            json.loads(text)
            await state.update_data(avito_params=text)
        except json.JSONDecodeError:
            await message.answer('Некорректный JSON. Попробуй снова или отправь "skip":')
            return
    await state.set_state(AddItemFSM.entering_threshold)
    await message.answer("Введи пороговую цену (макс. цена покупки в \u20bd):")


@router.message(AddItemFSM.entering_threshold)
async def threshold_entered(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("Некорректная цена. Введи число:")
        return
    await state.update_data(threshold_price=price)
    await state.set_state(AddItemFSM.entering_market_price)
    await message.answer("Введи рыночную цену продажи в \u20bd:")


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
    text = (
        f"📦 Новый товар:\n\n"
        f"Название: {data['item_name']}\n"
        f"Категория: {data['category_name']}\n"
        f"Порог: {data['threshold_price']:,}\u20bd\n"
        f"Рыночная цена: {data['market_price']:,}\u20bd\n"
        f"Примерный профит: ~{profit:,}\u20bd"
    )
    await message.answer(text, reply_markup=item_confirm_keyboard())


@router.callback_query(F.data == "item_confirm", AddItemFSM.confirming)
async def confirm_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await add_item(
        category_id=data["category_id"],
        name=data["item_name"],
        threshold_price=data["threshold_price"],
        market_price=data["market_price"],
        search_query=data["item_name"],
        avito_params=data.get("avito_params", "{}"),
    )
    await state.clear()
    await callback.message.edit_text("\u2705 Товар добавлен!")
    await callback.answer()

    cat_id = data["category_id"]
    total = await get_items_count_by_category(cat_id)
    items = await get_items_by_category(cat_id, offset=0, limit=ITEMS_PER_PAGE)
    category = await get_category(cat_id)
    text = f"📦 {category['name']} ({total} тов.)"
    await callback.message.answer(
        text,
        reply_markup=category_items_keyboard(items, cat_id, 0, total, source="cat_items"),
    )


@router.callback_query(F.data == "item_edit_restart", AddItemFSM.confirming)
async def restart_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    categories = await get_active_categories()
    await state.set_state(AddItemFSM.choosing_category)
    await callback.message.edit_text(
        "Выбери категорию:",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data == "item_cancel")
async def cancel_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    monitoring = await get_setting("monitoring_enabled")
    is_active = monitoring == "true"
    await callback.message.edit_text(
        "🔍 Avito Flipper Bot",
        reply_markup=main_menu(is_active),
    )
    await callback.answer("\u274c Отменено")


# --- Categories Management ---

@router.callback_query(F.data == "categories_list")
async def show_categories(callback: CallbackQuery) -> None:
    categories = await get_all_categories()
    cats_with_counts = []
    for cat in categories:
        count = await get_items_count_by_category(cat["id"])
        cats_with_counts.append({**cat, "items_count": count})

    text = "📁 Категории:"
    if not categories:
        text += "\n\nПока нет категорий."
    await callback.message.edit_text(
        text,
        reply_markup=categories_list_keyboard(cats_with_counts),
    )
    await callback.answer()


@router.callback_query(F.data == "category_add")
async def start_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategoryFSM.entering_name)
    await callback.message.edit_text(
        "Введи название категории:",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(AddCategoryFSM.entering_name)
async def category_name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым:")
        return
    await state.update_data(cat_name=name)
    await state.set_state(AddCategoryFSM.entering_avito_id)
    await message.answer("Введи Avito categoryId:")


@router.message(AddCategoryFSM.entering_avito_id)
async def category_id_entered(message: Message, state: FSMContext) -> None:
    try:
        avito_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("Некорректный ID. Введи число:")
        return

    data = await state.get_data()
    await add_category(data["cat_name"], avito_id)
    await state.clear()
    await message.answer(
        f"\u2705 Категория \u00ab{data['cat_name']}\u00bb добавлена!",
        reply_markup=back_main_keyboard(),
    )
