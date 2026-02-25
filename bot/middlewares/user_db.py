import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db.database import current_user_id, ensure_db_initialized

logger = logging.getLogger(__name__)


class UserDBMiddleware(BaseMiddleware):
    """Sets per-user database context for every incoming event."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        token = current_user_id.set(user.id)
        try:
            await ensure_db_initialized()
            return await handler(event, data)
        finally:
            current_user_id.reset(token)
