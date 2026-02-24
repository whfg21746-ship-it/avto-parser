import json
import logging

from aiogram import Bot

from ai.analyzer import analyze_ad
from bot.keyboards.menus import ad_alert_keyboard
from db.models import (
    get_active_items,
    get_setting,
    is_ad_seen,
    save_seen_ad,
)
import config
from parser.avito_api import AvitoAPI
from parser.cookie_provider import CookieProvider
from parser.filters import should_instant_reject, should_reject_seller
from parser.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

RECOMMENDATION_MAP = {
    "BUY": "КУПИТЬ",
    "CHECK": "ПРОВЕРИТЬ ЛИЧНО",
}


def _format_alert(item: dict, ad_data: dict, verdict: dict) -> str:
    """Format the Telegram alert message."""
    rec = verdict.get("recommendation", "CHECK")
    rec_ru = RECOMMENDATION_MAP.get(rec, rec)
    score = verdict.get("score", "?")
    comment = verdict.get("comment", "")
    profit = verdict.get("estimated_profit", 0)
    sell_price = verdict.get("estimated_sell_price", 0)
    defects = verdict.get("defects", [])
    red_flags = verdict.get("red_flags", [])

    ad_price = ad_data.get("price", 0)
    city = ad_data.get("city", "N/A")
    url = ad_data.get("url", "")

    if red_flags:
        header = f"\U0001f6a9 {item['name']} за {ad_price:,}\u20bd"
    else:
        header = "\U0001f525 Новая находка!"

    lines = [header, ""]

    if not red_flags:
        lines.append(f"\U0001f4f1 {item['name']}")

    lines.append(f"\U0001f4b0 Цена: {ad_price:,}\u20bd")
    lines.append(f"\U0001f4cd {city}")

    lines.extend([
        "",
        f"\U0001f916 Оценка: {score}/10 \u2014 {rec_ru}",
    ])

    if sell_price:
        lines.append(f"Перепродажа: ~{sell_price:,}\u20bd | Профит: ~{profit:,}\u20bd")

    lines.append(comment)

    if defects:
        defects_str = ", ".join(defects)
        lines.extend(["", f"\u26a0\ufe0f Замечено: {defects_str}"])

    if red_flags:
        flags_str = ", ".join(red_flags)
        lines.extend(["", f"\U0001f6a9 Красные флаги: {flags_str}"])

    return "\n".join(lines)


async def run_scan_cycle(bot: Bot) -> None:
    """Execute one full scan cycle: iterate over each active item's URL."""
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
    first_proxy = proxy_list[0] if proxy_list else None
    cookie_provider = CookieProvider(proxy_url=first_proxy)
    api = AvitoAPI(proxy_manager, cookie_provider=cookie_provider)

    chat_id = await get_setting("telegram_chat_id") or config.TELEGRAM_CHAT_ID
    max_seller_str = await get_setting("max_seller_items") or str(config.MAX_SELLER_ITEMS)
    max_seller_items = int(max_seller_str)

    items = await get_active_items()
    if not items:
        logger.debug("No active items to scan")
        await api.close()
        return

    total_new = 0
    total_alerts = 0
    total_errors = 0
    total_filtered = 0

    try:
        for item in items:
            logger.info("Scanning item: %s (url=%s)", item["name"], item["avito_url"][:80])

            # Build a search_query-like dict for the API
            search_query = {"avito_url": item["avito_url"], "keyword": item["name"]}

            try:
                listings = await api.search_by_keyword(search_query)
            except Exception as e:
                logger.error("Error scanning item '%s': %s", item["name"], e)
                total_errors += 1
                continue

            logger.info("Item '%s': %d listings found", item["name"], len(listings))

            for listing in listings:
                ad_id = listing["ad_id"]

                # (a) Dedup check
                if await is_ad_seen(ad_id):
                    continue

                total_new += 1

                # (b) Price threshold check
                if listing["price"] > item["threshold_price"]:
                    continue

                # (c) Instant-reject patterns in TITLE
                rejected, reason = should_instant_reject(listing["title"], "")
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        skip_reason=reason,
                    )
                    continue

                # (d) Extract full details from search result data
                raw_item = listing.get("_raw", {})
                details = api.get_item_details(ad_id, raw_item=raw_item)

                if not details:
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        skip_reason="no details",
                    )
                    continue

                # (e) Seller filter: type + closed items count
                seller_rejected, seller_reason = should_reject_seller(
                    seller_type=details.get("seller_type", "private"),
                    seller_closed_items=details.get("seller_closed_items", 0),
                    max_seller_items=max_seller_items,
                )
                if seller_rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, seller_reason)
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason=seller_reason,
                    )
                    continue

                # (f) Instant-reject patterns in DESCRIPTION
                description = details.get("description", "")
                rejected, reason = should_instant_reject(details.get("title", ""), description)
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason=reason,
                    )
                    continue

                # (g) AI analysis — only after all pre-filters passed
                verdict = await analyze_ad(item, details)
                if not verdict:
                    total_errors += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason="AI error",
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
                    ai_verdict=verdict,
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
        "Scan cycle complete: %d items, %d new, %d filtered, %d alerts, %d errors",
        len(items), total_new, total_filtered, total_alerts, total_errors,
    )

    # Check if all proxies are dead
    if proxy_list and not proxy_manager.has_proxies and chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="\u26a0\ufe0f Все прокси недоступны. Мониторинг приостановлен.",
            )
            from db.models import set_setting
            await set_setting("monitoring_enabled", "false")
        except Exception as e:
            logger.error("Failed to send proxy alert: %s", e)
