"""
Планировщик задач для автоматического закрытия турниров.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta

from database.connection import get_db
from database import queries as db_queries

logger = logging.getLogger(__name__)


async def close_expired_events_task():
    """Задача закрытия просроченных турниров."""
    try:
        db = await get_db()
        try:
            # Текущая дата
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Получаем список турниров для закрытия (для логирования)
            expired_events = await db_queries.get_expired_events(db, current_date)
            
            if expired_events:
                # Закрываем турниры
                count = await db_queries.close_expired_events(db, current_date)
                
                # Логируем каждый закрытый турнир
                for event in expired_events:
                    await db_queries.create_log(
                        db,
                        "event_auto_closed",
                        f"event_id={event['event_id']}, title={event['title']}, event_date={event['event_date']}"
                    )
                
                logger.info(f"✅ Автоматически закрыто турниров: {count}")
            else:
                logger.debug("Нет турниров для автоматического закрытия")
                
        finally:
            await db.close()
            
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии турниров: {e}")


async def scheduler_loop():
    """
    Основной цикл планировщика.
    Запускает проверку каждый день в 00:05.
    """
    logger.info("🕐 Планировщик задач запущен")
    
    while True:
        try:
            # Вычисляем время до следующего запуска (00:05)
            now = datetime.now()
            next_run = datetime.combine(now.date() + timedelta(days=1), time(0, 5))
            
            # Если сейчас раньше 00:05, запускаем сегодня
            today_run = datetime.combine(now.date(), time(0, 5))
            if now < today_run:
                next_run = today_run
            
            wait_seconds = (next_run - now).total_seconds()
            
            logger.info(f"⏰ Следующая проверка турниров: {next_run.strftime('%Y-%m-%d %H:%M')}")
            
            # Ждём до следующего запуска
            await asyncio.sleep(wait_seconds)
            
            # Выполняем задачу
            await close_expired_events_task()
            
        except asyncio.CancelledError:
            logger.info("🛑 Планировщик остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            # Ждём минуту перед повторной попыткой
            await asyncio.sleep(60)


async def run_scheduler():
    """Запустить планировщик в фоне."""
    # Сразу выполняем проверку при запуске
    await close_expired_events_task()
    
    # Запускаем цикл
    await scheduler_loop()
