import json
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import (
    back_main_keyboard,
    categories_keyboard,
    categories_list_keyboard,
    confirm_delete_keyboard,
    item_confirm_keyboard,
    item_detail_keyboard,
    items_list_keyboard,
    main_menu,
)
from bot.states.item_states import AddCategoryFSM, AddItemFSM, EditItemFSM
from db.models import (
    add_category,
    add_item,
    delete_item,
    get_active_categories,
    get_all_categories,
    get_all_items,
    get_category,
    get_item,
    get_item_stats,
    get_items_count_by_category,
    get_setting,
    update_item_field,
)

logger = logging.getLogger(__name__)
router = Router()


# --- Item List ---

@router.callback_query(F.data == "items_list")
async def show_items_list(callback: CallbackQuery) -> None:
    items = await get_all_items()
    active_count = sum(1 for i in items if i["is_active"])
    text = f"📦 \u041c\u043e\u0438 \u0442\u043e\u0432\u0430\u0440\u044b ({active_count} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445):"
    if not items:
        text += "\n\n\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0442\u043e\u0432\u0430\u0440\u043e\u0432. \u0414\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043f\u0435\u0440\u0432\u044b\u0439!"
    await callback.message.edit_text(text, reply_markup=items_list_keyboard(items))
    await callback.answer()


# --- Item Detail ---

