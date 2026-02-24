import json
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.menus import back_main_keyboard, settings_keyboard
from bot.states.item_states import SettingsFSM
from db.models import (
    get_active_search_queries,
    get_setting,
    set_setting,
)

logger = logging.getLogger(__name__)
router = Router()


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

    search_queries = await get_active_search_queries()

    mon_status = "\u25b6\ufe0f Включён" if monitoring == "true" else "\u23f8 Выключен"
    text = (
        "\u2699\ufe0f Настройки:\n\n"
        f"Мониторинг: {mon_status}\n"
        f"Интервал сканирования: {interval} сек\n"
        f"Прокси: {len(proxies)} шт. активны\n"
        f"Макс. объявлений продавца: {max_seller}\n"
        f"Активных запросов: {len(search_queries)}"
    )
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


# --- Interval ---

@router.callback_query(F.data == "setting_interval")
async def start_edit_interval(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_interval)
    await callback.message.edit_text(
        "Введи новый интервал сканирования (в секундах):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_interval)
async def process_interval(message: Message, state: FSMContext) -> None:
    try:
        interval = int(message.text.strip())
        if interval < 10:
            await message.answer("Минимальный интервал — 10 секунд:")
            return
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    await set_setting("scan_interval_seconds", str(interval))
    await state.clear()
    await message.answer(
        f"\u2705 Интервал установлен: {interval} сек",
        reply_markup=back_main_keyboard(),
    )


# --- Proxy ---

@router.callback_query(F.data == "setting_proxy")
async def start_edit_proxy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_proxy)
    await callback.message.edit_text(
        "Введи список прокси (JSON массив):\n"
        'Пример: ["http://user:pass@host:port"]\n\n'
        'Отправь "clear" чтобы очистить.',
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
            "\u2705 Прокси очищены.",
            reply_markup=back_main_keyboard(),
        )
        return

    try:
        proxies = json.loads(text)
        if not isinstance(proxies, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        await message.answer("Некорректный JSON. Отправь массив строк:")
        return

    await set_setting("proxy_list", json.dumps(proxies))
    await state.clear()
    await message.answer(
        f"\u2705 Прокси обновлены: {len(proxies)} шт.",
        reply_markup=back_main_keyboard(),
    )


# --- Max Seller Items ---

@router.callback_query(F.data == "setting_max_seller")
async def start_edit_max_seller(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.entering_max_seller)
    await callback.message.edit_text(
        "Введи максимальное кол-во объявлений продавца\n"
        "(продавцы с большим кол-вом будут отфильтрованы):",
        reply_markup=back_main_keyboard(),
    )
    await callback.answer()


@router.message(SettingsFSM.entering_max_seller)
async def process_max_seller(message: Message, state: FSMContext) -> None:
    try:
        val = int(message.text.strip())
        if val < 1:
            await message.answer("Введи число больше 0:")
            return
    except (ValueError, AttributeError):
        await message.answer("Введи число:")
        return

    await set_setting("max_seller_items", str(val))
    await state.clear()
    await message.answer(
        f"\u2705 Макс. объявлений продавца: {val}",
        reply_markup=back_main_keyboard(),
    )
