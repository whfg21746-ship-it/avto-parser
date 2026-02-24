import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from bot.keyboards.menus import main_menu
from db.models import get_setting, set_setting

logger = logging.getLogger(__name__)
router = Router()


async def _is_monitoring_active() -> bool:
    val = await get_setting("monitoring_enabled")
    return val == "true"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    active = await _is_monitoring_active()
    await message.answer(
        "🔍 Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=active),
    )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery) -> None:
    active = await _is_monitoring_active()
    await callback.message.edit_text(
        "🔍 Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=active),
    )
    await callback.answer()


@router.callback_query(F.data == "monitoring_on")
async def monitoring_on(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "true")
    await callback.message.edit_text(
        "🔍 Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=True),
    )
    await callback.answer("\u25b6\ufe0f \u041c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433 \u0432\u043a\u043b\u044e\u0447\u0451\u043d")


@router.callback_query(F.data == "monitoring_off")
async def monitoring_off(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "false")
    await callback.message.edit_text(
        "🔍 Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=False),
    )
    await callback.answer("\u23f8 \u041c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433 \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d")
