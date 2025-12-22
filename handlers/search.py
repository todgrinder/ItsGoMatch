"""
Обработчики: /search, просмотр и присоединение к заявкам.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import aiosqlite

from config import GENDER_LABELS
from keyboards.inline import elements_list_kb, element_detail_kb, main_menu_kb, event_menu_kb
from database import queries as db_queries

router = Router()


# ==================== HELPERS ====================

def format_member_info(member: dict) -> str:
    """Форматировать информацию об участнике."""
    gender_icon = "👨" if member.get("gender") == "male" else "👩" if member.get("gender") == "female" else "👤"
    username = member.get("username", "Без имени")
    rating = member.get("rating", 0)
    return f"{gender_icon} {username} — рейтинг: {int(rating)}"


def format_members_list(members: list) -> str:
    """Форматировать список участников."""
    if not members:
        return "Пока никого нет"
    return "\n".join([f"• {format_member_info(m)}" for m in members])


def format_element_preview(element: dict) -> str:
    """
    Форматировать краткую информацию о заявке для списка.
    Для пар: пол, имя, рейтинг
    Для команд: количество участников, средний рейтинг
    """
    members = element.get("members", [])
    event_type = element.get("event_type", "pair")
    
    if event_type == "pair":
        # Для пар показываем информацию о единственном участнике
        if members:
            member = members[0]
            gender_icon = "👨" if member.get("gender") == "male" else "👩" if member.get("gender") == "female" else "👤"
            username = member.get("username", "Без имени")
            rating = member.get("rating", 0)
            return f"{gender_icon} {username}, ⭐{int(rating)}"
        else:
            return "Нет данных"
    else:
        # Для команд показываем количество участников и средний рейтинг
        members_count = len(members)
        target_size = element.get("target_size", 0)
        
        if members:
            ratings = [m["rating"] for m in members if m.get("rating") is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            return f"{members_count}/{target_size} чел., ⭐{int(avg_rating)}"
        else:
            return f"{members_count}/{target_size} чел."


# ==================== КОМАНДЫ ====================

@router.message(Command("search"))
async def cmd_search(message: Message, db: aiosqlite.Connection):
    """Поиск свободных заявок: /search 123."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "🔎 <b>Поиск свободных мест</b>\n\n"
            "Формат: /search &lt;event_id&gt;\n"
            "Пример: <code>/search 123</code>\n\n"
            "Или используйте кнопку «🔎 Поиск турниров» в главном меню.",
            parse_mode="HTML"
        )
        return
    
    try:
        event_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID турнира должен быть числом.")
        return
    
    # Проверяем существование события
    event = await db_queries.get_event(db, event_id)
    if not event:
        await message.answer("❌ Турнир не найден.")
        return
    
    if event["status"] != "open":
        await message.answer("❌ Этот турнир закрыт.")
        return
    
    # Получаем открытые заявки
    elements = await db_queries.list_open_elements(db, event_id)
    
    # Фильтруем заявки, где пользователь уже является участником
    filtered_elements = []
    for elem in elements:
        is_member = await db_queries.check_user_in_element(db, elem["element_id"], user_id)
        if not is_member:
            # Добавляем информацию для отображения
            elem["preview_info"] = format_element_preview(elem)
            filtered_elements.append(elem)
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event['team_size']} чел.)"
    
    if not filtered_elements:
        await message.answer(
            f"🔎 <b>Поиск в турнире «{event['title']}»</b>\n\n"
            f"🎯 Тип: {type_label}\n\n"
            "📭 Свободных мест пока нет.\n"
            "Добавьте себя первым!",
            reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == user_id)),
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f"🔎 <b>Свободные места в турнире «{event['title']}»</b>\n\n"
        f"🎯 Тип: {type_label}\n"
        f"📊 Найдено заявок: {len(filtered_elements)}",
        reply_markup=elements_list_kb(filtered_elements, event_id),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data.startswith("search_elements:"))
