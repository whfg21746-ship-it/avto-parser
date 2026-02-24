import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from bot.keyboards.menus import back_main_keyboard, settings_keyboard
from bot.states.item_states import SettingsFSM
from db.models import (
    get_all_items,
    get_items_missing_params,
    get_setting,
    set_setting,
    update_category_avito_id,
    update_item_params,
)
from parser.param_discovery import ParamDiscovery
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)
router = Router()


async def _get_proxy_manager() -> ProxyManager:
    """Build a ProxyManager from settings or config."""
    proxy_raw = await get_setting("proxy_list")
    try:
        proxy_list = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxy_list = []
    if not proxy_list:
        proxy_list = config.PROXY_LIST
    return ProxyManager(proxy_list)


async def _run_discovery(
    items: list[dict],
    message: Message,
    force: bool = False,
) -> None:
    """Run param discovery for a list of items and report progress via Telegram."""
    if not items:
        await message.answer(
            "\u2705 Все товары уже имеют параметры." if not force
            else "\u274c Нет товаров для обработки.",
            reply_markup=back_main_keyboard(),
        )
        return

    proxy_manager = await _get_proxy_manager()
    discovery = ParamDiscovery(proxy_manager)

    # Group items by search_query to avoid duplicate lookups
    query_map: dict[str, list[dict]] = {}
    for item in items:
        query = item.get("search_query") or item["name"]
        if query not in query_map:
            query_map[query] = []
        query_map[query].append(item)

    total = len(query_map)
    discovered = 0
    failed = 0
    status_msg = await message.answer(
        f"🔍 Запускаю поиск параметров для {total} моделей...\n"
        f"Это может занять ~{total * 5} сек."
    )

    try:
        for i, (query, group_items) in enumerate(query_map.items()):
            result = await discovery.discover_and_verify(query)

            if result.get("category_id") and not result.get("error"):
                params_json = json.dumps(result.get("params", {}))
                category_id = result["category_id"]

                for item in group_items:
                    await update_item_params(item["id"], params_json)
                    if item.get("category_id"):
                        await update_category_avito_id(item["category_id"], category_id)

                discovered += 1
            else:
                failed += 1

            # Update progress every 5 items
            if (i + 1) % 5 == 0 or (i + 1) == total:
                try:
                    await status_msg.edit_text(
                        f"🔍 Поиск параметров: {i + 1}/{total}\n"
                        f"\u2705 Найдено: {discovered}\n"
                        f"\u274c Не найдено: {failed}"
                    )
                except Exception:
                    pass  # Edit may fail if content unchanged

            if i < total - 1:
                import asyncio
                await asyncio.sleep(3)

    finally:
        await discovery.close()

    await status_msg.edit_text(
        f"🔍 Поиск параметров завершён!\n\n"
        f"Всего моделей: {total}\n"
        f"\u2705 Найдено: {discovered}\n"
        f"\u274c Не найдено: {failed}\n\n"
        f"{'Бот теперь будет находить реальные объявления!' if discovered > 0 else 'Попробуйте позже или добавьте параметры вручную.'}",
        reply_markup=back_main_keyboard(),
    )


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery) -> None:
    monitoring = await get_setting("monitoring_enabled")
    interval = await get_setting("scan_interval_seconds")
    proxy_raw = await get_setting("proxy_list")
    max_seller = await get_setting("max_seller_items") or "10"

    try:
        proxies = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxies = []

    # Count items missing params
    missing = await get_items_missing_params()

    mon_status = "\u25b6\ufe0f \u0412\u043a\u043b\u044e\u0447\u0451\u043d" if monitoring == "true" else "\u23f8 \u0412\u044b\u043a\u043b\u044e\u0447\u0435\u043d"
    text = (
        "\u2699\ufe0f \u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438:\n\n"
        f"\u041c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433: {mon_status}\n"
        f"\u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f: {interval} \u0441\u0435\u043a\n"
        f"\u041f\u0440\u043e\u043a\u0441\u0438: {len(proxies)} \u0448\u0442. \u0430\u043a\u0442\u0438\u0432\u043d\u044b\n"
        f"\u041c\u0430\u043a\u0441. \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430: {max_seller}"
    )
    if missing:
        text += f"\n\n\u26a0\ufe0f {len(missing)} товаров без параметров Avito"
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


# --- Interval ---

