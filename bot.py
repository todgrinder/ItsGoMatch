"""
Точка входа — запуск бота.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OWNER_IDS
from database.connection import init_db
from handlers import setup_routers
from middlewares import DatabaseMiddleware, BlacklistMiddleware
from scheduler import run_scheduler


async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    # Проверка конфигурации
    if not OWNER_IDS:
        logger.warning("⚠️ OWNER_IDS не указаны! Админ-функции будут недоступны.")
    else:
        logger.info(f"👑 Владельцы бота: {OWNER_IDS}")
    
    # Инициализация БД
    await init_db()
    
    # Создание бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Хранилище для FSM (в памяти)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Подключение middleware (порядок важен!)
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.message.middleware(BlacklistMiddleware())
    dp.callback_query.middleware(BlacklistMiddleware())
    
    # Подключение роутеров
    dp.include_router(setup_routers())
    
    # Запуск планировщика в фоне
    scheduler_task = asyncio.create_task(run_scheduler())
    
    # Запуск бота
    logger.info("🚀 Бот запущен!")
    
    try:
        await dp.start_polling(bot)
    finally:
        # Останавливаем планировщик
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