@router.callback_query(F.data.startswith("item_view_"))
async def show_item_detail(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    if not item:
        await callback.answer("\u0422\u043e\u0432\u0430\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
        return

    stats = await get_item_stats(item_id)
    text = (
        f"📦 {item['name']}\n\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {item.get('category_name', 'N/A')}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f: {item['market_price']:,}\u20bd\n"
        f"\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {stats['total']}\n"
        f"\u0410\u043b\u0435\u0440\u0442\u043e\u0432 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e: {stats['alerted']}"
    )
    await callback.message.edit_text(text, reply_markup=item_detail_keyboard(item))
    await callback.answer()


# --- Toggle Item ---

@router.callback_query(F.data.startswith("item_activate_"))
async def activate_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    await update_item_field(item_id, "is_active", 1)

    item = await get_item(item_id)
    if not item:
        await callback.answer("\u0422\u043e\u0432\u0430\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
        return
    stats = await get_item_stats(item_id)
    text = (
        f"📦 {item['name']}\n\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {item.get('category_name', 'N/A')}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f: {item['market_price']:,}\u20bd\n"
        f"\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {stats['total']}\n"
        f"\u0410\u043b\u0435\u0440\u0442\u043e\u0432 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e: {stats['alerted']}"
    )
    await callback.message.edit_text(text, reply_markup=item_detail_keyboard(item))
    await callback.answer("\u25b6\ufe0f \u0422\u043e\u0432\u0430\u0440 \u0432\u043a\u043b\u044e\u0447\u0451\u043d")


@router.callback_query(F.data.startswith("item_deactivate_"))
async def deactivate_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    await update_item_field(item_id, "is_active", 0)

    item = await get_item(item_id)
    if not item:
        await callback.answer("\u0422\u043e\u0432\u0430\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
        return
    stats = await get_item_stats(item_id)
    text = (
        f"📦 {item['name']}\n\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {item.get('category_name', 'N/A')}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f: {item['market_price']:,}\u20bd\n"
        f"\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {stats['total']}\n"
        f"\u0410\u043b\u0435\u0440\u0442\u043e\u0432 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e: {stats['alerted']}"
    )
    await callback.message.edit_text(text, reply_markup=item_detail_keyboard(item))
    await callback.answer("\u23f8 \u0422\u043e\u0432\u0430\u0440 \u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d")


# --- Delete Item ---

@router.callback_query(F.data.startswith("item_delete_") & ~F.data.startswith("item_delete_confirm_"))
async def confirm_delete(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    item = await get_item(item_id)
    if not item:
        await callback.answer("\u0422\u043e\u0432\u0430\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d")
        return
    await callback.message.edit_text(
        f"\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0442\u043e\u0432\u0430\u0440 \u00ab{item['name']}\u00bb?\n\n"
        "\u0412\u0441\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043d\u044b\u0435 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u0442\u0430\u043a\u0436\u0435 \u0431\u0443\u0434\u0443\u0442 \u0443\u0434\u0430\u043b\u0435\u043d\u044b.",
        reply_markup=confirm_delete_keyboard(item_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item_delete_confirm_"))
async def do_delete_item(callback: CallbackQuery) -> None:
    item_id = int(callback.data.split("_")[-1])
    await delete_item(item_id)

    items = await get_all_items()
    active_count = sum(1 for i in items if i["is_active"])
    text = f"📦 \u041c\u043e\u0438 \u0442\u043e\u0432\u0430\u0440\u044b ({active_count} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445):"
    if not items:
        text += "\n\n\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0442\u043e\u0432\u0430\u0440\u043e\u0432. \u0414\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043f\u0435\u0440\u0432\u044b\u0439!"
    await callback.message.edit_text(text, reply_markup=items_list_keyboard(items))
    await callback.answer("🗑 \u0422\u043e\u0432\u0430\u0440 \u0443\u0434\u0430\u043b\u0451\u043d")


# --- Edit Threshold ---

@router.callback_query(F.data.startswith("item_edit_threshold_"))
async def start_edit_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split("_")[-1])
    await state.set_state(EditItemFSM.entering_threshold)
    await state.update_data(edit_item_id=item_id)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u043d\u043e\u0432\u0443\u044e \u043f\u043e\u0440\u043e\u0433\u043e\u0432\u0443\u044e \u0446\u0435\u043d\u0443 (\u0432 \u20bd):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(EditItemFSM.entering_threshold)
async def process_edit_threshold(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0446\u0435\u043d\u0430. \u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]
    await update_item_field(item_id, "threshold_price", price)
    await state.clear()

    item = await get_item(item_id)
    stats = await get_item_stats(item_id)
    text = (
        f"📦 {item['name']}\n\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {item.get('category_name', 'N/A')}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f: {item['market_price']:,}\u20bd\n"
        f"\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {stats['total']}\n"
        f"\u0410\u043b\u0435\u0440\u0442\u043e\u0432 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e: {stats['alerted']}"
    )
    await message.answer(text, reply_markup=item_detail_keyboard(item))


# --- Edit Market Price ---

@router.callback_query(F.data.startswith("item_edit_market_"))
async def start_edit_market(callback: CallbackQuery, state: FSMContext) -> None:
    item_id = int(callback.data.split("_")[-1])
    await state.set_state(EditItemFSM.entering_market_price)
    await state.update_data(edit_item_id=item_id)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u043d\u043e\u0432\u0443\u044e \u0440\u044b\u043d\u043e\u0447\u043d\u0443\u044e \u0446\u0435\u043d\u0443 (\u0432 \u20bd):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(EditItemFSM.entering_market_price)
async def process_edit_market(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0446\u0435\u043d\u0430. \u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return

    data = await state.get_data()
    item_id = data["edit_item_id"]
    await update_item_field(item_id, "market_price", price)
    await state.clear()

    item = await get_item(item_id)
    stats = await get_item_stats(item_id)
    text = (
        f"📦 {item['name']}\n\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {item.get('category_name', 'N/A')}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {item['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f: {item['market_price']:,}\u20bd\n"
        f"\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {stats['total']}\n"
        f"\u0410\u043b\u0435\u0440\u0442\u043e\u0432 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e: {stats['alerted']}"
    )
    await message.answer(text, reply_markup=item_detail_keyboard(item))


# --- Add Item Flow ---

@router.callback_query(F.data == "item_add")
async def start_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    categories = await get_active_categories()
    if not categories:
        await callback.answer("\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0434\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e!")
        return
    await state.set_state(AddItemFSM.choosing_category)
    await callback.message.edit_text(
        "\u0412\u044b\u0431\u0435\u0440\u0438 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e:",
        reply_markup=categories_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_select_"), AddItemFSM.choosing_category)
async def category_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split("_")[-1])
    category = await get_category(category_id)
    await state.update_data(category_id=category_id, category_name=category["name"])
    await state.set_state(AddItemFSM.entering_name)
    await callback.message.edit_text("\u0412\u0432\u0435\u0434\u0438 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0442\u043e\u0432\u0430\u0440\u0430:")
    await callback.answer()


@router.message(AddItemFSM.entering_name)
async def item_name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u0431\u044b\u0442\u044c \u043f\u0443\u0441\u0442\u044b\u043c. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0441\u043d\u043e\u0432\u0430:")
        return
    await state.update_data(item_name=name)
    await state.set_state(AddItemFSM.entering_avito_params)
    await message.answer(
        "\u0412\u0432\u0435\u0434\u0438 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u0444\u0438\u043b\u044c\u0442\u0440\u0430 Avito (JSON):\n"
        '\u041f\u0440\u0438\u043c\u0435\u0440: {"params[110012]": "123456"}\n\n'
        '\u0418\u043b\u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c "skip" \u0447\u0442\u043e\u0431\u044b \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442\u043e\u0432\u044b\u0439 \u043f\u043e\u0438\u0441\u043a.'
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
            await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 JSON. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0441\u043d\u043e\u0432\u0430 \u0438\u043b\u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c \"skip\":")
            return
    await state.set_state(AddItemFSM.entering_threshold)
    await message.answer("\u0412\u0432\u0435\u0434\u0438 \u043f\u043e\u0440\u043e\u0433\u043e\u0432\u0443\u044e \u0446\u0435\u043d\u0443 (\u043c\u0430\u043a\u0441. \u0446\u0435\u043d\u0430 \u043f\u043e\u043a\u0443\u043f\u043a\u0438 \u0432 \u20bd):")


@router.message(AddItemFSM.entering_threshold)
async def threshold_entered(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0446\u0435\u043d\u0430. \u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return
    await state.update_data(threshold_price=price)
    await state.set_state(AddItemFSM.entering_market_price)
    await message.answer("\u0412\u0432\u0435\u0434\u0438 \u0440\u044b\u043d\u043e\u0447\u043d\u0443\u044e \u0446\u0435\u043d\u0443 \u043f\u0440\u043e\u0434\u0430\u0436\u0438 \u0432 \u20bd:")


@router.message(AddItemFSM.entering_market_price)
async def market_price_entered(message: Message, state: FSMContext) -> None:
    try:
        price = int(message.text.strip().replace(" ", ""))
    except (ValueError, AttributeError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0446\u0435\u043d\u0430. \u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return
    await state.update_data(market_price=price)
    await state.set_state(AddItemFSM.confirming)

    data = await state.get_data()
    profit = data["market_price"] - data["threshold_price"]
    text = (
        f"📦 \u041d\u043e\u0432\u044b\u0439 \u0442\u043e\u0432\u0430\u0440:\n\n"
        f"\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435: {data['item_name']}\n"
        f"\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {data['category_name']}\n"
        f"\u041f\u043e\u0440\u043e\u0433: {data['threshold_price']:,}\u20bd\n"
        f"\u0420\u044b\u043d\u043e\u0447\u043d\u0430\u044f \u0446\u0435\u043d\u0430: {data['market_price']:,}\u20bd\n"
        f"\u041f\u0440\u0438\u043c\u0435\u0440\u043d\u044b\u0439 \u043f\u0440\u043e\u0444\u0438\u0442: ~{profit:,}\u20bd"
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
    await callback.message.edit_text("\u2705 \u0422\u043e\u0432\u0430\u0440 \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d!")
    await callback.answer()

    # Show items list
    items = await get_all_items()
    active_count = sum(1 for i in items if i["is_active"])
    text = f"📦 \u041c\u043e\u0438 \u0442\u043e\u0432\u0430\u0440\u044b ({active_count} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445):"
    await callback.message.answer(text, reply_markup=items_list_keyboard(items))


@router.callback_query(F.data == "item_edit_restart", AddItemFSM.confirming)
async def restart_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    categories = await get_active_categories()
    await state.set_state(AddItemFSM.choosing_category)
    await callback.message.edit_text(
        "\u0412\u044b\u0431\u0435\u0440\u0438 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e:",
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
    await callback.answer("\u274c \u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e")


# --- Categories Management ---

@router.callback_query(F.data == "categories_list")
async def show_categories(callback: CallbackQuery) -> None:
    categories = await get_all_categories()
    cats_with_counts = []
    for cat in categories:
        count = await get_items_count_by_category(cat["id"])
        cats_with_counts.append({**cat, "items_count": count})

    text = "📁 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438:"
    if not categories:
        text += "\n\n\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0439."
    await callback.message.edit_text(
        text,
        reply_markup=categories_list_keyboard(cats_with_counts),
    )
    await callback.answer()


@router.callback_query(F.data == "category_add")
async def start_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategoryFSM.entering_name)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438:",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(AddCategoryFSM.entering_name)
async def category_name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043d\u0435 \u043c\u043e\u0436\u0435\u0442 \u0431\u044b\u0442\u044c \u043f\u0443\u0441\u0442\u044b\u043c:")
        return
    await state.update_data(cat_name=name)
    await state.set_state(AddCategoryFSM.entering_avito_id)
    await message.answer("\u0412\u0432\u0435\u0434\u0438 Avito categoryId:")


@router.message(AddCategoryFSM.entering_avito_id)
async def category_id_entered(message: Message, state: FSMContext) -> None:
    try:
        avito_id = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 ID. \u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return

    data = await state.get_data()
    await add_category(data["cat_name"], avito_id)
    await state.clear()
    await message.answer(
        f"\u2705 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u00ab{data['cat_name']}\u00bb \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0430!",
        reply_markup=back_main_keyboard(),
    )
