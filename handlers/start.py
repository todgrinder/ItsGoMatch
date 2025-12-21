"""
Обработчики: /start, /help, главное меню, регистрация.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from config import GENDER_LABELS
from keyboards.inline import main_menu_kb, gender_kb, cancel_kb
from database import queries as db_queries

router = Router()


# ==================== FSM для регистрации ====================

class RegistrationFSM(StatesGroup):
    waiting_username = State()
    waiting_gender = State()
    waiting_rating = State()


# ==================== КОМАНДЫ ====================

@router.message(CommandStart())
async def cmd_start(message: Message, db: aiosqlite.Connection, state: FSMContext):
    """Обработка команды /start."""
    user_id = message.from_user.id
    telegram_username = message.from_user.username  # Получаем @username из Telegram
    
    # Очищаем возможное предыдущее состояние
    await state.clear()
    
    # Проверяем, есть ли пользователь в БД
    user = await db_queries.get_user(db, user_id)
    
    if user is None:
        # Новый пользователь — создаём запись и начинаем регистрацию
        await db_queries.create_user(db, user_id, telegram_username)
        
        await state.set_state(RegistrationFSM.waiting_username)
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Я бот для формирования пар и команд на турниры.\n\n"
            "Для начала давай заполним твой профиль.\n\n"
            "📛 <b>Шаг 1/3:</b> Введите ваше имя (никнейм):",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
    else:
        # Существующий пользователь — обновляем telegram_username (мог измениться)
        if user.get("telegram_username") != telegram_username:
            await db_queries.update_telegram_username(db, user_id, telegram_username)
        
        # Проверяем, заполнен ли профиль
        profile_complete = await db_queries.is_profile_complete(db, user_id)
        
        if not profile_complete:
            # Профиль не заполнен — определяем, какой шаг нужен
            if user.get("username") is None:
                await state.set_state(RegistrationFSM.waiting_username)
                await message.answer(
                    "👋 <b>С возвращением!</b>\n\n"
                    "Давай завершим регистрацию.\n\n"
                    "📛 <b>Шаг 1/3:</b> Введите ваше имя (никнейм):",
                    reply_markup=cancel_kb(),
                    parse_mode="HTML"
                )
            elif user.get("gender") is None:
                await state.set_state(RegistrationFSM.waiting_gender)
                await message.answer(
                    f"👋 <b>С возвращением, {user['username']}!</b>\n\n"
                    "Давай завершим регистрацию.\n\n"
                    "🚻 <b>Шаг 2/3:</b> Выберите ваш пол:",
                    reply_markup=gender_kb(),
                    parse_mode="HTML"
                )
            elif user.get("rating") is None:
                await state.set_state(RegistrationFSM.waiting_rating)
                await message.answer(
                    f"👋 <b>С возвращением, {user['username']}!</b>\n\n"
                    "Давай завершим регистрацию.\n\n"
                    "📊 <b>Шаг 3/3:</b> Введите ваш текущий рейтинг (число):",
                    parse_mode="HTML"
                )
        else:
            # Профиль заполнен — показываем главное меню
            await show_main_menu(message, user)


async def show_main_menu(message: Message, user: dict = None):
    """Показать главное меню."""
    if user:
        greeting = f"👋 Привет, <b>{user.get('username', 'Пользователь')}</b>!\n\n"
    else:
        greeting = ""
    
    await message.answer(
        f"{greeting}"
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработка команды /help."""
    help_text = """
📖 <b>Справка по командам</b>

<b>Основные:</b>
/start — Начать работу / Главное меню
/help — Эта справка

<b>Профиль:</b>
/my_profile — Показать мой профиль
/set_username &lt;имя&gt; — Изменить имя
/set_rating &lt;число&gt; — Установить рейтинг
/set_gender — Изменить пол

<b>Турниры:</b>
/create_event — Создать турнир
/list_events — Список открытых турниров
/close_event &lt;id&gt; — Закрыть турнир (только владелец)

<b>Элементы (пары/команды):</b>
/add_solo &lt;event_id&gt; — Добавить себя как одиночку
/my_elements &lt;event_id&gt; — Мои элементы в турнире
/search &lt;event_id&gt; — Поиск свободных элементов

<b>Запросы:</b>
/accept &lt;join_id&gt; — Принять запрос
/reject &lt;join_id&gt; — Отклонить запрос

<b>Аккаунт:</b>
/delete_me — Удалить все мои данные
"""
    await message.answer(help_text, parse_mode="HTML")


# ==================== FSM: Регистрация ====================

