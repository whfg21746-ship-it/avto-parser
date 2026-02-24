import json
import logging

from aiogram import Bot

from ai.analyzer import analyze_ad
from bot.keyboards.menus import ad_alert_keyboard
from db.models import (
    get_active_search_queries,
    get_items_by_search_query,
    get_setting,
    is_ad_seen,
    save_seen_ad,
)
import config
from parser.avito_api import AvitoAPI
from parser.cookie_provider import CookieProvider
from parser.filters import should_instant_reject, should_reject_seller
from parser.model_matcher import match_listing_to_item
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
    sell_price = verdict.get("estimated_sell_price", item["market_price"])
    defects = verdict.get("defects", [])
    red_flags = verdict.get("red_flags", [])

    ad_price = ad_data.get("price", 0)
    city = ad_data.get("city", "N/A")
    url = ad_data.get("url", "")

    # Header depends on whether there are red flags
    if red_flags:
        header = f"\U0001f6a9 {item['name']} за {ad_price:,}₽"
    else:
        header = "\U0001f525 Новая находка!"

    lines = [header, ""]

    if not red_flags:
        lines.append(f"\U0001f4f1 {item['name']}")

    lines.extend([
        f"\U0001f4b0 {ad_price:,}₽ → продажа ~{sell_price:,}₽",
        f"\U0001f4cd {city}",
        f"\U0001f4b5 Профит: ~{profit:,}₽",
    ])

    lines.extend([
        "",
        f"\U0001f916 Оценка: {score}/10 — {rec_ru}",
        comment,
    ])

    if defects:
        defects_str = ", ".join(defects)
        lines.extend(["", f"⚠️ Замечено: {defects_str}"])

    if red_flags:
        flags_str = ", ".join(red_flags)
        lines.extend(["", f"\U0001f6a9 Красные флаги: {flags_str}"])

    lines.extend(["", f"\U0001f517 {url}"])

    return "\n".join(lines)


async def run_scan_cycle(bot: Bot) -> None:
    """Execute one full scan cycle using broad keyword queries."""
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
    # Use the first proxy for Playwright cookie acquisition
    first_proxy = proxy_list[0] if proxy_list else None
    cookie_provider = CookieProvider(proxy_url=first_proxy)
    api = AvitoAPI(proxy_manager, cookie_provider=cookie_provider)

    chat_id = await get_setting("telegram_chat_id") or config.TELEGRAM_CHAT_ID

    search_queries = await get_active_search_queries()
    if not search_queries:
        logger.debug("No active search queries to scan")
        await api.close()
        return

    total_new = 0
    total_alerts = 0
    total_errors = 0
    total_matched = 0
    total_filtered = 0

    try:
        for sq in search_queries:
            logger.info("Scanning keyword: %s", sq["keyword"])

            # Get all active items linked to this search query
            items = await get_items_by_search_query(sq["id"])
            if not items:
                logger.debug("No active items for keyword '%s', skipping", sq["keyword"])
                continue

            # Step 1: One broad API query per keyword
            try:
                listings = await api.search_by_keyword(sq)
            except Exception as e:
                logger.error("Error searching keyword '%s': %s", sq["keyword"], e)
                total_errors += 1
                continue

            logger.info("Keyword '%s': %d listings found", sq["keyword"], len(listings))

            for listing in listings:
                ad_id = listing["ad_id"]

                # (a) Dedup check
                if await is_ad_seen(ad_id):
                    continue

                total_new += 1

                # (b) Instant-reject patterns in TITLE
                rejected, reason = should_instant_reject(listing["title"], "")
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    total_filtered += 1
                    continue

                # (c) Match listing to a specific item (model + storage)
                raw_item = listing.get("_raw", {})
                listing_params = api.extract_listing_params(raw_item)
                matched_item = match_listing_to_item(
                    listing["title"],
                    listing_params,
                    items,
                )

                if matched_item is None:
                    continue

                total_matched += 1

                # (d) Check price threshold
                if listing["price"] > matched_item["threshold_price"]:
                    continue

                # (e) Extract full details from search result data
                details = api.get_item_details(ad_id, raw_item=raw_item)

                if not details:
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=matched_item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        seller_type="unknown",
                    )
                    continue

                # (f) Seller filter: type + closed items count
                max_seller = matched_item.get("max_seller_items", config.MAX_SELLER_ITEMS)
                seller_rejected, seller_reason = should_reject_seller(
                    seller_type=details.get("seller_type", "private"),
                    seller_closed_items=details.get("seller_closed_items", 0),
                    max_seller_items=max_seller,
                )
                if seller_rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, seller_reason)
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=matched_item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        seller_type=details.get("seller_type", "unknown"),
                    )
                    continue

                # (g) Instant-reject patterns in DESCRIPTION
                description = details.get("description", "")
                rejected, reason = should_instant_reject(details.get("title", ""), description)
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=matched_item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        seller_type=details.get("seller_type", "unknown"),
                    )
                    continue

                # (h) AI analysis — only after all pre-filters passed
                verdict = await analyze_ad(matched_item, details)
                if not verdict:
                    total_errors += 1
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=matched_item["id"],
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
                    item_id=matched_item["id"],
                    price=details.get("price", 0),
                    title=details.get("title", ""),
                    url=details.get("url", ""),
                    seller_type=details.get("seller_type", "unknown"),
                    ai_verdict=verdict,
                    profit_estimate=verdict.get("estimated_profit", 0),
                    was_alerted=should_alert,
                )

                if should_alert and chat_id:
                    alert_text = _format_alert(matched_item, details, verdict)
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
        "Scan cycle complete: %d queries, %d new, %d matched, %d filtered, %d alerts, %d errors",
        len(search_queries), total_new, total_matched, total_filtered, total_alerts, total_errors,
    )

    # Check if all proxies are dead
    if proxy_list and not proxy_manager.has_proxies and chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ Все прокси недоступны. Мониторинг приостановлен.",
            )
            from db.models import set_setting
            await set_setting("monitoring_enabled", "false")
        except Exception as e:
            logger.error("Failed to send proxy alert: %s", e)
