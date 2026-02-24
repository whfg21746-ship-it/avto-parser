import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from bot.handlers import items, settings, start
from db.database import init_db
from db.models import get_setting
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

    # Initialize database
    await init_db()

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
