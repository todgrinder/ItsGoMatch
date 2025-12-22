"""
Обработчики: /my_profile, /set_username, /set_rating, /set_gender.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from config import GENDER_LABELS
from keyboards.inline import profile_menu_kb, gender_with_cancel_kb, main_menu_kb, cancel_kb
from database import queries as db_queries

router = Router()


# ==================== FSM ====================

class ProfileFSM(StatesGroup):
    waiting_new_username = State()
    waiting_new_rating = State()
    waiting_new_gender = State()


# ==================== HELPERS ====================

async def show_profile(message_or_callback, db: aiosqlite.Connection, user_id: int, edit: bool = False):
    """Показать профиль пользователя."""
    user = await db_queries.get_user(db, user_id)
    
    if not user:
        text = (
            "❌ Профиль не найден.\n\n"
            "Используйте /start для регистрации."
        )
        if edit and hasattr(message_or_callback, 'message'):
            await message_or_callback.message.edit_text(text)
        else:
            await message_or_callback.answer(text)
        return
    
    username = user.get("username") or "Не указано"
    rating = user.get("rating")
    rating_text = str(int(rating)) if rating is not None else "Не указан"
    gender = GENDER_LABELS.get(user.get("gender"), "Не указан")
    
    # Получаем статистику
    user_groups = await db_queries.get_user_groups(db, user_id)
    user_elements = await db_queries.get_all_user_active_elements(db, user_id)
    pending_sent = await db_queries.get_pending_requests_for_user(db, user_id)
    pending_incoming = await db_queries.get_incoming_requests_for_user(db, user_id)
    
    text = (
        "👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: <b>{username}</b>\n"
        f"🚻 Пол: {gender}\n"
        f"📊 Рейтинг: <b>{rating_text}</b>\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Активные заявки: {len(user_elements)}\n"
        f"• Сформированные группы: {len(user_groups)}\n"
        f"• Отправленные запросы: {len(pending_sent)}\n"
        f"• Входящие запросы: {len(pending_incoming)}"
    )
    
    if edit and hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=profile_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=profile_menu_kb(),
            parse_mode="HTML"
        )


# ==================== КОМАНДЫ ====================

@router.message(Command("my_profile"))
async def cmd_my_profile(message: Message, db: aiosqlite.Connection):
    """Показать профиль пользователя."""
    await show_profile(message, db, message.from_user.id)


@router.message(Command("set_username"))
async def cmd_set_username(message: Message, db: aiosqlite.Connection):
    """Установить имя: /set_username Nickname."""
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    user = await db_queries.get_user(db, user_id)
    if not user:
        await message.answer(
            "❌ Сначала зарегистрируйтесь.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "📛 <b>Изменение имени</b>\n\n"
            "Формат: /set_username &lt;имя&gt;\n"
            "Пример: <code>/set_username Вася</code>",
            parse_mode="HTML"
        )
        return
    
    username = args[1].strip()
    
    if not username:
        await message.answer("❌ Имя не может быть пустым.")
        return
    
    if len(username) > 50:
        await message.answer("❌ Имя слишком длинное (максимум 50 символов).")
        return
    
    # Обновляем в БД
    await db_queries.update_username(db, user_id, username)
    
    # Логируем
    await db_queries.create_log(db, "username_updated", f"user_id={user_id}, new_username={username}")
    
    await message.answer(
        f"✅ Имя обновлено: <b>{username}</b>",
        reply_markup=profile_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("set_rating"))
async def cmd_set_rating(message: Message, db: aiosqlite.Connection):
    """Установить рейтинг: /set_rating 1500."""
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    user = await db_queries.get_user(db, user_id)
    if not user:
        await message.answer(
            "❌ Сначала зарегистрируйтесь.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "📊 <b>Установка рейтинга</b>\n\n"
            "Формат: /set_rating &lt;число&gt;\n"
            "Пример: <code>/set_rating 1500</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        rating = float(args[1].strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число.")
        return
    
    if rating < 0 or rating > 100000:
        await message.answer("❌ Рейтинг должен быть от 0 до 100 000.")
        return
    
    old_rating = user.get("rating")
    
    # Обновляем в БД
    await db_queries.update_rating(db, user_id, rating)
    
    # Логируем
    await db_queries.create_log(db, "rating_updated", f"user_id={user_id}, old={old_rating}, new={rating}")
    
    change_text = ""
    if old_rating is not None:
        diff = rating - old_rating
        if diff > 0:
            change_text = f" (↑ +{diff:.1f})"
        elif diff < 0:
            change_text = f" (↓ {diff:.1f})"
    
    await message.answer(
        f"✅ Рейтинг обновлён: <b>{rating:.1f}</b>{change_text}",
        reply_markup=profile_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("set_gender"))
async def cmd_set_gender(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Изменить пол."""
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    user = await db_queries.get_user(db, user_id)
    if not user:
        await message.answer(
            "❌ Сначала зарегистрируйтесь.\n"
            "Используйте /start"
        )
        return
    
    await state.set_state(ProfileFSM.waiting_new_gender)
    await message.answer(
        "🚻 <b>Изменение пола</b>\n\n"
        "Выберите:",
        reply_markup=gender_with_cancel_kb(),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data == "my_profile")
