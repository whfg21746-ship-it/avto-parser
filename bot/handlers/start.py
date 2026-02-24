import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from bot.keyboards.menus import main_menu
from db.models import get_all_items, get_setting, set_setting

logger = logging.getLogger(__name__)
router = Router()


async def _main_menu_text_and_kb():
    active = await get_setting("monitoring_enabled")
    is_active = active == "true"
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

    return text, main_menu(monitoring_active=is_active, has_items=has_items)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text, kb = await _main_menu_text_and_kb()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery) -> None:
    text, kb = await _main_menu_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "monitoring_on")
async def monitoring_on(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "true")
    text, kb = await _main_menu_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("\u25b6\ufe0f Мониторинг включён")


@router.callback_query(F.data == "monitoring_off")
async def monitoring_off(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "false")
    text, kb = await _main_menu_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("\u23f8 Мониторинг приостановлен")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()
