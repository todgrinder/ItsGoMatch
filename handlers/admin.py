"""
Обработчики администратора: управление чёрным списком и турнирами.
"""

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from config import is_owner, GENDER_LABELS
from keyboards.inline import (
    admin_menu_kb,
    blacklist_kb,
    confirm_kb,
    cancel_kb,
    main_menu_kb,
    admin_events_menu_kb,
    admin_events_list_kb,
    admin_event_detail_kb
)
from database import queries as db_queries

router = Router()


# ==================== FSM ====================

class BanUserFSM(StatesGroup):
    waiting_user_id = State()
    waiting_reason = State()


class UnbanUserFSM(StatesGroup):
    waiting_user_id = State()


class DeleteEventFSM(StatesGroup):
    waiting_event_id = State()


# ==================== HELPERS ====================

def format_date_ru(date_str: str) -> str:
    """Форматировать дату в русский формат."""
    if not date_str:
        return "Не указана"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        months = [
            "", "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        return f"{dt.day} {months[dt.month]} {dt.year}"
    except:
        return date_str


# ==================== ФИЛЬТР ВЛАДЕЛЬЦА ====================

def owner_filter(message: Message) -> bool:
    """Фильтр: только владелец бота."""
    return is_owner(message.from_user.id)


def owner_callback_filter(callback: CallbackQuery) -> bool:
    """Фильтр для callback: только владелец бота."""
    return is_owner(callback.from_user.id)


# ==================== КОМАНДЫ ====================

@router.message(Command("admin"), owner_filter)
async def cmd_admin(message: Message, db: aiosqlite.Connection):
    """Панель администратора."""
    # Получаем статистику
    blacklist_count = await db_queries.get_blacklist_count(db)
    
    # Общая статистика
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    users_count = (await cursor.fetchone())[0]
    
    events_open = await db_queries.get_events_count(db, "open")
    events_closed = await db_queries.get_events_count(db, "closed")
    events_total = events_open + events_closed
    
    cursor = await db.execute("SELECT COUNT(*) FROM groups")
    groups_count = (await cursor.fetchone())[0]
    
    await message.answer(
        "🔐 <b>Панель администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Пользователей: {users_count}\n"
        f"• Турниров: {events_total} (открытых: {events_open}, закрытых: {events_closed})\n"
        f"• Сформированных групп: {groups_count}\n"
        f"• В чёрном списке: {blacklist_count}\n",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("ban"), owner_filter)
async def cmd_ban(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Заблокировать пользователя: /ban <user_id> [причина]."""
    args = message.text.split(maxsplit=2)
    
    if len(args) < 2:
        await state.set_state(BanUserFSM.waiting_user_id)
        await message.answer(
            "🚫 <b>Блокировка пользователя</b>\n\n"
            "Введите ID пользователя для блокировки:\n\n"
            "<i>Вы можете узнать ID, переслав сообщение пользователя боту @userinfobot</i>",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return
    
    # Проверяем, не пытается ли владелец заблокировать себя или другого владельца
    if is_owner(user_id):
        await message.answer("❌ Нельзя заблокировать владельца бота.")
        return
    
    reason = args[2].strip() if len(args) > 2 else None
    
    # Проверяем, не заблокирован ли уже
    if await db_queries.is_user_banned(db, user_id):
        await message.answer(
            f"❌ Пользователь {user_id} уже в чёрном списке.\n\n"
            f"Используйте /unban {user_id} для разблокировки."
        )
        return
    
    # Блокируем
    await db_queries.add_to_blacklist(db, user_id, message.from_user.id, reason)
    
    # Получаем информацию о пользователе
    user = await db_queries.get_user(db, user_id)
    username = user.get("username", "Неизвестный") if user else "Неизвестный"
    
    # Логируем
    await db_queries.create_log(
        db,
        "user_banned",
        f"user_id={user_id}, banned_by={message.from_user.id}, reason={reason}"
    )
    
    reason_text = f"\n📝 Причина: {reason}" if reason else ""
    
    await message.answer(
        f"✅ <b>Пользователь заблокирован</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {username}"
        f"{reason_text}",
        parse_mode="HTML"
    )


@router.message(Command("unban"), owner_filter)
async def cmd_unban(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Разблокировать пользователя: /unban <user_id>."""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await state.set_state(UnbanUserFSM.waiting_user_id)
        await message.answer(
            "✅ <b>Разблокировка пользователя</b>\n\n"
            "Введите ID пользователя для разблокировки:",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return
    
    # Проверяем, заблокирован ли
    if not await db_queries.is_user_banned(db, user_id):
        await message.answer(f"❌ Пользователь {user_id} не в чёрном списке.")
        return
    
    # Получаем информацию перед удалением
    ban_info = await db_queries.get_ban_info(db, user_id)
    
    # Разблокируем
    await db_queries.remove_from_blacklist(db, user_id)
    
    # Логируем
    await db_queries.create_log(
        db,
        "user_unbanned",
        f"user_id={user_id}, unbanned_by={message.from_user.id}"
    )
    
    username = ban_info.get("banned_user_name", "Неизвестный") if ban_info else "Неизвестный"
    
    await message.answer(
        f"✅ <b>Пользователь разблокирован</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {username}",
        parse_mode="HTML"
    )


@router.message(Command("blacklist"), owner_filter)
async def cmd_blacklist(message: Message, db: aiosqlite.Connection):
    """Показать чёрный список."""
    blacklist = await db_queries.get_blacklist(db, limit=20)
    total = await db_queries.get_blacklist_count(db)
    
    if not blacklist:
        await message.answer(
            "📋 <b>Чёрный список</b>\n\n"
            "Список пуст.",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
        return
    
    text = "📋 <b>Чёрный список</b>\n\n"
    
    for i, ban in enumerate(blacklist, 1):
        username = ban.get("banned_user_name") or "Неизвестный"
        reason = ban.get("reason") or "Не указана"
        banned_at = ban.get("banned_at", "?")[:10]  # Только дата
        
        text += (
            f"{i}. <b>{username}</b> (ID: <code>{ban['user_id']}</code>)\n"
            f"   📝 {reason}\n"
            f"   📅 {banned_at}\n\n"
        )
    
    if total > 20:
        text += f"\n... и ещё {total - 20} пользователей"
    
    await message.answer(
        text,
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.message(Command("check_user"), owner_filter)
async def cmd_check_user(message: Message, db: aiosqlite.Connection):
    """Проверить информацию о пользователе: /check_user <user_id>."""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Проверка пользователя</b>\n\n"
            "Формат: /check_user &lt;user_id&gt;\n"
            "Пример: <code>/check_user 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return
    
    # Получаем информацию о пользователе
    user = await db_queries.get_user(db, user_id)
    is_banned = await db_queries.is_user_banned(db, user_id)
    ban_info = await db_queries.get_ban_info(db, user_id) if is_banned else None
    
    if not user and not is_banned:
        await message.answer(
            f"❌ Пользователь с ID <code>{user_id}</code> не найден в базе данных.",
            parse_mode="HTML"
        )
        return
    
    # Формируем информацию
    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"🆔 ID: <code>{user_id}</code>\n"
    
    if user:
        username = user.get("username") or "Не указано"
        telegram_username = user.get("telegram_username")
        telegram_text = f"@{telegram_username}" if telegram_username else "Не указан"
        rating = user.get("rating")
        rating_text = f"{rating:.1f}" if rating is not None else "Не указан"
        gender = GENDER_LABELS.get(user.get("gender"), "Не указан")
        created_at = user.get("created_at", "?")[:10]
        
        text += (
            f"👤 Имя: {username}\n"
            f"📱 Telegram: {telegram_text}\n"
            f"🚻 Пол: {gender}\n"
            f"📊 Рейтинг: {rating_text}\n"
            f"📅 Регистрация: {created_at}\n"
        )
        
        # Статистика
        groups = await db_queries.get_user_groups(db, user_id)
        elements = await db_queries.get_all_user_active_elements(db, user_id)
        events = await db_queries.list_user_events(db, user_id)
        text += (
            f"\n📈 <b>Статистика:</b>\n"
            f"• Создано турниров: {len(events)}\n"
            f"• Активных элементов: {len(elements)}\n"
            f"• Сформированных групп: {len(groups)}\n"
        )
    else:
        text += "👤 Пользователь не зарегистрирован\n"
    
    # Информация о бане
    if is_banned:
        reason = ban_info.get("reason") or "Не указана"
        banned_at = ban_info.get("banned_at", "?")[:10]
        admin_name = ban_info.get("admin_name") or "Неизвестный"
        
        text += (
            f"\n🚫 <b>ЗАБЛОКИРОВАН</b>\n"
            f"📝 Причина: {reason}\n"
            f"📅 Дата: {banned_at}\n"
            f"👮 Заблокировал: {admin_name}\n"
        )
    else:
        text += "\n✅ Не заблокирован\n"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("delete_event"), owner_filter)
async def cmd_delete_event(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Удалить турнир: /delete_event <event_id>."""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await state.set_state(DeleteEventFSM.waiting_event_id)
        await message.answer(
            "🗑️ <b>Удаление турнира</b>\n\n"
            "Введите ID турнира для удаления:",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
        return
    
    try:
        event_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID турнира должен быть числом.")
        return
    
    # Получаем информацию о турнире
    event_info = await db_queries.get_event_full_info(db, event_id)
    if not event_info:
        await message.answer(f"❌ Турнир с ID {event_id} не найден.")
        return
    
    # Формируем информацию для подтверждения
    event = event_info
    owner = event_info.get("owner")
    stats = event_info.get("stats")
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    date_text = format_date_ru(event.get("event_date"))
    owner_name = owner.get("username", "Неизвестный") if owner else "Неизвестный"
    
    await message.answer(
        f"🗑️ <b>Удаление турнира</b>\n\n"
        f"📌 Название: {event['title']}\n"
        f"🎯 Тип: {type_label}\n"
        f"📅 Дата: {date_text}\n"
        f"👤 Владелец: {owner_name} (ID: {event['owner_id']})\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n"
        f"• Участников в группах: {stats['users_in_groups']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n\n"
        f"⚠️ <b>Внимание!</b> Это действие необратимо.\n"
        f"Все связанные данные будут удалены.\n\n"
        f"Вы уверены?",
        reply_markup=confirm_kb("admin_delete_event", event_id),
        parse_mode="HTML"
    )


# ==================== FSM HANDLERS ====================

@router.message(BanUserFSM.waiting_user_id)
async def fsm_ban_user_id(message: Message, state: FSMContext):
    """Получили ID для бана."""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом.\n\n"
            "Введите ID пользователя:"
        )
        return
    
    if is_owner(user_id):
        await message.answer("❌ Нельзя заблокировать владельца бота.")
        await state.clear()
        return
    
    await state.update_data(user_id=user_id)
    await state.set_state(BanUserFSM.waiting_reason)
    
    await message.answer(
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"Введите причину блокировки\n"
        f"(или отправьте <code>-</code> чтобы пропустить):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(BanUserFSM.waiting_reason)
async def fsm_ban_reason(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили причину бана."""
    data = await state.get_data()
    await state.clear()
    
    user_id = data["user_id"]
    reason = message.text.strip()
    if reason == "-":
        reason = None
    
    # Проверяем, не заблокирован ли уже
    if await db_queries.is_user_banned(db, user_id):
        await message.answer(
            f"❌ Пользователь {user_id} уже в чёрном списке.",
            reply_markup=admin_menu_kb()
        )
        return
    
    # Блокируем
    await db_queries.add_to_blacklist(db, user_id, message.from_user.id, reason)
    
    # Получаем информацию о пользователе
    user = await db_queries.get_user(db, user_id)
    username = user.get("username", "Неизвестный") if user else "Неизвестный"
    
    # Логируем
    await db_queries.create_log(
        db,
        "user_banned",
        f"user_id={user_id}, banned_by={message.from_user.id}, reason={reason}"
    )
    
    reason_text = f"\n📝 Причина: {reason}" if reason else ""
    
    await message.answer(
        f"✅ <b>Пользователь заблокирован</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {username}"
        f"{reason_text}",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.message(UnbanUserFSM.waiting_user_id)
async def fsm_unban_user_id(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили ID для разбана."""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом.\n\n"
            "Введите ID пользователя:"
        )
        return
    
    await state.clear()
    
    # Проверяем, заблокирован ли
    if not await db_queries.is_user_banned(db, user_id):
        await message.answer(
            f"❌ Пользователь {user_id} не в чёрном списке.",
            reply_markup=admin_menu_kb()
        )
        return
    
    # Получаем информацию перед удалением
    ban_info = await db_queries.get_ban_info(db, user_id)
    
    # Разблокируем
    await db_queries.remove_from_blacklist(db, user_id)
    
    # Логируем
    await db_queries.create_log(
        db,
        "user_unbanned",
        f"user_id={user_id}, unbanned_by={message.from_user.id}"
    )
    
    username = ban_info.get("banned_user_name", "Неизвестный") if ban_info else "Неизвестный"
    
    await message.answer(
        f"✅ <b>Пользователь разблокирован</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {username}",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.message(DeleteEventFSM.waiting_event_id)
async def fsm_delete_event_id(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили ID турнира для удаления."""
    try:
        event_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ ID должен быть числом.\n\n"
            "Введите ID турнира:"
        )
        return
    
    await state.clear()
    
    # Получаем информацию о турнире
    event_info = await db_queries.get_event_full_info(db, event_id)
    if not event_info:
        await message.answer(
            f"❌ Турнир с ID {event_id} не найден.",
            reply_markup=admin_menu_kb()
        )
        return
    
    # Формируем информацию для подтверждения
    event = event_info
    owner = event_info.get("owner")
    stats = event_info.get("stats")
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    date_text = format_date_ru(event.get("event_date"))
    owner_name = owner.get("username", "Неизвестный") if owner else "Неизвестный"
    
    await message.answer(
        f"🗑️ <b>Удаление турнира</b>\n\n"
        f"📌 Название: {event['title']}\n"
        f"🎯 Тип: {type_label}\n"
        f"📅 Дата: {date_text}\n"
        f"👤 Владелец: {owner_name} (ID: {event['owner_id']})\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n"
        f"• Участников в группах: {stats['users_in_groups']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n\n"
        f"⚠️ <b>Внимание!</b> Это действие необратимо.\n"
        f"Все связанные данные будут удалены.\n\n"
        f"Вы уверены?",
        reply_markup=confirm_kb("admin_delete_event", event_id),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data == "admin_blacklist", owner_callback_filter)
async def cb_admin_blacklist(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Чёрный список»."""
    blacklist = await db_queries.get_blacklist(db, limit=10)
    total = await db_queries.get_blacklist_count(db)
    
    if not blacklist:
        await callback.message.edit_text(
            "📋 <b>Чёрный список</b>\n\n"
            "Список пуст.",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"📋 <b>Чёрный список ({total})</b>\n\n"
    
    for ban in blacklist:
        username = ban.get("banned_user_name") or "Неизвестный"
        reason = ban.get("reason") or "—"
        text += f"• <b>{username}</b> (<code>{ban['user_id']}</code>): {reason}\n"
    
    if total > 10:
        text += f"\n... и ещё {total - 10}\n"
    
    text += "\nИспользуйте /blacklist для полного списка"
    
    await callback.message.edit_text(
        text,
        reply_markup=blacklist_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_ban", owner_callback_filter)
async def cb_admin_add_ban(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Добавить в ЧС»."""
    await state.set_state(BanUserFSM.waiting_user_id)
    await callback.message.edit_text(
        "🚫 <b>Блокировка пользователя</b>\n\n"
        "Введите ID пользователя для блокировки:\n\n"
        "<i>Вы можете узнать ID, переслав сообщение пользователя боту @userinfobot</i>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_remove_ban", owner_callback_filter)
async def cb_admin_remove_ban(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Убрать из ЧС»."""
    await state.set_state(UnbanUserFSM.waiting_user_id)
    await callback.message.edit_text(
        "✅ <b>Разблокировка пользователя</b>\n\n"
        "Введите ID пользователя для разблокировки:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== УПРАВЛЕНИЕ ТУРНИРАМИ ====================

@router.callback_query(F.data == "admin_events", owner_callback_filter)
async def cb_admin_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Турниры»."""
    await callback.message.edit_text(
        "🏆 <b>Управление турнирами</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_events_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_all_events", owner_callback_filter)
async def cb_admin_all_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать все турниры."""
    events = await db_queries.get_all_events(db, status=None, limit=15)
    total = await db_queries.get_events_count(db)
    
    if not events:
        await callback.message.edit_text(
            "📋 <b>Все турниры</b>\n\n"
            "Турниров нет.",
            reply_markup=admin_events_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"📋 <b>Все турниры ({total})</b>\n\n"
        "Выберите турнир для просмотра:",
        reply_markup=admin_events_list_kb(events),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_open_events", owner_callback_filter)
async def cb_admin_open_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать открытые турниры."""
    events = await db_queries.get_all_events(db, status="open", limit=15)
    total = await db_queries.get_events_count(db, "open")
    
    if not events:
        await callback.message.edit_text(
            "📋 <b>Открытые турниры</b>\n\n"
            "Нет открытых турниров.",
            reply_markup=admin_events_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"🟢 <b>Открытые турниры ({total})</b>\n\n"
        "Выберите турнир для просмотра:",
        reply_markup=admin_events_list_kb(events),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_closed_events", owner_callback_filter)
async def cb_admin_closed_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать закрытые турниры."""
    events = await db_queries.get_all_events(db, status="closed", limit=15)
    total = await db_queries.get_events_count(db, "closed")
    
    if not events:
        await callback.message.edit_text(
            "📋 <b>Закрытые турниры</b>\n\n"
            "Нет закрытых турниров.",
            reply_markup=admin_events_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"🔴 <b>Закрытые турниры ({total})</b>\n\n"
        "Выберите турнир для просмотра:",
        reply_markup=admin_events_list_kb(events),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_event:"), owner_callback_filter)
async def cb_admin_view_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр турнира администратором."""
    event_id = int(callback.data.split(":")[1])
    
    # Получаем полную информацию о турнире
    event_info = await db_queries.get_event_full_info(db, event_id)
    if not event_info:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    event = event_info
    owner = event_info.get("owner")
    stats = event_info.get("stats")
    
    # Форматируем информацию
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    status_label = "🟢 Открыт" if event["status"] == "open" else "🔴 Закрыт"
    date_text = format_date_ru(event.get("event_date"))
    description = event.get("description") or "—"
    
    owner_name = owner.get("username", "Неизвестный") if owner else "Неизвестный"
    owner_telegram = owner.get("telegram_username") if owner else None
    owner_contact = f"@{owner_telegram}" if owner_telegram else f"ID: {event['owner_id']}"
    
    created_at = event.get("created_at", "?")[:10]
    
    await callback.message.edit_text(
        f"🔍 <b>Детали турнира (Админ)</b>\n\n"
        f"📌 <b>{event['title']}</b>\n\n"
        f"🎯 Тип: {type_label}\n"
        f"📅 Дата: {date_text}\n"
        f"📝 Описание: {description}\n"
        f"📊 Статус: {status_label}\n"
        f"📆 Создан: {created_at}\n\n"
        f"👤 <b>Владелец:</b>\n"
        f"• {owner_name} ({owner_contact})\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n"
        f"• Участников в группах: {stats['users_in_groups']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n\n"
        f"🆔 ID: <code>{event_id}</code>",
        reply_markup=admin_event_detail_kb(event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_event:"), owner_callback_filter)
async def cb_admin_confirm_delete_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать подтверждение удаления турнира."""
    event_id = int(callback.data.split(":")[1])
    
    # Получаем информацию о турнире
    event_info = await db_queries.get_event_full_info(db, event_id)
    if not event_info:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    event = event_info
    owner = event_info.get("owner")
    stats = event_info.get("stats")
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    date_text = format_date_ru(event.get("event_date"))
    owner_name = owner.get("username", "Неизвестный") if owner else "Неизвестный"
    
    await callback.message.edit_text(
        f"🗑️ <b>Удаление турнира</b>\n\n"
        f"📌 Название: {event['title']}\n"
        f"🎯 Тип: {type_label}\n"
        f"📅 Дата: {date_text}\n"
        f"👤 Владелец: {owner_name} (ID: {event['owner_id']})\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n"
        f"• Участников в группах: {stats['users_in_groups']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n\n"
        f"⚠️ <b>Внимание!</b> Это действие необратимо.\n"
        f"Все связанные данные будут удалены.\n\n"
        f"Вы уверены?",
        reply_markup=confirm_kb("admin_delete_event", event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:admin_delete_event:"), owner_callback_filter)
async def cb_confirm_admin_delete_event(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    """Подтверждение удаления турнира."""
    event_id = int(callback.data.split(":")[2])
    
    # Получаем информацию перед удалением
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    event_title = event["title"]
    owner_id = event["owner_id"]
    
    # Получаем всех участников групп для уведомления
    groups = await db_queries.get_event_groups(db, event_id)
    all_members = set()
    for group in groups:
        members = await db_queries.get_group_members(db, group["group_id"])
        for member in members:
            all_members.add(member["user_id"])
    
    # Получаем всех участников элементов
    cursor = await db.execute(
        """
        SELECT DISTINCT em.user_id
        FROM element_members em
        JOIN elements e ON em.element_id = e.element_id
        WHERE e.event_id = ?
        """,
        (event_id,)
    )
    rows = await cursor.fetchall()
    for row in rows:
        all_members.add(row[0])
    
    # Удаляем турнир
    success = await db_queries.delete_event(db, event_id)
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "event_deleted_by_admin",
            f"event_id={event_id}, title={event_title}, admin_id={callback.from_user.id}"
        )
        
        # Уведомляем владельца
        try:
            await bot.send_message(
                owner_id,
                f"⚠️ <b>Ваш турнир удалён администратором</b>\n\n"
                f"📌 Турнир: {event_title}\n"
                f"🆔 ID: {event_id}\n\n"
                f"Если у вас есть вопросы, обратитесь к администратору.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        # Уведомляем всех участников
        for member_id in all_members:
            if member_id != owner_id:  # Владельцу уже отправили
                try:
                    await bot.send_message(
                        member_id,
                        f"⚠️ <b>Турнир удалён</b>\n\n"
                        f"📌 Турнир «{event_title}» был удалён администратором.\n\n"
                        f"Все связанные элементы и группы также удалены.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        
        await callback.message.edit_text(
            f"✅ <b>Турнир удалён</b>\n\n"
            f"📌 {event_title}\n"
            f"🆔 ID: {event_id}\n\n"
            f"Владелец и {len(all_members)} участников получили уведомление.",
            reply_markup=admin_events_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer("Турнир удалён")
    else:
        await callback.answer("❌ Не удалось удалить турнир", show_alert=True)


@router.callback_query(F.data == "admin_delete_event_start", owner_callback_filter)
async def cb_admin_delete_event_start(callback: CallbackQuery, state: FSMContext):
    """Начать процесс удаления турнира."""
    await state.set_state(DeleteEventFSM.waiting_event_id)
    await callback.message.edit_text(
        "🗑️ <b>Удаление турнира</b>\n\n"
        "Введите ID турнира для удаления:\n\n"
        "<i>ID можно найти в списке турниров или использовать команду /check_event</i>",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_close_event:"), owner_callback_filter)
async def cb_admin_close_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Закрыть турнир (администратор)."""
    event_id = int(callback.data.split(":")[1])
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    if event["status"] == "closed":
        await callback.answer("❌ Турнир уже закрыт", show_alert=True)
        return
    
    # Закрываем от имени владельца (но логируем что это админ)
    await db.execute(
        "UPDATE events SET status = 'closed' WHERE event_id = ?",
        (event_id,)
    )
    await db.commit()
    
    # Логируем
    await db_queries.create_log(
        db,
        "event_closed_by_admin",
        f"event_id={event_id}, admin_id={callback.from_user.id}"
    )
    
    await callback.answer("✅ Турнир закрыт", show_alert=True)
    
    # Обновляем информацию
    await cb_admin_view_event.__wrapped__(callback, db)


@router.callback_query(F.data.startswith("admin_open_event:"), owner_callback_filter)
async def cb_admin_open_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Открыть турнир (администратор)."""
    event_id = int(callback.data.split(":")[1])
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    if event["status"] == "open":
        await callback.answer("❌ Турнир уже открыт", show_alert=True)
        return
    
    # Открываем
    await db.execute(
        "UPDATE events SET status = 'open' WHERE event_id = ?",
        (event_id,)
    )
    await db.commit()
    
    # Логируем
    await db_queries.create_log(
        db,
        "event_opened_by_admin",
        f"event_id={event_id}, admin_id={callback.from_user.id}"
    )
    
    await callback.answer("✅ Турнир открыт", show_alert=True)
    
    # Обновляем информацию
    await cb_admin_view_event.__wrapped__(callback, db)


@router.callback_query(F.data.startswith("admin_view_owner:"), owner_callback_filter)
async def cb_admin_view_owner(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр профиля владельца турнира."""
    event_id = int(callback.data.split(":")[1])
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    owner_id = event["owner_id"]
    
    # Получаем информацию о владельце
    user = await db_queries.get_user(db, owner_id)
    is_banned = await db_queries.is_user_banned(db, owner_id)
    
    if not user:
        await callback.answer("❌ Владелец не найден в базе", show_alert=True)
        return
    
    username = user.get("username", "Не указано")
    telegram_username = user.get("telegram_username")
    telegram_text = f"@{telegram_username}" if telegram_username else "Не указан"
    rating = user.get("rating")
    rating_text = f"{rating:.1f}" if rating is not None else "Не указан"
    gender = GENDER_LABELS.get(user.get("gender"), "Не указан")
    
    # Статистика
    groups = await db_queries.get_user_groups(db, owner_id)
    elements = await db_queries.get_all_user_active_elements(db, owner_id)
    events = await db_queries.list_user_events(db, owner_id)
    
    banned_text = "\n\n🚫 <b>ЗАБЛОКИРОВАН</b>" if is_banned else ""
    
    await callback.message.edit_text(
        f"👤 <b>Профиль владельца турнира</b>\n\n"
        f"🆔 ID: <code>{owner_id}</code>\n"
        f"📛 Имя: {username}\n"
        f"📱 Telegram: {telegram_text}\n"
        f"🚻 Пол: {gender}\n"
        f"📊 Рейтинг: {rating_text}\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Создано турниров: {len(events)}\n"
        f"• Активных элементов: {len(elements)}\n"
        f"• Сформированных групп: {len(groups)}"
        f"{banned_text}",
        reply_markup=admin_event_detail_kb(event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_admin", owner_callback_filter)
async def cb_back_admin(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Возврат в админ-панель."""
    await state.clear()
    
    # Получаем статистику
    blacklist_count = await db_queries.get_blacklist_count(db)
    
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    users_count = (await cursor.fetchone())[0]
    
    events_open = await db_queries.get_events_count(db, "open")
    events_closed = await db_queries.get_events_count(db, "closed")
    events_total = events_open + events_closed
    
    cursor = await db.execute("SELECT COUNT(*) FROM groups")
    groups_count = (await cursor.fetchone())[0]
    
    await callback.message.edit_text(
        "🔐 <b>Панель администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Пользователей: {users_count}\n"
        f"• Турниров: {events_total} (открытых: {events_open}, закрытых: {events_closed})\n"
        f"• Сформированных групп: {groups_count}\n"
        f"• В чёрном списке: {blacklist_count}\n",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== ОБРАБОТКА НЕ-ВЛАДЕЛЬЦЕВ ====================

@router.message(Command("admin"))
async def cmd_admin_denied(message: Message):
    """Попытка доступа к админ-панели не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")


@router.message(Command("ban"))
async def cmd_ban_denied(message: Message):
    """Попытка бана не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")


@router.message(Command("unban"))
async def cmd_unban_denied(message: Message):
    """Попытка разбана не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")


@router.message(Command("blacklist"))
async def cmd_blacklist_denied(message: Message):
    """Попытка просмотра ЧС не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")


@router.message(Command("check_user"))
async def cmd_check_user_denied(message: Message):
    """Попытка проверки пользователя не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")


@router.message(Command("delete_event"))
async def cmd_delete_event_denied(message: Message):
    """Попытка удаления турнира не-владельцем."""
    await message.answer("🚫 У вас нет доступа к этой команде.")