@router.message(RegistrationFSM.waiting_username)
async def fsm_registration_username(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Пользователь ввёл имя при регистрации."""
    username = message.text.strip()
    
    if not username:
        await message.answer(
            "❌ Имя не может быть пустым.\n\n"
            "📛 Введите ваше имя (никнейм):"
        )
        return
    
    if len(username) > 50:
        await message.answer(
            "❌ Имя слишком длинное (максимум 50 символов).\n\n"
            "📛 Введите ваше имя (никнейм):"
        )
        return
    
    user_id = message.from_user.id
    telegram_username = message.from_user.username
    
    # Сохраняем имя и обновляем telegram_username в БД
    await db_queries.update_user_profile(db, user_id, username=username, telegram_username=telegram_username)
    
    await state.set_state(RegistrationFSM.waiting_gender)
    
    await message.answer(
        f"✅ Имя: <b>{username}</b>\n\n"
        "🚻 <b>Шаг 2/3:</b> Выберите ваш пол:",
        reply_markup=gender_kb(),
        parse_mode="HTML"
    )


@router.callback_query(RegistrationFSM.waiting_gender, F.data.startswith("set_gender:"))
async def fsm_registration_gender(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Пользователь выбрал пол при регистрации."""
    gender = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Сохраняем пол в БД
    await db_queries.update_gender(db, user_id, gender)
    
    await state.set_state(RegistrationFSM.waiting_rating)
    await callback.message.edit_text(
        f"✅ Пол: <b>{GENDER_LABELS[gender]}</b>\n\n"
        "📊 <b>Шаг 3/3:</b> Введите ваш текущий рейтинг (число):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(RegistrationFSM.waiting_rating)
async def fsm_registration_rating(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Пользователь ввёл рейтинг при регистрации."""
    try:
        rating = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число.\n\n"
            "Например: <code>1500</code> или <code>1234.5</code>",
            parse_mode="HTML"
        )
        return
    
    if rating < 0 or rating > 100000:
        await message.answer(
            "❌ Рейтинг должен быть от 0 до 100 000.\n\n"
            "📊 Введите ваш рейтинг:"
        )
        return
    
    user_id = message.from_user.id
    
    # Сохраняем рейтинг в БД
    await db_queries.update_rating(db, user_id, rating)
    
    await state.clear()
    
    # Получаем обновлённые данные пользователя
    user = await db_queries.get_user(db, user_id)
    gender_label = GENDER_LABELS.get(user.get("gender"), "Не указан")
    
    # Логируем регистрацию
    await db_queries.create_log(db, "user_registered", f"user_id={user_id}, username={user.get('username')}")
    
    await message.answer(
        "🎉 <b>Регистрация завершена!</b>\n\n"
        f"📛 Имя: {user.get('username')}\n"
        f"🚻 Пол: {gender_label}\n"
        f"📊 Рейтинг: {rating}\n\n"
        "Теперь вы можете пользоваться ботом!",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    """Кнопка помощи."""
    help_text = """
📖 <b>Краткая справка</b>

🔹 <b>Турниры</b> — создавайте свои или присоединяйтесь к существующим
🔹 <b>Элементы</b> — добавляйте себя в турнир, чтобы найти пару/команду
🔹 <b>Запросы</b> — отправляйте запросы на присоединение и принимайте их

Полная справка: /help
"""
    await callback.message.edit_text(
        help_text,
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Возврат в главное меню."""
    await state.clear()
    
    user = await db_queries.get_user(db, callback.from_user.id)
    
    # Обновляем telegram_username при каждом взаимодействии
    telegram_username = callback.from_user.username
    if user and user.get("telegram_username") != telegram_username:
        await db_queries.update_telegram_username(db, callback.from_user.id, telegram_username)
    
    username = user.get("username", "Пользователь") if user else "Пользователь"
    
    await callback.message.edit_text(
        f"🏠 <b>Главное меню</b>\n\n"
        f"Привет, <b>{username}</b>! Выберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Отмена текущего действия."""
    await state.clear()
    
    # Проверяем, зарегистрирован ли пользователь полностью
    user_id = callback.from_user.id
    profile_complete = await db_queries.is_profile_complete(db, user_id)
    
    if profile_complete:
        await callback.message.edit_text(
            "❌ Действие отменено.\n\n"
            "🏠 <b>Главное меню</b>",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ Действие отменено.\n\n"
            "⚠️ Ваш профиль не заполнен до конца.\n"
            "Используйте /start чтобы продолжить регистрацию.",
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Пустой callback (ничего не делает)."""
    await callback.answer()
