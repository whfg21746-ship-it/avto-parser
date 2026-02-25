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


PID_FILE = "/tmp/avito-bot.pid"


def _kill_old_instance() -> None:
    """Kill any previous bot process using the PID file."""
    if os.path.exists(PID_FILE):
        try:
            old_pid = int(open(PID_FILE).read().strip())
            if old_pid != os.getpid():
                logger.info("Killing old bot process PID %d", old_pid)
                os.kill(old_pid, signal.SIGKILL)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass

    # Write our own PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


async def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    logger.info("Bot PID: %d", os.getpid())

    # Kill any stale bot process before we do anything
    _kill_old_instance()

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Force-cancel any stale Telegram polling session.
    logger.info("Clearing stale Telegram sessions...")
    try:
        await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=True), timeout=10)
    except Exception as e:
        logger.warning("delete_webhook failed: %s", e)
    await asyncio.sleep(1)
    # Short getUpdates to steal the polling slot (hard 5s timeout per attempt)
    for attempt in range(3):
        try:
            await asyncio.wait_for(
                bot.get_updates(offset=-1, timeout=1), timeout=5
            )
            break
        except asyncio.TimeoutError:
            logger.warning("get_updates attempt %d timed out", attempt + 1)
        except Exception:
            pass
        await asyncio.sleep(1)
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
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        logger.info("Bot stopped (PID %d)", os.getpid())


async def _shutdown(dp: Dispatcher, scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """Graceful shutdown: stop polling first, then cleanup."""
    logger.info("Received shutdown signal, stopping...")
    scheduler.shutdown(wait=False)
    await dp.stop_polling()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
