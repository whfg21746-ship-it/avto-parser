import json
import logging

from aiogram import Bot

import config
from ai.analyzer import analyze_ad
from bot.keyboards.menus import ad_alert_keyboard
from db.models import (
    get_active_items,
    get_setting,
    is_ad_seen,
    save_seen_ad,
)
from parser.avito_api import AvitoAPI
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

CONDITION_MAP = {
    "mint": "\u0438\u0434\u0435\u0430\u043b\u044c\u043d\u043e\u0435",
    "good": "\u0445\u043e\u0440\u043e\u0448\u0435\u0435",
    "defects": "\u0441 \u0434\u0435\u0444\u0435\u043a\u0442\u0430\u043c\u0438",
    "parts_only": "\u043d\u0430 \u0437\u0430\u043f\u0447\u0430\u0441\u0442\u0438",
}

RECOMMENDATION_MAP = {
    "BUY": "\u041a\u0423\u041f\u0418\u0422\u042c",
    "CHECK": "\u041f\u0420\u041e\u0412\u0415\u0420\u0418\u0422\u042c \u041b\u0418\u0427\u041d\u041e",
}


def _format_alert(item: dict, ad_data: dict, verdict: dict) -> str:
    """Format the Telegram alert message."""
    condition_ru = CONDITION_MAP.get(verdict.get("condition", ""), verdict.get("condition", ""))
    rec_ru = RECOMMENDATION_MAP.get(verdict.get("recommendation", ""), verdict.get("recommendation", ""))
    score = verdict.get("score", "?")
    comment = verdict.get("comment", "")
    profit = verdict.get("estimated_profit", 0)
    red_flags = verdict.get("red_flags", [])

    params_str = ad_data.get("params_str", "")

    lines = [
        "\ud83d\udd25 \u041d\u043e\u0432\u0430\u044f \u043d\u0430\u0445\u043e\u0434\u043a\u0430!",
        "",
        f"\ud83d\udcf1 {item['name']}",
        f"\ud83d\udcb0 {ad_data.get('price', 0):,}\u20bd (\u0440\u044b\u043d\u043e\u043a: {item['market_price']:,}\u20bd)",
        f"\ud83d\udccd {ad_data.get('city', 'N/A')}",
        f"\ud83d\udd17 {ad_data.get('url', '')}",
    ]

    if params_str and params_str != "N/A":
        lines.append(f"\n\ud83d\udcdd {params_str}")

    lines.extend([
        "",
        f"\ud83e\udd16 \u041e\u0446\u0435\u043d\u043a\u0430 AI ({score}/10):",
        f"\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435: {condition_ru}",
        f"\u26a0\ufe0f {comment}",
        f"\ud83d\udcb5 \u041f\u0440\u043e\u0444\u0438\u0442: ~{profit:,}\u20bd",
    ])

    if red_flags:
        flags_str = ", ".join(red_flags)
        lines.append(f"\ud83d\udea9 \u041a\u0440\u0430\u0441\u043d\u044b\u0435 \u0444\u043b\u0430\u0433\u0438: {flags_str}")

    lines.append(f"\u2705 \u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u044f: {rec_ru}")

    return "\n".join(lines)


async def run_scan_cycle(bot: Bot) -> None:
    """Execute one full scan cycle across all active items."""
    monitoring = await get_setting("monitoring_enabled")
    if monitoring != "true":
        logger.debug("Monitoring is disabled, skipping cycle")
        return

    # Load proxies
    proxy_raw = await get_setting("proxy_list")
    try:
        proxy_list = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxy_list = []

    proxy_manager = ProxyManager(proxy_list)
    api = AvitoAPI(proxy_manager)

    chat_id = await get_setting("telegram_chat_id") or config.TELEGRAM_CHAT_ID

    items = await get_active_items()
    if not items:
        logger.debug("No active items to scan")
        await api.close()
        return

    total_new = 0
    total_alerts = 0
    total_errors = 0

    try:
        for item in items:
            logger.info("Scanning: %s", item["name"])
            try:
                listings = await api.search_items(item)
            except Exception as e:
                logger.error("Error searching %s: %s", item["name"], e)
                total_errors += 1
                continue

            for listing in listings:
                ad_id = listing["ad_id"]

                # Dedup check
                if await is_ad_seen(ad_id):
                    continue

                total_new += 1
                await api.delay()

                # Fetch details
                try:
                    details = await api.get_item_details(ad_id)
                except Exception as e:
                    logger.error("Error fetching details for %s: %s", ad_id, e)
                    total_errors += 1
                    continue

                if not details:
                    # Save as seen even without details to avoid re-fetching
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        seller_type="unknown",
                    )
                    continue

                # Seller filter
                max_seller = item.get("max_seller_items", config.MAX_SELLER_ITEMS)
                if details.get("seller_items_count", 0) > max_seller:
                    logger.debug(
                        "Skipping %s: seller has %d items (max %d)",
                        ad_id, details["seller_items_count"], max_seller,
                    )
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        seller_type=details.get("seller_type", "unknown"),
                    )
                    continue

                # AI analysis
                verdict = await analyze_ad(item, details)
                if not verdict:
                    total_errors += 1
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        seller_type=details.get("seller_type", "unknown"),
                    )
                    continue

                recommendation = verdict.get("recommendation", "SKIP")
                should_alert = recommendation in ("BUY", "CHECK")

                await save_seen_ad(
                    ad_id=ad_id,
                    item_id=item["id"],
                    price=details.get("price", 0),
                    title=details.get("title", ""),
                    url=details.get("url", ""),
                    seller_type=details.get("seller_type", "unknown"),
                    ai_verdict=verdict,
                    profit_estimate=verdict.get("estimated_profit", 0),
                    was_alerted=should_alert,
                )

                if should_alert and chat_id:
                    alert_text = _format_alert(item, details, verdict)
                    ad_url = details.get("url", "")
                    reply_markup = ad_alert_keyboard(ad_url) if ad_url else None
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=alert_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True,
                        )
                        total_alerts += 1
                    except Exception as e:
                        logger.error("Failed to send alert: %s", e)
                        total_errors += 1

            await api.delay()

    except Exception as e:
        logger.error("Scan cycle error: %s", e)
    finally:
        await api.close()

    logger.info(
        "Scan cycle complete: %d new, %d alerts, %d errors",
        total_new, total_alerts, total_errors,
    )

    # Check if all proxies are dead
    if proxy_list and not proxy_manager.has_proxies and chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="\u26a0\ufe0f \u0412\u0441\u0435 \u043f\u0440\u043e\u043a\u0441\u0438 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b. \u041c\u043e\u043d\u0438\u0442\u043e\u0440\u0438\u043d\u0433 \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d.",
            )
            from db.models import set_setting
            await set_setting("monitoring_enabled", "false")
        except Exception as e:
            logger.error("Failed to send proxy alert: %s", e)
