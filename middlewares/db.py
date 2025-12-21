"""
Middleware для инъекции соединения с базой данных в хэндлеры.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.connection import get_db


class DatabaseMiddleware(BaseMiddleware):
    """Middleware, которое добавляет db‑соединение в data хэндлера."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Открываем соединение
        db = await get_db()
        data["db"] = db
        
        try:
            result = await handler(event, data)
        finally:
            # Закрываем соединение после обработки
            await db.close()
        
        return result
