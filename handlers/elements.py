"""
Обработчики: /add_solo, /add_partial, /my_elements.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from config import GENDER_LABELS
from keyboards.inline import (
    my_elements_kb,
    manage_element_kb,
    main_menu_kb,
    cancel_kb,
    confirm_kb,
    event_menu_kb,
    add_type_kb  # Новая клавиатура
)
from database import queries as db_queries

router = Router()


# ==================== FSM ====================

class AddElementFSM(StatesGroup):
    waiting_type = State()  # Новый шаг: выбор типа (solo/team)
    waiting_teammates = State()  # Новый шаг: ввод тиммейтов
    waiting_description = State()


# ==================== HELPERS ====================

def format_member_info(member: dict) -> str:
    """Форматировать информацию об участнике."""
    gender_icon = "👨" if member.get("gender") == "male" else "👩" if member.get("gender") == "female" else "👤"
    username = member.get("username", "Без имени")
    rating = member.get("rating", "?")
    return f"{gender_icon} {username} — рейтинг: {rating}"


async def find_users_by_telegram_username(db: aiosqlite.Connection, usernames: list) -> dict:
    """
    Найти пользователей по их Telegram username.
    Возвращает словарь: {username: user_data} или {username: None} если не найден
    """
    result = {}
    
    for username in usernames:
        # Убираем @ если есть
        clean_username = username.lstrip('@').strip().lower()
        
        if not clean_username:
            continue
        
        # Ищем пользователя по telegram_username (без учёта регистра)
        cursor = await db.execute(
            """
            SELECT * FROM users 
            WHERE LOWER(telegram_username) = ?
            """,
            (clean_username,)
        )
        row = await cursor.fetchone()
        
        if row:
            from database.queries import row_to_dict
            result[username] = row_to_dict(row)
        else:
            result[username] = None
    
    return result


# ==================== КОМАНДЫ ====================

@router.message(Command("add_solo"))
async def cmd_add_solo(message: Message, db: aiosqlite.Connection, state: FSMContext):
    """Добавить себя как одиночку: /add_solo 123."""
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
            "➕ <b>Добавить себя в турнир</b>\n\n"
            "Формат: /add_solo &lt;event_id&gt;\n"
            "Пример: <code>/add_solo 123</code>\n\n"
            "Или найдите турнир через «🔎 Поиск турниров» в главном меню.",
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
        await message.answer("❌ Этот турнир закрыт для новых участников.")
        return
    
    # Проверяем, что пользователь ещё не в элементе этого события
    has_element = await db_queries.check_user_has_element(db, event_id, user_id)
    if has_element:
        await message.answer(
            "❌ Вы уже добавлены в этот турнир.\n\n"
            "Используйте /my_elements для просмотра ваших заявок."
        )
        return
    
    # Проверяем, не состоит ли пользователь уже в группе этого события
    in_group = await db_queries.check_user_in_group(db, event_id, user_id)
    if in_group:
        await message.answer(
            "❌ Вы уже состоите в сформированной группе в этом турнире."
        )
        return
    
    # Сохраняем event_id в state и запрашиваем описание
    await state.update_data(
        event_id=event_id, 
        event_title=event["title"], 
        target_size=event["team_size"] or 2,
        add_type="solo",
        initial_members=[user_id]
    )
    await state.set_state(AddElementFSM.waiting_description)
    
    type_label = "пару" if event["type"] == "pair" else f"команду ({event['team_size']} чел.)"
    
    await message.answer(
        f"➕ <b>Добавление в турнир «{event['title']}»</b>\n\n"
        f"Вы ищете {type_label}.\n\n"
        f"Введите описание/комментарий к вашей заявке\n"
        f"(например, ваш опыт, предпочтения, время игры)\n\n"
        f"Или отправьте <code>-</code> чтобы пропустить:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(Command("add_partial"))
async def cmd_add_partial(message: Message, db: aiosqlite.Connection):
    """Добавить неполную команду: /add_partial 123."""
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
            "➕ <b>Добавить неполную команду</b>\n\n"
            "Формат: /add_partial &lt;event_id&gt;\n"
            "Пример: <code>/add_partial 123</code>\n\n"
            "После этого вы сможете указать участников команды.",
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
        await message.answer("❌ Этот турнир закрыт для новых участников.")
        return
    
    # Проверка типа турнира - частичную команду можно добавить только в командный турнир
    if event["type"] == "pair":
        await message.answer(
            "❌ В парном турнире можно добавить только себя.\n\n"
            f"Используйте: /add_solo {event_id}"
        )
        return
    
    # Проверяем, что пользователь ещё не в элементе этого события
    has_element = await db_queries.check_user_has_element(db, event_id, user_id)
    if has_element:
        await message.answer(
            "❌ Вы уже добавлены в этот турнир.\n\n"
            "Используйте /my_elements для просмотра ваших заявок."
        )
        return
    
    # Проверяем, не состоит ли пользователь уже в группе
    in_group = await db_queries.check_user_in_group(db, event_id, user_id)
    if in_group:
        await message.answer(
            "❌ Вы уже состоите в сформированной группе в этом турнире."
        )
        return
    
    await message.answer(
        f"➕ <b>Добавление команды в турнир</b>\n\n"
        f"📌 Турнир: {event['title']}\n"
        f"👥 Размер команды: {event['team_size']}\n\n"
        "Используйте кнопку «➕ Добавить себя» в меню турнира для выбора типа добавления.",
        reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == user_id)),
        parse_mode="HTML"
    )


@router.message(Command("my_elements"))
async def cmd_my_elements(message: Message, db: aiosqlite.Connection):
    """Мои заявки в турнире: /my_elements 123."""
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
        # Показываем все элементы пользователя во всех событиях
        elements = await db_queries.get_all_user_active_elements(db, user_id)
        
        if not elements:
            await message.answer(
                "📦 <b>Мои заявки</b>\n\n"
                "У вас пока нет активных заявок.\n"
                "Добавьте себя в турнир с помощью /add_solo &lt;event_id&gt;",
                reply_markup=main_menu_kb(),
                parse_mode="HTML"
            )
            return
        
        elements_text = ""
        for elem in elements[:10]:  # Максимум 10
            event_title = elem.get("event_title", f"Турнир #{elem['event_id']}")
            elements_text += f"\n• {event_title} — заявка #{elem['element_id']}"
        
        await message.answer(
            f"📦 <b>Мои заявки ({len(elements)})</b>\n"
            f"{elements_text}\n\n"
            f"Для просмотра в конкретном турнире:\n"
            f"/my_elements &lt;event_id&gt;",
            reply_markup=main_menu_kb(),
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
    
    # Получаем элементы пользователя в этом событии
    elements = await db_queries.get_user_elements(db, event_id, user_id)
    
    if not elements:
        await message.answer(
            f"📦 <b>Мои заявки в турнире «{event['title']}»</b>\n\n"
            "У вас нет заявок в этом турнире.\n"
            f"Добавьте себя: /add_solo {event_id}",
            reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == user_id)),
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f"📦 <b>Мои заявки в турнире «{event['title']}»</b>",
        reply_markup=my_elements_kb(elements, event_id),
        parse_mode="HTML"
    )


@router.message(Command("my_groups"))
async def cmd_my_groups(message: Message, db: aiosqlite.Connection):
    """Показать группы пользователя."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    groups = await db_queries.get_user_groups(db, user_id)
    
    if not groups:
        await message.answer(
            "👥 <b>Мои группы</b>\n\n"
            "Вы пока не состоите ни в одной сформированной группе.\n"
            "Присоединяйтесь к турнирам и находите партнёров!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return
    
    groups_text = ""
    for group in groups[:10]:  # Максимум 10
        event_title = group.get("event_title", f"Турнир #{group['event_id']}")
        avg_rating = group.get("rating_avg", 0)
        members_count = group.get("members_count", 0)
        groups_text += f"\n• {event_title}\n  Группа #{group['group_id']} — {members_count} чел., ⭐ {avg_rating:.0f}"
    
    await message.answer(
        f"👥 <b>Мои группы ({len(groups)})</b>\n"
        f"{groups_text}",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data.startswith("add_element:"))
async def cb_add_element(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Кнопка «Добавить себя»."""
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
    
    # Проверяем, что пользователь ещё не в элементе этого события
    has_element = await db_queries.check_user_has_element(db, event_id, user_id)
    if has_element:
        await callback.answer("❌ Вы уже добавлены в этот турнир", show_alert=True)
        return
    
    # Проверяем, не состоит ли пользователь уже в группе
    in_group = await db_queries.check_user_in_group(db, event_id, user_id)
    if in_group:
        await callback.answer("❌ Вы уже в сформированной группе", show_alert=True)
        return
    
    # Сохраняем данные
    await state.update_data(
        event_id=event_id, 
        event_title=event["title"], 
        target_size=event["team_size"] or 2,
        event_type=event["type"]
    )
    
    # Для парного турнира сразу переходим к описанию
    if event["type"] == "pair":
        await state.update_data(add_type="solo", initial_members=[user_id])
        await state.set_state(AddElementFSM.waiting_description)
        
        await callback.message.edit_text(
            f"➕ <b>Добавление в турнир «{event['title']}»</b>\n\n"
            f"Вы ищете пару.\n\n"
            f"Введите описание/комментарий к вашей заявке:\n"
            f"(например, ваш опыт, предпочтения, время игры)\n\n"
            f"Или отправьте <code>-</code> чтобы пропустить:",
            reply_markup=cancel_kb(),
            parse_mode="HTML"
        )
    else:
        # Для командного турнира предлагаем выбрать тип
        await state.set_state(AddElementFSM.waiting_type)
        
        await callback.message.edit_text(
            f"➕ <b>Добавление в турнир «{event['title']}»</b>\n\n"
            f"👥 Размер команды: {event['team_size']}\n\n"
            f"Выберите тип добавления:",
            reply_markup=add_type_kb(),
            parse_mode="HTML"
        )
    
    await callback.answer()


# ==================== FSM: Выбор типа добавления ====================

@router.callback_query(AddElementFSM.waiting_type, F.data == "add_type_solo")
async def fsm_add_type_solo(callback: CallbackQuery, state: FSMContext):
    """Выбрали добавление себя одного."""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    await state.update_data(add_type="solo", initial_members=[user_id])
    await state.set_state(AddElementFSM.waiting_description)
    
    await callback.message.edit_text(
        f"➕ <b>Добавление в турнир «{data['event_title']}»</b>\n\n"
        f"Вы ищете команду ({data['target_size']} чел.).\n\n"
        f"Введите описание/комментарий к вашей заявке:\n"
        f"(например, ваш опыт, предпочтения, время игры)\n\n"
        f"Или отправьте <code>-</code> чтобы пропустить:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AddElementFSM.waiting_type, F.data == "add_type_team")
async def fsm_add_type_team(callback: CallbackQuery, state: FSMContext):
    """Выбрали добавление неполной команды."""
    data = await state.get_data()
    
    await state.update_data(add_type="team")
    await state.set_state(AddElementFSM.waiting_teammates)
    
    await callback.message.edit_text(
        f"➕ <b>Добавление команды в турнир «{data['event_title']}»</b>\n\n"
        f"👥 Размер команды: {data['target_size']}\n\n"
        f"Введите Telegram username ваших тиммейтов через пробел или запятую.\n\n"
        f"<b>Примеры:</b>\n"
        f"<code>@user1 @user2 @user3</code>\n"
        f"<code>user1, user2, user3</code>\n\n"
        f"⚠️ <b>Важно:</b>\n"
        f"• Все участники должны быть зарегистрированы в боте\n"
        f"• Максимум {data['target_size'] - 1} тиммейтов (вы включены автоматически)\n"
        f"• Можно указать меньше — остальных найдут позже",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== FSM: Ввод тиммейтов ====================

@router.message(AddElementFSM.waiting_teammates)
async def fsm_teammates_input(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили список тиммейтов."""
    user_id = message.from_user.id
    data = await state.get_data()
    target_size = data["target_size"]
    
    # Парсим введённые username
    text = message.text.strip()
    # Разделяем по пробелам и запятым
    import re
    usernames = re.split(r'[,\s]+', text)
    usernames = [u.strip() for u in usernames if u.strip()]
    
    if not usernames:
        await message.answer(
            "❌ Вы не указали ни одного участника.\n\n"
            "Введите Telegram username тиммейтов:"
        )
        return
    
    # Проверяем количество
    if len(usernames) >= target_size:
        await message.answer(
            f"❌ Слишком много участников.\n\n"
            f"Размер команды: {target_size}\n"
            f"Вы указали: {len(usernames)} (+ вы = {len(usernames) + 1})\n\n"
            f"Максимум можно указать {target_size - 1} тиммейтов."
        )
        return
    
    # Ищем пользователей в базе
    found_users = await find_users_by_telegram_username(db, usernames)
    
    # Разделяем на найденных и не найденных
    found = []
    not_found = []
    
    for username, user_data in found_users.items():
        if user_data:
            # Проверяем, что пользователь не сам создатель
            if user_data["user_id"] == user_id:
                await message.answer(
                    f"❌ Вы не можете добавить себя в список тиммейтов (@{username}).\n"
                    f"Вы уже включены автоматически."
                )
                return
            
            # Проверяем, что профиль заполнен
            if not await db_queries.is_profile_complete(db, user_data["user_id"]):
                await message.answer(
                    f"❌ Пользователь @{username} не завершил регистрацию в боте.\n"
                    f"Попросите их использовать /start"
                )
                return
            
            # Проверяем, не состоит ли уже в элементе этого события
            has_element = await db_queries.check_user_has_element(db, data["event_id"], user_data["user_id"])
            if has_element:
                await message.answer(
                    f"❌ Пользователь @{username} уже добавлен в этот турнир."
                )
                return
            
            # Проверяем, не состоит ли в группе
            in_group = await db_queries.check_user_in_group(db, data["event_id"], user_data["user_id"])
            if in_group:
                await message.answer(
                    f"❌ Пользователь @{username} уже состоит в сформированной группе в этом турнире."
                )
                return
            
            found.append(user_data)
        else:
            not_found.append(username)
    
    # Если есть не найденные
    if not_found:
        not_found_list = ", ".join([f"@{u}" for u in not_found])
        await message.answer(
            f"❌ <b>Не найдены в боте:</b>\n{not_found_list}\n\n"
            f"Убедитесь, что:\n"
            f"• Username указан верно\n"
            f"• Пользователь зарегистрирован в боте (/start)\n\n"
            f"Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    # Формируем список участников (создатель + найденные)
    initial_members = [user_id] + [u["user_id"] for u in found]
    
    # Сохраняем и переходим к описанию
    await state.update_data(initial_members=initial_members)
    await state.set_state(AddElementFSM.waiting_description)
    
    # Формируем список для показа
    members_text = "• Вы\n"
    for u in found:
        gender_icon = "👨" if u.get("gender") == "male" else "👩" if u.get("gender") == "female" else "👤"
        members_text += f"• {gender_icon} {u.get('username', 'Без имени')} (@{u.get('telegram_username')}) — рейтинг: {u.get('rating', '?')}\n"
    
    await message.answer(
        f"✅ <b>Участники команды ({len(initial_members)}/{target_size}):</b>\n\n"
        f"{members_text}\n"
        f"🪑 Свободных мест: {target_size - len(initial_members)}\n\n"
        f"Введите описание/комментарий к вашей заявке\n"
        f"(например, требования к недостающим участникам)\n\n"
        f"Или отправьте <code>-</code> чтобы пропустить:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


# ==================== FSM: Описание ====================

@router.message(AddElementFSM.waiting_description)
async def fsm_element_description(message: Message, state: FSMContext, db: aiosqlite.Connection, bot: Bot):
    """Получили описание заявки."""
    description = message.text.strip()
    if description == "-":
        description = None
    elif len(description) > 300:
        await message.answer(
            "❌ Описание слишком длинное (максимум 300 символов).\n\n"
            "Введите описание или отправьте <code>-</code> чтобы пропустить:",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    await state.clear()
    
    event_id = data["event_id"]
    event_title = data["event_title"]
    target_size = data["target_size"]
    initial_members = data.get("initial_members", [message.from_user.id])
    user_id = message.from_user.id
    
    # Ещё раз проверяем, что пользователь не добавлен (на случай race condition)
    has_element = await db_queries.check_user_has_element(db, event_id, user_id)
    if has_element:
        await message.answer(
            "❌ Вы уже добавлены в этот турнир.",
            reply_markup=main_menu_kb()
        )
        return
    
    # Создаём элемент
    element_id = await db_queries.create_element(
        db,
        event_id=event_id,
        creator_id=user_id,
        target_size=target_size,
        initial_members=initial_members,
        description=description
    )
    
    # Логируем
    await db_queries.create_log(
        db,
        "element_created",
        f"element_id={element_id}, event_id={event_id}, creator_id={user_id}, members={len(initial_members)}"
    )
    
    # Получаем всех участников для отображения
    members = await db_queries.get_element_members(db, element_id)
    members_text = "\n".join([f"• {format_member_info(m)}" for m in members])
    
    # Уведомляем добавленных участников (кроме создателя)
    for member_id in initial_members:
        if member_id != user_id:
            try:
                creator = await db_queries.get_user(db, user_id)
                await bot.send_message(
                    member_id,
                    f"👥 <b>Вы добавлены в команду!</b>\n\n"
                    f"📌 Турнир: {event_title}\n"
                    f"👤 Вас добавил: {creator.get('username', 'Участник')}\n"
                    f"📦 Заявка: #{element_id}\n\n"
                    f"Посмотреть детали: /my_elements {event_id}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    
    await message.answer(
        f"✅ <b>{'Команда' if len(initial_members) > 1 else 'Вы'} добавлена в турнир!</b>\n\n"
        f"📌 Турнир: {event_title}\n"
        f"📦 Заявка: #{element_id}\n"
        f"📝 Описание: {description or '—'}\n\n"
        f"👤 Участники ({len(initial_members)}/{target_size}):\n"
        f"{members_text}\n\n"
        f"🪑 Свободных мест: {target_size - len(initial_members)}\n\n"
        f"Теперь другие участники могут найти вас и отправить запрос на присоединение.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ==================== Остальные callbacks без изменений ====================

@router.callback_query(F.data.startswith("my_elements:"))
async def cb_my_elements(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Мои заявки»."""
    event_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Проверяем существование события
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    # Получаем элементы пользователя
    elements = await db_queries.get_user_elements(db, event_id, user_id)
    
    await callback.message.edit_text(
        f"📦 <b>Мои заявки в турнире «{event['title']}»</b>",
        reply_markup=my_elements_kb(elements, event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_element:"))
async def cb_manage_element(callback: CallbackQuery, db: aiosqlite.Connection):
    """Управление своими заявками."""
    element_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем элемент
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Проверяем, что пользователь — создатель или участник
    is_member = await db_queries.check_user_in_element(db, element_id, user_id)
    if not is_member and element["creator_id"] != user_id:
        await callback.answer("❌ Это не ваша заявка", show_alert=True)
        return
    
    event_id = element["event_id"]
    
    # Получаем участников
    members = await db_queries.get_element_members(db, element_id)
    
    # Получаем количество ожидающих запросов
    pending_requests = await db_queries.get_pending_requests_for_element(db, element_id)
    
    # Формируем информацию
    target_size = element["target_size"]
    spots_left = target_size - len(members)
    description = element.get("description") or "—"
    
    members_text = "\n".join([f"• {format_member_info(m)}" for m in members]) if members else "Никого"
    
    # Рассчитываем средний рейтинг
    if members:
        ratings = [m["rating"] for m in members if m.get("rating") is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        avg_rating_text = f"\n⭐ Средний рейтинг: {avg_rating:.0f}"
    else:
        avg_rating_text = ""
    
    is_creator = element["creator_id"] == user_id
    creator_text = " (вы создатель)" if is_creator else ""
    
    await callback.message.edit_text(
        f"⚙️ <b>Заявка #{element_id}</b>{creator_text}\n\n"
        f"📝 Описание: {description}\n"
        f"👥 Участники ({len(members)}/{target_size}):\n{members_text}"
        f"{avg_rating_text}\n"
        f"🪑 Свободных мест: {spots_left}\n"
        f"📩 Входящих запросов: {len(pending_requests)}",
        reply_markup=manage_element_kb(element_id, event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("element_members:"))
async def cb_element_members(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать участников заявки."""
    element_id = int(callback.data.split(":")[1])
    
    # Получаем элемент
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Получаем участников
    members = await db_queries.get_element_members(db, element_id)
    
    if not members:
        await callback.answer("📭 В заявке пока нет участников", show_alert=True)
        return
    
    members_text = "\n".join([f"• {format_member_info(m)}" for m in members])
    
    await callback.message.edit_text(
        f"👥 <b>Участники заявки #{element_id}</b>\n\n"
        f"{members_text}",
        reply_markup=manage_element_kb(element_id, element["event_id"]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_element:"))
async def cb_delete_element(callback: CallbackQuery, db: aiosqlite.Connection):
    """Удаление заявки — показать подтверждение."""
    element_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем элемент
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Проверяем, что пользователь — создатель
    if element["creator_id"] != user_id:
        await callback.answer("❌ Только создатель может удалить заявку", show_alert=True)
        return
    
    # Получаем количество участников
    members = await db_queries.get_element_members(db, element_id)
    pending_requests = await db_queries.get_pending_requests_for_element(db, element_id)
    
    await callback.message.edit_text(
        f"🗑 <b>Удаление заявки #{element_id}</b>\n\n"
        f"⚠️ <b>Внимание!</b>\n"
        f"Будут удалены:\n"
        f"• Заявка и все ее данные\n"
        f"• Участники: {len(members)}\n"
        f"• Ожидающие запросы: {len(pending_requests)}\n\n"
        f"Вы уверены?",
        reply_markup=confirm_kb("delete_element", element_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:delete_element:"))
async def cb_confirm_delete_element(callback: CallbackQuery, db: aiosqlite.Connection, bot: Bot):
    """Подтверждение удаления заявки."""
    element_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    # Получаем элемент
    element = await db_queries.get_element(db, element_id)
    if not element:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    # Проверяем права
    if element["creator_id"] != user_id:
        await callback.answer("❌ Только создатель может удалить заявку", show_alert=True)
        return
    
    event_id = element["event_id"]
    
    # Получаем участников для уведомления
    members = await db_queries.get_element_members(db, element_id)
    event = await db_queries.get_event(db, event_id)
    
    # Удаляем элемент
    success = await db_queries.delete_element(db, element_id, user_id)
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "element_deleted",
            f"element_id={element_id}, event_id={event_id}, creator_id={user_id}"
        )
        
        # Уведомляем других участников (кроме создателя)
        for member in members:
            if member["user_id"] != user_id:
                try:
                    await bot.send_message(
                        member["user_id"],
                        f"❌ <b>Заявка удалёна</b>\n\n"
                        f"Заявка #{element_id} в турнире «{event['title']}» был удалён создателем.\n\n"
                        f"Вы можете найти другие заявки для присоединения.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        
        await callback.message.edit_text(
            f"✅ <b>Заявка #{element_id} удалёна</b>\n\n"
            f"Все участники были уведомлены.",
            reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == user_id)),
            parse_mode="HTML"
        )
        await callback.answer("Заявка удалёна")
    else:
        await callback.answer("❌ Не удалось удалить заявку", show_alert=True)


@router.callback_query(F.data == "back_my_elements")
async def cb_back_my_elements(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Возврат к списку своих заявок."""
    # Пытаемся получить event_id из state или показываем все элементы
    data = await state.get_data()
    event_id = data.get("last_event_id")
    user_id = callback.from_user.id
    
    if event_id:
        event = await db_queries.get_event(db, event_id)
        if event:
            elements = await db_queries.get_user_elements(db, event_id, user_id)
            await callback.message.edit_text(
                f"📦 <b>Мои заявки в турнире «{event['title']}»</b>",
                reply_markup=my_elements_kb(elements, event_id),
                parse_mode="HTML"
            )
            await callback.answer()
            return
    
    # Если event_id неизвестен, показываем главное меню
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
