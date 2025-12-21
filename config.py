import os
from pathlib import Path

# Токен бота из переменной окружения или напрямую
BOT_TOKEN = os.getenv("BOT_TOKEN", "8418863320:AAFAjlsEeMhKM_IUqKUN4aRZ4bs2kOulf3M")

# ID владельца бота (администратора)
# Можно указать несколько через запятую: "123456789,987654321"
OWNER_IDS_STR = os.getenv("OWNER_IDS", "296289652")
OWNER_IDS = [int(x.strip()) for x in OWNER_IDS_STR.split(",") if x.strip().isdigit()]

# Путь к базе данных
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "bot.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# Константы для пола
GENDER_MALE = "male"
GENDER_FEMALE = "female"
GENDER_LABELS = {
    GENDER_MALE: "👨 Мужской",
    GENDER_FEMALE: "👩 Женский"
}


def is_owner(user_id: int) -> bool:
    """Проверить, является ли пользователь владельцем бота."""
    return user_id in OWNER_IDS
