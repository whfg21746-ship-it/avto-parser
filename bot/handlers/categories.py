import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    back_main_keyboard,
    categories_list_keyboard,
    category_manage_keyboard,
    confirm_delete_category_keyboard,
)
from bot.states.item_states import AddCategoryFSM, RenameCategoryFSM
from db.models import (
    add_category,
    delete_category,
    get_active_items_count_by_category,
    get_all_categories,
    get_category,
    get_items_count_by_category,
    rename_category,
    set_category_items_active,
)

logger = logging.getLogger(__name__)
router = Router()


async def _categories_with_counts() -> list[dict]:
    categories = await get_all_categories()
    result = []
    for cat in categories:
        count = await get_items_count_by_category(cat["id"])
        result.append({**cat, "items_count": count})
    return result


# --- Categories List ---

@router.callback_query(F.data == "categories_list")
async def show_categories(callback: CallbackQuery) -> None:
    cats = await _categories_with_counts()
    text = "\U0001f4c1 Мои категории:"
    if not cats:
        text += "\n\nПока нет категорий."
    await callback.message.edit_text(text, reply_markup=categories_list_keyboard(cats))
    await callback.answer()


# --- Category Manage ---

@router.callback_query(F.data.startswith("cat_manage_"))
async def manage_category(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split("_")[-1])
    category = await get_category(cat_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    total = await get_items_count_by_category(cat_id)
    active = await get_active_items_count_by_category(cat_id)

    text = f"\U0001f4c1 {category['name']} ({total} товаров, {active} активных)"
    await callback.message.edit_text(
        text,
        reply_markup=category_manage_keyboard(category, total, active),
    )
    await callback.answer()


# --- Enable/Disable All Items in Category ---

@router.callback_query(F.data.startswith("cat_activate_all_"))
async def activate_all_items(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split("_")[-1])
    await set_category_items_active(cat_id, True)

    category = await get_category(cat_id)
    total = await get_items_count_by_category(cat_id)
    active = await get_active_items_count_by_category(cat_id)

    text = f"\U0001f4c1 {category['name']} ({total} товаров, {active} активных)"
    await callback.message.edit_text(
        text,
        reply_markup=category_manage_keyboard(category, total, active),
    )
    await callback.answer("\u25b6\ufe0f Все товары включены")


@router.callback_query(F.data.startswith("cat_deactivate_all_"))
async def deactivate_all_items(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split("_")[-1])
    await set_category_items_active(cat_id, False)

    category = await get_category(cat_id)
    total = await get_items_count_by_category(cat_id)
    active = await get_active_items_count_by_category(cat_id)

    text = f"\U0001f4c1 {category['name']} ({total} товаров, {active} активных)"
    await callback.message.edit_text(
        text,
        reply_markup=category_manage_keyboard(category, total, active),
    )
    await callback.answer("\u23f8 Все товары выключены")


# --- Rename Category ---

@router.callback_query(F.data.startswith("cat_rename_"))
async def start_rename(callback: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(callback.data.split("_")[-1])
    category = await get_category(cat_id)
    if not category:
        await callback.answer("Категория не найдена")
        return
    await state.set_state(RenameCategoryFSM.entering_name)
    await state.update_data(rename_cat_id=cat_id)
    await callback.message.edit_text(
        f"Текущее название: \u00ab{category['name']}\u00bb\n\nВведи новое название:",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(RenameCategoryFSM.entering_name)
async def process_rename(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым:")
        return

    data = await state.get_data()
    cat_id = data["rename_cat_id"]
    await rename_category(cat_id, name)
    await state.clear()

    category = await get_category(cat_id)
    total = await get_items_count_by_category(cat_id)
    active = await get_active_items_count_by_category(cat_id)

    await message.answer(
        f"\u2705 Категория переименована!\n\n"
        f"\U0001f4c1 {category['name']} ({total} товаров, {active} активных)",
        reply_markup=category_manage_keyboard(category, total, active),
    )


# --- Delete Category ---

@router.callback_query(F.data.startswith("cat_delete_") & ~F.data.startswith("cat_delete_confirm_"))
async def confirm_delete_cat(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split("_")[-1])
    category = await get_category(cat_id)
    if not category:
        await callback.answer("Категория не найдена")
        return
    total = await get_items_count_by_category(cat_id)
    await callback.message.edit_text(
        f"Удалить категорию \u00ab{category['name']}\u00bb?\n\n"
        f"Будет удалено {total} товаров и все их объявления.",
        reply_markup=confirm_delete_category_keyboard(cat_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_delete_confirm_"))
async def do_delete_category(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split("_")[-1])
    await delete_category(cat_id)
    await callback.answer("\U0001f5d1 Категория удалена")

    cats = await _categories_with_counts()
    text = "\U0001f4c1 Мои категории:"
    if not cats:
        text += "\n\nПока нет категорий."
    await callback.message.edit_text(text, reply_markup=categories_list_keyboard(cats))


# --- Add Category (standalone) ---

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

    await add_category(name)
    await state.clear()

    cats = await _categories_with_counts()
    await message.answer(
        f"\u2705 Категория \u00ab{name}\u00bb добавлена!",
    )
    await message.answer(
        "\U0001f4c1 Мои категории:",
        reply_markup=categories_list_keyboard(cats),
    )
