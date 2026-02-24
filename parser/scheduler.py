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
from parser.model_matcher import match_listing_to_item
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
        "\U0001f525 \u041d\u043e\u0432\u0430\u044f \u043d\u0430\u0445\u043e\u0434\u043a\u0430!",
        "",
        f"\U0001f4f1 {item['name']}",
        f"\U0001f4b0 {ad_data.get('price', 0):,}\u20bd (\u0440\u044b\u043d\u043e\u043a: {item['market_price']:,}\u20bd)",
        f"\U0001f4cd {ad_data.get('city', 'N/A')}",
        f"\U0001f517 {ad_data.get('url', '')}",
    ]

    if params_str and params_str != "N/A":
        lines.append(f"\n\U0001f4dd {params_str}")

    lines.extend([
        "",
        f"\U0001f916 \u041e\u0446\u0435\u043d\u043a\u0430 AI ({score}/10):",
        f"\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435: {condition_ru}",
        f"\u26a0\ufe0f {comment}",
        f"\U0001f4b5 \u041f\u0440\u043e\u0444\u0438\u0442: ~{profit:,}\u20bd",
    ])

    if red_flags:
        flags_str = ", ".join(red_flags)
        lines.append(f"\U0001f6a9 \u041a\u0440\u0430\u0441\u043d\u044b\u0435 \u0444\u043b\u0430\u0433\u0438: {flags_str}")

    lines.append(f"\u2705 \u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0438\u044f: {rec_ru}")

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

                # Dedup check
                if await is_ad_seen(ad_id):
                    continue

                total_new += 1

                # Step 2: Match listing to a specific item (model + storage)
                matched_item = match_listing_to_item(
                    listing["title"],
                    listing.get("params"),
                    items,
                )

                if matched_item is None:
                    continue

                total_matched += 1

                # Step 3: Check price threshold
                if listing["price"] > matched_item["threshold_price"]:
                    continue

                await api.delay()

                # Step 4: Fetch full details only for matched + affordable listings
                try:
                    details = await api.get_item_details(ad_id, url=listing.get("url", ""))
                except Exception as e:
                    logger.error("Error fetching details for %s: %s", ad_id, e)
                    total_errors += 1
                    continue

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

                # Seller filter
                max_seller = matched_item.get("max_seller_items", config.MAX_SELLER_ITEMS)
                if details.get("seller_items_count", 0) > max_seller:
                    logger.debug(
                        "Skipping %s: seller has %d items (max %d)",
                        ad_id, details["seller_items_count"], max_seller,
                    )
                    await save_seen_ad(
                        ad_id=ad_id,
                        item_id=matched_item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        seller_type=details.get("seller_type", "unknown"),
                    )
                    continue

                # Step 5: AI analysis
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
        "Scan cycle complete: %d queries, %d new listings, %d matched, %d alerts, %d errors",
        len(search_queries), total_new, total_matched, total_alerts, total_errors,
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
