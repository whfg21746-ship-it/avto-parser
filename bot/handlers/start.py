import json
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from bot.keyboards.menus import back_main_keyboard, main_menu
from db.models import get_active_search_queries, get_setting, set_setting
from parser.avito_api import AvitoAPI
from parser.cookie_provider import CookieProvider
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)
router = Router()


async def _is_monitoring_active() -> bool:
    val = await get_setting("monitoring_enabled")
    return val == "true"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    active = await _is_monitoring_active()
    await message.answer(
        "\U0001f50d Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=active),
    )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery) -> None:
    active = await _is_monitoring_active()
    await callback.message.edit_text(
        "\U0001f50d Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=active),
    )
    await callback.answer()


@router.callback_query(F.data == "monitoring_on")
async def monitoring_on(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "true")
    await callback.message.edit_text(
        "\U0001f50d Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=True),
    )
    await callback.answer("\u25b6\ufe0f Мониторинг включён")


@router.callback_query(F.data == "monitoring_off")
async def monitoring_off(callback: CallbackQuery) -> None:
    await set_setting("monitoring_enabled", "false")
    await callback.message.edit_text(
        "\U0001f50d Avito Flipper Bot",
        reply_markup=main_menu(monitoring_active=False),
    )
    await callback.answer("\u23f8 Мониторинг приостановлен")


# --- Test Avito API ---

@router.callback_query(F.data == "test_api")
async def test_api(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("\u23f3 Тестирую Avito (веб-парсинг)...")

    proxy_raw = await get_setting("proxy_list")
    try:
        proxy_list = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxy_list = []

    proxy_mgr = ProxyManager(proxy_list)
    first_proxy = proxy_list[0] if proxy_list else None
    cookie_provider = CookieProvider(proxy_url=first_proxy)
    api = AvitoAPI(proxy_mgr, cookie_provider=cookie_provider)

    search_queries = await get_active_search_queries()
    test_sq = search_queries[0] if search_queries else None

    if not test_sq:
        await callback.message.edit_text(
            "\u274c Нет активных поисковых запросов для теста.\n"
            "Добавь поисковый запрос и попробуй снова.",
            reply_markup=back_main_keyboard(),
        )
        await api.close()
        return

    source = test_sq.get("avito_url") or test_sq["keyword"]
    lines = [f'\U0001f52c Тест для: "{source[:60]}"\n']

    try:
        listings = await api.search_by_keyword(test_sq)
        lines.append(f"\u2705 Поиск: найдено {len(listings)} объявлений")

        if listings:
            ad = listings[0]
            lines.append(f"\nПервое объявление:")
            lines.append(f"  Название: {ad.get('title', '?')}")
            lines.append(f"  Цена: {ad.get('price', '?'):,}\u20bd")
            lines.append(f"  Город: {ad.get('city', '?')}")
            lines.append(f"  URL: {ad.get('url', '?')}")

            # Extract details from search result data (no extra HTTP request)
            raw_item = ad.get("_raw", {})
            details = api.get_item_details(ad["ad_id"], raw_item=raw_item)
            if details:
                lines.append(f"\n\u2705 Детали из поиска:")
                lines.append(f"  Продавец: {details.get('seller_type', '?')}")
                lines.append(f"  Закрытых: {details.get('seller_closed_items', '?')}")
                lines.append(f"  Фото: {len(details.get('images', []))} шт.")
                params = details.get("params_str", "N/A")
                if params and params != "N/A":
                    lines.append(f"  Параметры: {params[:200]}")
                desc = details.get("description", "")
                if desc:
                    lines.append(f"  Описание: {desc[:100]}...")
        else:
            lines.append("\n\u26a0\ufe0f 0 результатов. Проверь URL/ключевое слово или прокси.")
    except Exception as e:
        lines.append(f"\u274c Ошибка поиска: {e}")
    finally:
        await api.close()

    lines.append(f"\nПрокси: {'да (' + str(len(proxy_list)) + ' шт.)' if proxy_list else 'нет'}")
    lines.append("Метод: веб-парсинг (embedded JSON)")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_main_keyboard(),
        disable_web_page_preview=True,
    )
