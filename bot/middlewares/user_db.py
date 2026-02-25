import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

import config
from db.database import current_user_id, ensure_db_initialized

logger = logging.getLogger(__name__)


class UserDBMiddleware(BaseMiddleware):
    """Sets per-user database context for every incoming event.

    Also enforces the ALLOWED_USERS whitelist when configured.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Enforce whitelist if configured
        if config.ALLOWED_USERS and user.id not in config.ALLOWED_USERS:
            logger.warning(
                "Unauthorized user %d (%s) blocked by whitelist",
                user.id, user.username or "no username",
            )
            # Try to send a message back
            event_obj = data.get("event")
            if hasattr(event_obj, "answer"):
                await event_obj.answer(
                    "У вас нет доступа к этому боту."
                )
            return None

        token = current_user_id.set(user.id)
        try:
            await ensure_db_initialized()
            return await handler(event, data)
        finally:
            current_user_id.reset(token)