async def cb_search_elements(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Поиск свободных»."""
    event_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    # Проверяем существование события
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    if event["status"] != "open":
        await callback.answer("❌ Этот турнир закрыт", show_alert=True)
        return
    
    # Получаем открытые заявки
    elements = await db_queries.list_open_elements(db, event_id)
    
    # Фильтруем заявки, где пользователь уже является участником
    filtered_elements = []
    for elem in elements:
        is_member = await db_queries.check_user_in_element(db, elem["element_id"], user_id)
        if not is_member:
            # Добавляем информацию для отображения
            elem["preview_info"] = format_element_preview(elem)
            filtered_elements.append(elem)
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event['team_size']} чел.)"
    
    if not filtered_elements:
        await callback.message.edit_text(
            f"🔎 <b>Поиск в турнире «{event['title']}»</b>\n\n"
            f"🎯 Тип: {type_label}\n\n"
            "📭 Свободных мест пока нет.\n"
            "Добавьте себя, чтобы другие могли вас найти!",
            reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == user_id)),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"🔎 <b>Свободные места в турнире «{event['title']}»</b>\n\n"
            f"🎯 Тип: {type_label}\n"
            f"📊 Найдено заявок: {len(filtered_elements)}\n\n"
            "Выберите заявку для просмотра:",
            reply_markup=elements_list_kb(filtered_elements, event_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("view_element:"))
async def cb_view_element(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр деталей заявки."""
    element_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем заявку
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    if not element.get("is_active"):
        await callback.answer("❌ Эта заявка уже неактивна", show_alert=True)
        return
    
    event_id = element["event_id"]
    event = await db_queries.get_event(db, event_id)
    event_type = event.get("type", "pair")
    
    # Получаем участников
    members = await db_queries.get_element_members(db, element_id)
    
    target_size = element["target_size"]
    spots_left = target_size - len(members)
    description = element.get("description") or "—"
    
    # Проверяем, может ли пользователь присоединиться
    is_member = await db_queries.check_user_in_element(db, element_id, user_id)
    has_pending_request = await db_queries.check_existing_request(db, element_id, user_id)
    
    can_join = not is_member and not has_pending_request and spots_left > 0
    
    # Формируем статус
    status_text = ""
    if is_member:
        status_text = "\n\n✅ <i>Вы уже в этой заявке</i>"
    elif has_pending_request:
        status_text = "\n\n⏳ <i>Ваш запрос ожидает рассмотрения</i>"
    
    # Формируем информацию в зависимости от типа турнира
    if event_type == "pair":
        # Для пар показываем детальную информацию об игроке
        if members:
            member = members[0]
            gender_label = GENDER_LABELS.get(member.get("gender"), "Не указан")
            username = member.get("username", "Без имени")
            rating = int(member.get("rating", 0))
            
            await callback.message.edit_text(
                f"👥 <b>Заявка на пару #{element_id}</b>\n\n"
                f"📝 Описание: {description}\n\n"
                f"👤 <b>Игрок:</b>\n"
                f"• 📛 Имя: {username}\n"
                f"• 🚻 Пол: {gender_label}\n"
                f"• 📊 Рейтинг: {rating}\n\n"
                f"{status_text}",
                reply_markup=element_detail_kb(element_id, event_id, can_join=can_join),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"👥 <b>Заявка на пару #{element_id}</b>\n\n"
                f"📝 Описание: {description}\n\n"
                f"👤 Участников пока нет\n"
                f"{status_text}",
                reply_markup=element_detail_kb(element_id, event_id, can_join=can_join),
                parse_mode="HTML"
            )
    else:
        # Для команд показываем количество участников и средний рейтинг
        members_count = len(members)
        
        if members:
            ratings = [m["rating"] for m in members if m.get("rating") is not None]
            avg_rating = int(sum(ratings) / len(ratings)) if ratings else 0
            
            # Список участников
            members_text = format_members_list(members)
            
            await callback.message.edit_text(
                f"👨‍👩‍👧‍👦 <b>Командная заявка #{element_id}</b>\n\n"
                f"📝 Описание: {description}\n\n"
                f"👥 <b>Участники ({members_count}/{target_size}):</b>\n"
                f"{members_text}\n\n"
                f"⭐ Средний рейтинг команды: <b>{avg_rating}</b>\n"
                f"🪑 Свободных мест: {spots_left}"
                f"{status_text}",
                reply_markup=element_detail_kb(element_id, event_id, can_join=can_join),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"👨‍👩‍👧‍👦 <b>Командная заявка #{element_id}</b>\n\n"
                f"📝 Описание: {description}\n\n"
                f"👥 Участников: {members_count}/{target_size}\n"
                f"🪑 Свободных мест: {spots_left}"
                f"{status_text}",
                reply_markup=element_detail_kb(element_id, event_id, can_join=can_join),
                parse_mode="HTML"
            )
    
    await callback.answer()


@router.callback_query(F.data.startswith("join_element:"))
async def cb_join_element(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    """Кнопка «Присоединиться» к заявке."""
    element_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Обновляем telegram_username
    await db_queries.update_telegram_username(db, user_id, callback.from_user.username)
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    # Получаем заявку
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    if not element.get("is_active"):
        await callback.answer("❌ Эта заявка уже неактивна", show_alert=True)
        return
    
    event_id = element["event_id"]
    
    # Проверяем, что событие открыто
    event = await db_queries.get_event(db, event_id)
    if not event or event["status"] != "open":
        await callback.answer("❌ Турнир закрыт", show_alert=True)
        return
    
    # Проверяем, что пользователь не в этой заявке
    is_member = await db_queries.check_user_in_element(db, element_id, user_id)
    if is_member:
        await callback.answer("❌ Вы уже в этой заявке", show_alert=True)
        return
    
    # Проверяем, что нет активного запроса
    has_pending_request = await db_queries.check_existing_request(db, element_id, user_id)
    if has_pending_request:
        await callback.answer("❌ Вы уже отправили запрос к этой заявке", show_alert=True)
        return
    
    # Проверяем, есть ли свободные места
    spots_left = await db_queries.get_element_spots_left(db, element_id)
    if spots_left <= 0:
        await callback.answer("❌ В этой заявке больше нет свободных мест", show_alert=True)
        return
    
    # Создаём запрос на присоединение
    join_id = await db_queries.create_join_request(db, element_id, user_id)
    
    # Получаем данные для уведомления
    requester = await db_queries.get_user(db, user_id)
    creator_id = element["creator_id"]
    
    # Логируем
    await db_queries.create_log(
        db, 
        "join_request_created", 
        f"join_id={join_id}, element_id={element_id}, requester_id={user_id}"
    )
    
    # Уведомляем владельца заявки
    try:
        gender_icon = "👨" if requester.get("gender") == "male" else "👩" if requester.get("gender") == "female" else "👤"
        gender_label = GENDER_LABELS.get(requester.get("gender"), "Не указан")
        rating = int(requester.get("rating", 0))
        
        from keyboards.inline import join_request_kb
        await bot.send_message(
            creator_id,
            f"📨 <b>Новый запрос на присоединение!</b>\n\n"
            f"К вашей заявке в турнире «{event['title']}»\n\n"
            f"👤 <b>Игрок:</b>\n"
            f"• {gender_icon} Имя: <b>{requester.get('username', 'Без имени')}</b>\n"
            f"• 🚻 Пол: {gender_label}\n"
            f"• 📊 Рейтинг: <b>{rating}</b>\n\n"
            f"Принять этого участника?",
            reply_markup=join_request_kb(join_id),
            parse_mode="HTML"
        )
    except Exception as e:
        # Если не удалось отправить уведомление, всё равно создаём запрос
        pass
    
    await callback.answer("✅ Запрос отправлен!", show_alert=True)
    
    # Обновляем сообщение
    await callback.message.edit_text(
        f"📨 <b>Запрос отправлен!</b>\n\n"
        f"Заявка: #{element_id}\n"
        f"Турнир: {event['title']}\n\n"
        "Владелец заявки получит уведомление и сможет принять или отклонить вашу заявку.\n\n"
        "⏳ Ожидайте ответа.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