@router.callback_query(F.data == "setting_interval")
async def start_edit_interval(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_interval)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u043d\u043e\u0432\u044b\u0439 \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f (\u0432 \u0441\u0435\u043a\u0443\u043d\u0434\u0430\u0445):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_interval)
async def process_interval(message: Message, state: FSMContext) -> None:
    try:
        interval = int(message.text.strip())
        if interval < 10:
            await message.answer("\u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u2014 10 \u0441\u0435\u043a\u0443\u043d\u0434:")
            return
    except (ValueError, AttributeError):
        await message.answer("\u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return

    await set_setting("scan_interval_seconds", str(interval))
    await state.clear()
    await message.answer(
        f"\u2705 \u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d: {interval} \u0441\u0435\u043a",
        reply_markup=back_main_keyboard(),
    )


# --- Proxy ---

@router.callback_query(F.data == "setting_proxy")
async def start_edit_proxy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_proxy)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u0441\u043f\u0438\u0441\u043e\u043a \u043f\u0440\u043e\u043a\u0441\u0438 (JSON \u043c\u0430\u0441\u0441\u0438\u0432):\n"
        '\u041f\u0440\u0438\u043c\u0435\u0440: ["http://user:pass@host:port"]\n\n'
        '\u041e\u0442\u043f\u0440\u0430\u0432\u044c "clear" \u0447\u0442\u043e\u0431\u044b \u043e\u0447\u0438\u0441\u0442\u0438\u0442\u044c.',
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_proxy)
async def process_proxy(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.lower() == "clear":
        await set_setting("proxy_list", "[]")
        await state.clear()
        await message.answer(
            "\u2705 \u041f\u0440\u043e\u043a\u0441\u0438 \u043e\u0447\u0438\u0449\u0435\u043d\u044b.",
            reply_markup=back_main_keyboard(),
        )
        return

    try:
        proxies = json.loads(text)
        if not isinstance(proxies, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        await message.answer("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 JSON. \u041e\u0442\u043f\u0440\u0430\u0432\u044c \u043c\u0430\u0441\u0441\u0438\u0432 \u0441\u0442\u0440\u043e\u043a:")
        return

    await set_setting("proxy_list", json.dumps(proxies))
    await state.clear()
    await message.answer(
        f"\u2705 \u041f\u0440\u043e\u043a\u0441\u0438 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u044b: {len(proxies)} \u0448\u0442.",
        reply_markup=back_main_keyboard(),
    )


# --- Max Seller Items ---

@router.callback_query(F.data == "setting_max_seller")
async def start_edit_max_seller(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_max_seller)
    await callback.message.edit_text(
        "\u0412\u0432\u0435\u0434\u0438 \u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u043e\u0435 \u043a\u043e\u043b-\u0432\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430\n"
        "(\u043f\u0440\u043e\u0434\u0430\u0432\u0446\u044b \u0441 \u0431\u043e\u043b\u044c\u0448\u0438\u043c \u043a\u043e\u043b-\u0432\u043e\u043c \u0431\u0443\u0434\u0443\u0442 \u043e\u0442\u0444\u0438\u043b\u044c\u0442\u0440\u043e\u0432\u0430\u043d\u044b):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_max_seller)
async def process_max_seller(message: Message, state: FSMContext) -> None:
    try:
        val = int(message.text.strip())
        if val < 1:
            await message.answer("\u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e \u0431\u043e\u043b\u044c\u0448\u0435 0:")
            return
    except (ValueError, AttributeError):
        await message.answer("\u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e:")
        return

    await set_setting("max_seller_items", str(val))
    await state.clear()
    await message.answer(
        f"\u2705 \u041c\u0430\u043a\u0441. \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430: {val}",
        reply_markup=back_main_keyboard(),
    )


# --- Discover Params (items missing params only) ---

@router.callback_query(F.data == "discover_params")
async def discover_params_cb(callback: CallbackQuery) -> None:
    """Discover params for items with empty/placeholder avito_params."""
    await callback.answer()
    items = await get_items_missing_params()
    await _run_discovery(items, callback.message, force=False)


@router.message(Command("discover_params"))
async def discover_params_cmd(message: Message) -> None:
    """Command handler: /discover_params"""
    items = await get_items_missing_params()
    await _run_discovery(items, message, force=False)


# --- Refresh Params (ALL items) ---

@router.callback_query(F.data == "refresh_params")
async def refresh_params_cb(callback: CallbackQuery) -> None:
    """Re-discover params for ALL items, even those with existing params."""
    await callback.answer()
    items = await get_all_items()
    await _run_discovery(items, callback.message, force=True)


@router.message(Command("refresh_params"))
async def refresh_params_cmd(message: Message) -> None:
    """Command handler: /refresh_params"""
    items = await get_all_items()
    await _run_discovery(items, message, force=True)
