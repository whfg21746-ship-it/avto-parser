import asyncio
import logging
import os
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot.handlers import categories, items, settings, start
from bot.middlewares.user_db import UserDBMiddleware
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

    logger.info("Bot PID: %d", os.getpid())

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Force-cancel any stale polling session from a crashed process.
    # delete_webhook cancels webhooks, getUpdates(offset=-1, timeout=1)
    # forces Telegram to drop any lingering long-poll connection.
    logger.info("Clearing stale Telegram sessions...")
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    try:
        await bot.get_updates(offset=-1, timeout=1)
    except Exception:
        pass
    logger.info("Stale sessions cleared, starting bot...")

    # Per-user database middleware (must be registered before routers)
    dp.message.middleware(UserDBMiddleware())
    dp.callback_query.middleware(UserDBMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(items.router)
    dp.include_router(categories.router)
    dp.include_router(settings.router)

    # Set up scheduler
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        scheduled_scan,
        "interval",
        seconds=config.SCAN_INTERVAL,
        args=[bot],
        id="avito_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with interval %d seconds", config.SCAN_INTERVAL)

    # Graceful shutdown on SIGTERM (systemctl stop)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(dp, scheduler, bot)))

    try:
        logger.info("Bot starting polling...")
        await dp.start_polling(bot, close_bot_session=True)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped (PID %d)", os.getpid())


async def _shutdown(dp: Dispatcher, scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """Graceful shutdown: stop polling first, then cleanup."""
    logger.info("Received shutdown signal, stopping...")
    scheduler.shutdown(wait=False)
    await dp.stop_polling()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