async def cb_my_profile(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Мой профиль»."""
    await show_profile(callback, db, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "change_username")
async def cb_change_username(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Кнопка «Изменить имя»."""
    user_id = callback.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    user = await db_queries.get_user(db, user_id)
    current_name = user.get("username", "не указано")
    
    await state.set_state(ProfileFSM.waiting_new_username)
    await callback.message.edit_text(
        f"📛 <b>Изменение имени</b>\n\n"
        f"Текущее имя: <b>{current_name}</b>\n\n"
        "Введите новое имя (никнейм):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "change_rating")
async def cb_change_rating(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Кнопка «Изменить рейтинг»."""
    user_id = callback.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    user = await db_queries.get_user(db, user_id)
    current_rating = user.get("rating")
    rating_text = f"{current_rating:.1f}" if current_rating is not None else "не указан"
    
    await state.set_state(ProfileFSM.waiting_new_rating)
    await callback.message.edit_text(
        f"📊 <b>Изменение рейтинга</b>\n\n"
        f"Текущий рейтинг: <b>{rating_text}</b>\n\n"
        "Введите новое значение рейтинга (число):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "change_gender")
async def cb_change_gender(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Кнопка «Изменить пол»."""
    user_id = callback.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    user = await db_queries.get_user(db, user_id)
    current_gender = GENDER_LABELS.get(user.get("gender"), "не указан")
    
    await state.set_state(ProfileFSM.waiting_new_gender)
    await callback.message.edit_text(
        f"🚻 <b>Изменение пола</b>\n\n"
        f"Текущий пол: <b>{current_gender}</b>\n\n"
        "Выберите новое значение:",
        reply_markup=gender_with_cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== FSM HANDLERS ====================

@router.message(ProfileFSM.waiting_new_username)
async def fsm_new_username(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили новое имя."""
    username = message.text.strip()
    user_id = message.from_user.id
    
    if not username:
        await message.answer(
            "❌ Имя не может быть пустым.\n\n"
            "📛 Введите новое имя:"
        )
        return
    
    if len(username) > 50:
        await message.answer(
            "❌ Имя слишком длинное (максимум 50 символов).\n\n"
            "📛 Введите новое имя:"
        )
        return
    
    await state.clear()
    
    # Обновляем в БД
    await db_queries.update_username(db, user_id, username)
    
    # Логируем
    await db_queries.create_log(db, "username_updated", f"user_id={user_id}, new_username={username}")
    
    await message.answer(
        f"✅ Имя обновлено: <b>{username}</b>",
        reply_markup=profile_menu_kb(),
        parse_mode="HTML"
    )


@router.message(ProfileFSM.waiting_new_rating)
async def fsm_new_rating(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили новый рейтинг."""
    user_id = message.from_user.id
    
    try:
        rating = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число.\n\n"
            "Например: <code>1500</code> или <code>1234</code>",
            parse_mode="HTML"
        )
        return
    
    if rating < 0 or rating > 100000:
        await message.answer(
            "❌ Рейтинг должен быть от 0 до 100 000.\n\n"
            "📊 Введите рейтинг:"
        )
        return
    
    await state.clear()
    
    # Получаем старый рейтинг для сравнения
    user = await db_queries.get_user(db, user_id)
    old_rating = user.get("rating") if user else None
    
    # Обновляем в БД
    await db_queries.update_rating(db, user_id, rating)
    
    # Логируем
    await db_queries.create_log(db, "rating_updated", f"user_id={user_id}, old={old_rating}, new={rating}")
    
    change_text = ""
    if old_rating is not None:
        diff = rating - old_rating
        if diff > 0:
            change_text = f" (↑ +{int(diff)})"
        elif diff < 0:
            change_text = f" (↓ {int(diff)})"
    
    await message.answer(
        f"✅ Рейтинг обновлён: <b>{int(rating)}</b>{change_text}",
        reply_markup=profile_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(ProfileFSM.waiting_new_gender, F.data.startswith("set_gender:"))
async def fsm_new_gender(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Выбрали новый пол."""
    gender = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    await state.clear()
    
    # Обновляем в БД
    await db_queries.update_gender(db, user_id, gender)
    
    # Логируем
    await db_queries.create_log(db, "gender_updated", f"user_id={user_id}, new_gender={gender}")
    
    await callback.message.edit_text(
        f"✅ Пол обновлён: <b>{GENDER_LABELS[gender]}</b>",
        reply_markup=profile_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
