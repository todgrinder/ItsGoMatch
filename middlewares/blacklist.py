"""
Middleware для проверки чёрного списка.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database import queries as db_queries


class BlacklistMiddleware(BaseMiddleware):
    """Middleware, которое блокирует пользователей из чёрного списка."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if user_id is None:
            return await handler(event, data)
        
        # Получаем соединение с БД
        db = data.get("db")
        if db is None:
            return await handler(event, data)
        
        # Проверяем, заблокирован ли пользователь
        is_banned = await db_queries.is_user_banned(db, user_id)
        
        if is_banned:
            # Получаем информацию о бане
            ban_info = await db_queries.get_ban_info(db, user_id)
            reason = ban_info.get("reason") if ban_info else None
            reason_text = f"\n\n📝 Причина: {reason}" if reason else ""
            
            # Отправляем сообщение о блокировке
            if isinstance(event, Message):
                await event.answer(
                    f"🚫 <b>Вы заблокированы</b>\n\n"
                    f"Доступ к боту ограничен.{reason_text}\n\n"
                    f"Если вы считаете, что это ошибка, обратитесь к администратору.",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "🚫 Вы заблокированы. Доступ к боту ограничен.",
                    show_alert=True
                )
            
            # Не вызываем следующий handler
            return None
        
        # Пользователь не заблокирован — продолжаем
        return await handler(event, data)
