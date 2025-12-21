import aiosqlite
from config import DB_PATH, SCHEMA_PATH


async def init_db():
    """Инициализация базы данных (создание таблиц)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = f.read()
        
        await db.executescript(schema)
        await db.commit()
        print("✅ База данных инициализирована")


async def get_db() -> aiosqlite.Connection:
    """Получить соединение с БД."""
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA foreign_keys = ON;")
    db.row_factory = aiosqlite.Row  # доступ к колонкам по имени
    return db
