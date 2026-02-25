"""Scan cycle orchestration with watchdog and graceful degradation."""

import asyncio
import json
import logging
import random
import time

from aiogram import Bot

from ai.analyzer import analyze_ad
from bot.keyboards.menus import ad_alert_keyboard
from db.database import current_user_id, ensure_db_initialized, get_all_user_ids
from db.models import (
    get_active_items,
    get_setting,
    has_seen_ads,
    is_ad_seen,
    save_seen_ad,
)
import config
from parser.avito_api import AvitoAPI
from parser.cookie_provider import get_cookie_provider
from parser.filters import should_instant_reject, should_reject_model_pattern, should_reject_seller
from parser.proxy_manager import ProxyManager
from parser.resilience import NoHealthyProxyError, retry_async

logger = logging.getLogger(__name__)

RECOMMENDATION_MAP = {
    "BUY": "КУПИТЬ",
    "CHECK": "ПРОВЕРИТЬ ЛИЧНО",
}

# Per-user last scan timestamps for dynamic interval support
_user_last_scan: dict[int, float] = {}

# Watchdog state
_consecutive_failures: int = 0
MAX_CONSECUTIVE_FAILURES = 5
FAILURE_PAUSE_SECONDS = 300  # 5 minutes


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


@retry_async(max_retries=3, base_delay=1, exceptions=(Exception,))
async def _send_alert(bot: Bot, chat_id: str, text: str,
                      images: list[str] | None = None,
                      reply_markup=None) -> None:
    """Send Telegram alert with retry and photo fallback."""
    if images:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=images[0],
                caption=text[:1024],
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass  # fall through to text message

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


async def _scan_user_with_context(bot: Bot, uid: int) -> None:
    """Run scan for a single user with its own context."""
    token = current_user_id.set(uid)
    try:
        await ensure_db_initialized()
        await _run_user_scan(bot, uid)
    except Exception as e:
        logger.error("Scan error for user %d: %s", uid, e, exc_info=True)
    finally:
        current_user_id.reset(token)


async def run_scan_cycle(bot: Bot) -> None:
    """Execute scan cycle for all registered users in parallel.

    Includes watchdog logic: after MAX_CONSECUTIVE_FAILURES failures
    in a row, pauses for FAILURE_PAUSE_SECONDS.
    """
    global _consecutive_failures

    user_ids = get_all_user_ids()
    if not user_ids:
        return

    logger.info("Starting scan for %d user(s): %s", len(user_ids), user_ids)
    try:
        await asyncio.gather(
            *(_scan_user_with_context(bot, uid) for uid in user_ids)
        )
        _consecutive_failures = 0
    except Exception as e:
        _consecutive_failures += 1
        logger.error(
            "Scan cycle failed (%d consecutive): %s",
            _consecutive_failures, e,
        )
        if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.critical(
                "Too many consecutive failures (%d), pausing for %ds",
                _consecutive_failures, FAILURE_PAUSE_SECONDS,
            )
            await asyncio.sleep(FAILURE_PAUSE_SECONDS)
            _consecutive_failures = 0


