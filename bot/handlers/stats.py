import csv
import io
import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    BufferedInputFile,
)

from bot.keyboards.menus import back_main_keyboard
from db.models import get_user_stats, delete_old_seen_ads, get_alerted_ads

logger = logging.getLogger(__name__)
router = Router()


def _stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001f4e4 Export CSV", callback_data="export_csv"),
            InlineKeyboardButton(text="\U0001f4e4 Export JSON", callback_data="export_json"),
        ],
        [
            InlineKeyboardButton(
                text="\U0001f5d1 Очистить старые (>30 дней)",
                callback_data="cleanup_seen_ads",
            ),
        ],
        [InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="back_main")],
    ])


async def _stats_text() -> str:
    stats = await get_user_stats()
    text = (
        "\U0001f4ca Статистика\n\n"
        f"\U0001f50d Просмотрено объявлений: {stats['total_seen']}\n"
        f"\U0001f514 Отправлено алертов: {stats['total_alerted']}\n"
        f"\U0001f4e6 Активных товаров: {stats['active_items']}\n"
        f"\U0001f4c1 Активных категорий: {stats['active_categories']}\n"
    )
    if stats["total_seen"] > 0:
        rate = stats["total_alerted"] / stats["total_seen"] * 100
        text += f"\n\U0001f3af Конверсия: {rate:.1f}%"
    return text


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    text = await _stats_text()
    await message.answer(text, reply_markup=_stats_keyboard())


@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery) -> None:
    text = await _stats_text()
    await callback.message.edit_text(text, reply_markup=_stats_keyboard())
    await callback.answer()


@router.callback_query(F.data == "cleanup_seen_ads")
async def cleanup_seen_ads(callback: CallbackQuery) -> None:
    deleted = await delete_old_seen_ads(days=30)
    await callback.answer(f"Удалено {deleted} старых записей")
    # Refresh stats
    text = await _stats_text()
    await callback.message.edit_text(text, reply_markup=_stats_keyboard())


@router.callback_query(F.data == "export_csv")
async def export_csv(callback: CallbackQuery) -> None:
    ads = await get_alerted_ads()
    if not ads:
        await callback.answer("Нет данных для экспорта")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ad_id", "title", "price", "url", "recommendation", "score",
                      "estimated_profit", "created_at"])
    for ad in ads:
        verdict = {}
        if ad.get("ai_verdict"):
            try:
                verdict = json.loads(ad["ai_verdict"])
            except (json.JSONDecodeError, TypeError):
                pass
        writer.writerow([
            ad.get("ad_id", ""),
            ad.get("title", ""),
            ad.get("price", 0),
            ad.get("url", ""),
            verdict.get("recommendation", ""),
            verdict.get("score", ""),
            verdict.get("estimated_profit", ""),
            ad.get("created_at", ""),
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    doc = BufferedInputFile(csv_bytes, filename="avito_alerts.csv")
    await callback.message.answer_document(doc)
    await callback.answer()


@router.callback_query(F.data == "export_json")
async def export_json(callback: CallbackQuery) -> None:
    ads = await get_alerted_ads()
    if not ads:
        await callback.answer("Нет данных для экспорта")
        return

    export_data = []
    for ad in ads:
        verdict = {}
        if ad.get("ai_verdict"):
            try:
                verdict = json.loads(ad["ai_verdict"])
            except (json.JSONDecodeError, TypeError):
                pass
        export_data.append({
            "ad_id": ad.get("ad_id", ""),
            "title": ad.get("title", ""),
            "price": ad.get("price", 0),
            "url": ad.get("url", ""),
            "verdict": verdict,
            "created_at": ad.get("created_at", ""),
        })

    json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
    doc = BufferedInputFile(json_bytes, filename="avito_alerts.json")
    await callback.message.answer_document(doc)
    await callback.answer()
