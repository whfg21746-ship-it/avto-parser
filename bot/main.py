import asyncio
import fcntl
import logging
import os
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot.handlers import categories, items, settings, start, stats
from bot.middlewares.user_db import UserDBMiddleware
from db.database import close_all_connections
from parser.scheduler import run_scan_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Global reference to prevent GC from closing the lock file
_lock_file = None


def ensure_single_instance() -> None:
    """Prevent multiple bot instances via PID lock file."""
    global _lock_file
    _lock_file = open("/tmp/avito-bot.lock", "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
    except IOError:
        print("Bot already running! Exiting.")
        sys.exit(1)


async def scheduled_scan(bot: Bot, scheduler: AsyncIOScheduler) -> None:
    """Wrapper for the scan cycle called by APScheduler.

    Uses self-rescheduling instead of a fixed interval so the next scan
    starts only *after* the current one finishes, eliminating overlaps
    and 'maximum number of running instances reached' warnings.
    """
    try:
        await run_scan_cycle(bot)
    except Exception as e:
        logger.error("Scheduled scan error: %s", e)
    finally:
        tick = min(config.SCAN_INTERVAL, 30)
        scheduler.add_job(
            scheduled_scan,
            "date",
            run_date=datetime.now() + timedelta(seconds=tick),
            args=[bot, scheduler],
            id="avito_scan",
            replace_existing=True,
        )


async def main() -> None:
    ensure_single_instance()

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
    dp.include_router(stats.router)

    # Set up scheduler — first scan runs immediately, subsequent scans
    # are rescheduled after each completion (self-rescheduling pattern).
    tick_interval = min(config.SCAN_INTERVAL, 30)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_scan,
        "date",
        run_date=datetime.now() + timedelta(seconds=5),
        args=[bot, scheduler],
        id="avito_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started (self-rescheduling, base tick %d seconds)",
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