async def _run_user_scan(bot: Bot, user_id: int) -> None:
    """Execute scan for a single user (context already set)."""
    monitoring = await get_setting("monitoring_enabled")
    if monitoring != "true":
        logger.debug("User %d: monitoring disabled, skipping", user_id)
        return

    # Check per-user scan interval
    user_interval_raw = await get_setting("scan_interval_seconds")
    user_interval = int(user_interval_raw) if user_interval_raw else config.SCAN_INTERVAL
    last_scan = _user_last_scan.get(user_id, 0)
    elapsed = time.time() - last_scan
    if last_scan > 0 and elapsed < user_interval:
        logger.debug(
            "User %d: skipping scan (%.0fs elapsed, interval=%ds)",
            user_id, elapsed, user_interval,
        )
        return
    _user_last_scan[user_id] = time.time()

    # Load proxies
    proxy_raw = await get_setting("proxy_list")
    try:
        proxy_list = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxy_list = []

    proxy_manager = ProxyManager(proxy_list)
    first_proxy = proxy_list[0] if proxy_list else None
    cookie_provider = get_cookie_provider(proxy_url=first_proxy)
    api = AvitoAPI(proxy_manager, cookie_provider=cookie_provider)

    chat_id = await get_setting("telegram_chat_id") or str(user_id)
    max_seller_str = await get_setting("max_seller_items") or str(config.MAX_SELLER_ITEMS)
    max_seller_items = int(max_seller_str)

    items = await get_active_items()
    if not items:
        logger.debug("User %d: no active items to scan", user_id)
        await api.close()
        return

    logger.info(
        "User %d: scanning %d active item(s) [proxies: %s]",
        user_id, len(items), proxy_manager.status(),
    )

    total_new = 0
    total_alerts = 0
    total_errors = 0
    total_filtered = 0

    try:
        for item in items:
            logger.info(
                "User %d: scanning item: %s (url=%s)",
                user_id, item["name"], item["avito_url"][:80],
            )

            search_query = {"avito_url": item["avito_url"], "keyword": item["name"]}

            try:
                listings = await api.search_by_keyword(
                    search_query, max_pages=config.SEARCH_PAGES,
                )
            except NoHealthyProxyError:
                logger.error("User %d: all proxies dead, stopping scan", user_id)
                break
            except Exception as e:
                logger.error("Error scanning item '%s': %s", item["name"], e)
                total_errors += 1
                continue

            logger.info(
                "Item '%s': %d listings found (threshold=%d)",
                item["name"], len(listings), item["threshold_price"],
            )

            # Baseline scan
            if not await has_seen_ads(item["id"]):
                logger.info(
                    "First scan for item '%s': saving %d existing ads as baseline",
                    item["name"], len(listings),
                )
                for listing in listings:
                    await save_seen_ad(
                        ad_id=listing["ad_id"],
                        item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        skip_reason="baseline",
                    )
                await api.delay()
                continue

            # Per-item pipeline counters
            item_dedup = 0
            item_new = 0
            item_price_skip = 0
            item_title_skip = 0
            item_seller_skip = 0
            item_desc_skip = 0
            item_ai_ok = 0
            item_ai_err = 0

            for listing in listings:
                ad_id = listing["ad_id"]

                # (a) Dedup check
                if await is_ad_seen(ad_id):
                    item_dedup += 1
                    continue

                item_new += 1
                total_new += 1

                # (b) Price threshold check
                if listing["price"] > item["threshold_price"]:
                    item_price_skip += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        skip_reason=f"price {listing['price']} > {item['threshold_price']}",
                    )
                    continue

                # (c) Instant-reject patterns in TITLE
                rejected, reason = should_instant_reject(listing["title"], "")
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    item_title_skip += 1
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=listing.get("price", 0),
                        title=listing.get("title", ""),
                        url=listing.get("url", ""),
                        skip_reason=reason,
                    )
                    continue

                # (c2) Model pattern check
                model_pattern = item.get("model_pattern")
                if model_pattern:
                    pattern_rejected, pattern_reason = should_reject_model_pattern(
                        listing["title"], listing.get("params", ""), model_pattern,
                    )
                    if pattern_rejected:
                        logger.info("[SKIP] ad_id=%s reason=%r", ad_id, pattern_reason)
                        total_filtered += 1
                        await save_seen_ad(
                            ad_id=ad_id, item_id=item["id"],
                            price=listing.get("price", 0),
                            title=listing.get("title", ""),
                            url=listing.get("url", ""),
                            skip_reason=pattern_reason,
                        )
                        continue

                # (d) Extract full details
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

                # (e) Seller filter
                seller_rejected, seller_reason = should_reject_seller(
                    seller_type=details.get("seller_type", "private"),
                    seller_active_items=details.get("seller_active_items", 0),
                    max_seller_items=max_seller_items,
                )
                if seller_rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, seller_reason)
                    item_seller_skip += 1
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason=seller_reason,
                    )
                    continue

                # (f) Fetch full ad page for description + seller data
                ad_url = details.get("url", "")
                try:
                    extra = await api.fetch_ad_extra(ad_url)
                    if extra.get("description"):
                        details["description"] = extra["description"]
                    if extra.get("seller_active_items") and not details.get("seller_active_items"):
                        details["seller_active_items"] = extra["seller_active_items"]
                        seller_rejected2, seller_reason2 = should_reject_seller(
                            seller_type=details.get("seller_type", "private"),
                            seller_active_items=details["seller_active_items"],
                            max_seller_items=max_seller_items,
                        )
                        if seller_rejected2:
                            logger.info("[SKIP] ad_id=%s reason=%r (from ad page)", ad_id, seller_reason2)
                            item_seller_skip += 1
                            total_filtered += 1
                            await save_seen_ad(
                                ad_id=ad_id, item_id=item["id"],
                                price=details.get("price", 0),
                                title=details.get("title", ""),
                                url=details.get("url", ""),
                                skip_reason=seller_reason2,
                            )
                            continue
                    await asyncio.sleep(random.uniform(1.0, 3.0))
                except Exception as e:
                    logger.warning("Failed to fetch ad extra for %s: %s", ad_id, e)

                # (g) Instant-reject patterns in DESCRIPTION
                description = details.get("description", "")
                rejected, reason = should_instant_reject(details.get("title", ""), description)
                if rejected:
                    logger.info("[SKIP] ad_id=%s reason=%r", ad_id, reason)
                    item_desc_skip += 1
                    total_filtered += 1
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason=reason,
                    )
                    continue

                # (h) AI analysis
                logger.info(
                    "[AI] ad_id=%s title=%r price=%d",
                    ad_id, details.get("title", "")[:60], details.get("price", 0),
                )
                verdict = await analyze_ad(item, details)

                if not verdict:
                    item_ai_err += 1
                    total_errors += 1
                    # Graceful degradation: if AI is down, send raw alert
                    await save_seen_ad(
                        ad_id=ad_id, item_id=item["id"],
                        price=details.get("price", 0),
                        title=details.get("title", ""),
                        url=details.get("url", ""),
                        skip_reason="AI error",
                    )
                    continue

                item_ai_ok += 1
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
                    images = details.get("images", [])
                    reply_markup = ad_alert_keyboard(ad_url) if ad_url else None
                    try:
                        await _send_alert(
                            bot, chat_id, alert_text,
                            images=images, reply_markup=reply_markup,
                        )
                        total_alerts += 1
                    except Exception as e:
                        logger.error("Failed to send alert after retries: %s", e)
                        total_errors += 1

            # Per-item pipeline summary
            logger.info(
                "Item '%s' pipeline: %d total -> %d dedup, %d new "
                "-> %d price_skip, %d title_skip, %d seller_skip, "
                "%d desc_skip -> %d to_AI (%d ok, %d err)",
                item["name"], len(listings), item_dedup, item_new,
                item_price_skip, item_title_skip, item_seller_skip,
                item_desc_skip, item_ai_ok + item_ai_err,
                item_ai_ok, item_ai_err,
            )

            await api.delay()

    except Exception as e:
        logger.error("Scan cycle error for user %d: %s", user_id, e, exc_info=True)
    finally:
        await api.close()

    logger.info(
        "User %d scan complete: %d items, %d new, %d filtered, %d alerts, %d errors",
        user_id, len(items), total_new, total_filtered, total_alerts, total_errors,
    )

    # Graceful degradation: notify if all proxies dead
    if proxy_list and proxy_manager.healthy_count == 0 and chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="\u26a0\ufe0f Все прокси недоступны. Они будут восстановлены через 5 мин.",
            )
        except Exception as e:
            logger.error("Failed to send proxy alert: %s", e)
