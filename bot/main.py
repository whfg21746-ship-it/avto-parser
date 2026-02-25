import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot.handlers import categories, items, settings, start
from bot.middlewares.user_db import UserDBMiddleware
from db.database import close_all_connections
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


async def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Per-user database middleware (must be registered before routers)
    dp.message.middleware(UserDBMiddleware())
    dp.callback_query.middleware(UserDBMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(items.router)
    dp.include_router(categories.router)
    dp.include_router(settings.router)

    # Set up scheduler — runs at a base tick rate, per-user intervals
    # are checked inside the scan cycle itself.
    tick_interval = min(config.SCAN_INTERVAL, 30)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_scan,
        "interval",
        seconds=tick_interval,
        args=[bot],
        id="avito_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started with tick interval %d seconds (user intervals may vary)",
        tick_interval,
    )

    # CRITICAL: aiogram 3 does NOT call delete_webhook before polling.
    # Without this, if a previous polling session is still alive on Telegram's
    # servers, we get TelegramConflictError (409) ping-pong forever.
    # delete_webhook forces Telegram to drop any stale session state.
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Telegram session reset OK")
    except Exception as e:
        logger.warning("delete_webhook failed (non-fatal): %s", e)

    try:
        logger.info("Starting polling...")
        # handle_signals=True (default) — aiogram handles SIGTERM/SIGINT gracefully
        # close_bot_session=True — aiogram closes aiohttp session on shutdown
        await dp.start_polling(bot, close_bot_session=True)
    finally:
        scheduler.shutdown(wait=False)
        await close_all_connections()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
