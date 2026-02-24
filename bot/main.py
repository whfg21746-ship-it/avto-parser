import asyncio
import json
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot.handlers import items, settings, start
from db.database import init_db
from db.models import (
    get_items_missing_params,
    get_setting,
    update_category_avito_id,
    update_item_params,
)
from parser.param_discovery import ParamDiscovery
from parser.proxy_manager import ProxyManager
from parser.scheduler import run_scan_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def scheduled_scan(bot: Bot) -> None:
    """Wrapper for the scan cycle called by APScheduler."""
    try:
        await run_scan_cycle(bot)
    except Exception as e:
        logger.error("Scheduled scan error: %s", e)


async def auto_discover_missing_params() -> None:
    """On startup, discover params for items that have empty/placeholder avito_params."""
    items_missing = await get_items_missing_params()
    if not items_missing:
        logger.info("All items already have Avito params, skipping auto-discovery")
        return

    logger.info("Found %d items with missing params, running auto-discovery...", len(items_missing))

    # Load proxies
    proxy_raw = await get_setting("proxy_list")
    try:
        proxy_list = json.loads(proxy_raw) if proxy_raw else []
    except json.JSONDecodeError:
        proxy_list = []
    if not proxy_list:
        proxy_list = config.PROXY_LIST

    proxy_manager = ProxyManager(proxy_list)
    discovery = ParamDiscovery(proxy_manager)

    # Group by search_query to avoid duplicate lookups
    query_map: dict[str, list[dict]] = {}
    for item in items_missing:
        query = item.get("search_query") or item["name"]
        if query not in query_map:
            query_map[query] = []
        query_map[query].append(item)

    discovered = 0
    failed = 0

    try:
        for i, (query, group_items) in enumerate(query_map.items()):
            result = await discovery.discover_and_verify(query)

            if result.get("category_id") and not result.get("error"):
                params_json = json.dumps(result.get("params", {}))
                category_id = result["category_id"]

                for item in group_items:
                    await update_item_params(item["id"], params_json)
                    if item.get("category_id"):
                        await update_category_avito_id(item["category_id"], category_id)

                discovered += 1
                logger.info(
                    "Discovered params for '%s': categoryId=%s (%d/%d)",
                    query, category_id, i + 1, len(query_map),
                )
            else:
                failed += 1
                logger.warning("Failed to discover params for '%s' (%d/%d)", query, i + 1, len(query_map))

            if i < len(query_map) - 1:
                await asyncio.sleep(3)

    except Exception as e:
        logger.error("Auto-discovery error: %s", e)
    finally:
        await discovery.close()

    logger.info(
        "Auto-discovery complete: %d discovered, %d failed out of %d unique queries",
        discovered, failed, len(query_map),
    )


async def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    # Initialize database
    await init_db()

    # Auto-discover missing params on startup
    try:
        await auto_discover_missing_params()
    except Exception as e:
        logger.error("Startup param discovery failed: %s", e)

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers
    dp.include_router(start.router)
    dp.include_router(items.router)
    dp.include_router(settings.router)

    # Set up scheduler
    scheduler = AsyncIOScheduler()

    interval_str = await get_setting("scan_interval_seconds")
    interval = int(interval_str) if interval_str else config.SCAN_INTERVAL

    scheduler.add_job(
        scheduled_scan,
        "interval",
        seconds=interval,
        args=[bot],
        id="avito_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with interval %d seconds", interval)

    # aiogram 3.x handles SIGINT/SIGTERM gracefully on its own
    try:
        logger.info("Bot starting...")
        await dp.start_polling(bot, close_bot_session=False)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
