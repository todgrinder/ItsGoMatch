"""
Обработчики: /create_event, /list_events, /close_event.
"""

from datetime import datetime, date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

from keyboards.inline import (
    event_type_kb,
    team_size_kb,
    events_list_kb,
    event_menu_kb,
    main_menu_kb,
    cancel_kb,
    confirm_kb,
    date_picker_kb,
    date_confirm_kb,
    edit_event_kb
)
from database import queries as db_queries

router = Router()


# ==================== FSM для создания события ====================

class CreateEventFSM(StatesGroup):
    waiting_title = State()
    waiting_type = State()
    waiting_team_size = State()
    waiting_date = State()
    waiting_description = State()

class EditEventFSM(StatesGroup):
    waiting_field_choice = State()
    waiting_new_title = State()
    waiting_new_description = State()
    waiting_new_date = State()

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


def get_days_until(date_str: str) -> str:
    """Получить текст о количестве дней до события (компактный формат)."""
    if not date_str:
        return ""
    try:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (event_date - today).days
        
        if delta == 0:
            return "Сегодня"
        elif delta == 1:
            return "Завтра"
        elif delta < 0:
            return "Прошёл"
        elif delta <= 7:
            return f"Через {delta}д"
        elif delta <= 30:
            return f"{delta}д"
        else:
            # Для дальних дат показываем саму дату
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return f"{dt.day:02d}.{dt.month:02d}"
    except:
        return ""


def format_event_info(event: dict, include_stats: bool = False) -> str:
    """Форматировать информацию о событии."""
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    status_label = "🟢 Открыт" if event["status"] == "open" else "🔴 Закрыт"
    description = event.get("description") or "—"
    
    # Дата проведения
    event_date = event.get("event_date")
    date_text = format_date_ru(event_date)
    days_until = get_days_until(event_date)
    date_line = f"📅 Дата: {date_text}"
    if days_until:
        date_line += f" ({days_until})"
    
    text = (
        f"📌 <b>{event['title']}</b>\n\n"
        f"🎯 Тип: {type_label}\n"
        f"{date_line}\n"
        f"📝 Описание: {description}\n"
        f"📊 Статус: {status_label}\n"
        f"🆔 ID: <code>{event['event_id']}</code>"
    )
    
    return text


async def show_event_details(callback: CallbackQuery, db: aiosqlite.Connection, event_id: int, user_id: int):
    """Показать детали события."""
    event = await db_queries.get_event(db, event_id)
    
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    is_owner = event["owner_id"] == user_id
    
    # Получаем статистику
    stats = await db_queries.get_event_statistics(db, event_id)
    
    type_label = "👥 Пары" if event["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({event.get('team_size', '?')} чел.)"
    status_label = "🟢 Открыт" if event["status"] == "open" else "🔴 Закрыт"
    description = event.get("description") or "—"
    owner_text = " (вы владелец)" if is_owner else ""
    
    # Дата проведения
    event_date = event.get("event_date")
    date_text = format_date_ru(event_date)
    days_until = get_days_until(event_date)
    date_line = f"📅 Дата: {date_text}"
    if days_until:
        date_line += f" <b>{days_until}</b>"
    
    text = (
        f"📌 <b>{event['title']}</b>{owner_text}\n\n"
        f"🎯 Тип: {type_label}\n"
        f"{date_line}\n"
        f"📝 Описание: {description}\n"
        f"📊 Статус: {status_label}\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n"
        f"• Участников в группах: {stats['users_in_groups']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n\n"
        f"🆔 ID: <code>{event_id}</code>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=event_menu_kb(event_id, is_owner=is_owner),
        parse_mode="HTML"
    )


# ==================== КОМАНДЫ ====================

@router.message(Command("create_event"))
async def cmd_create_event(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Начать создание турнира."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    await state.set_state(CreateEventFSM.waiting_title)
    await message.answer(
        "🏆 <b>Создание турнира</b>\n\n"
        "Шаг 1/5: Введите название турнира:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )


@router.message(Command("list_events"))
async def cmd_list_events(message: Message, db: aiosqlite.Connection):
    """Показать список открытых турниров."""
    user_id = message.from_user.id
    
    # Проверяем регистрацию
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    events = await db_queries.list_open_events(db)
    
    if not events:
        await message.answer(
            "📋 <b>Открытые турниры</b>\n\n"
            "Пока нет открытых турниров.\n"
            "Создайте первый с помощью /create_event",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return
    
    # Добавляем информацию о дате к каждому событию
    for event in events:
        event_date = event.get("event_date")
        if event_date:
            days_until = get_days_until(event_date)
            event["date_badge"] = days_until
        else:
            event["date_badge"] = ""
    
    await message.answer(
        f"📋 <b>Открытые турниры ({len(events)})</b>\n\n"
        "Выберите турнир для просмотра:",
        reply_markup=events_list_kb(events, action="view"),
        parse_mode="HTML"
    )


@router.message(Command("close_event"))
async def cmd_close_event(message: Message, db: aiosqlite.Connection):
    """Закрыть турнир: /close_event 123."""
    user_id = message.from_user.id
    
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "🔒 <b>Закрытие турнира</b>\n\n"
            "Формат: /close_event &lt;event_id&gt;\n"
            "Пример: <code>/close_event 123</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        event_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ ID турнира должен быть числом.")
        return
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await message.answer("❌ Турнир не найден.")
        return
    
    if event["owner_id"] != user_id:
        await message.answer("❌ Вы не являетесь владельцем этого турнира.")
        return
    
    if event["status"] == "closed":
        await message.answer("❌ Этот турнир уже закрыт.")
        return
    
    success = await db_queries.close_event(db, event_id, user_id)
    
    if success:
        await db_queries.create_log(db, "event_closed", f"event_id={event_id}, owner_id={user_id}")
        
        await message.answer(
            f"✅ Турнир «{event['title']}» закрыт.\n\n"
            f"Новые элементы и запросы больше не принимаются."
        )
    else:
        await message.answer("❌ Не удалось закрыть турнир.")


@router.message(Command("my_events"))
async def cmd_my_events(message: Message, db: aiosqlite.Connection):
    """Показать турниры пользователя."""
    user_id = message.from_user.id
    
    if not await db_queries.is_profile_complete(db, user_id):
        await message.answer(
            "❌ Сначала завершите регистрацию.\n"
            "Используйте /start"
        )
        return
    
    events = await db_queries.list_user_events(db, user_id)
    
    if not events:
        await message.answer(
            "📋 <b>Мои турниры</b>\n\n"
            "У вас пока нет созданных турниров.\n"
            "Создайте первый с помощью /create_event",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        return
    
    # Добавляем информацию о дате
    for event in events:
        event_date = event.get("event_date")
        if event_date:
            days_until = get_days_until(event_date)
            event["date_badge"] = days_until
        else:
            event["date_badge"] = ""
    
    await message.answer(
        f"📋 <b>Мои турниры ({len(events)})</b>\n\n"
        "Выберите турнир для управления:",
        reply_markup=events_list_kb(events, action="manage"),
        parse_mode="HTML"
    )


# ==================== CALLBACKS ====================

@router.callback_query(F.data == "create_event")
async def cb_create_event(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Кнопка «Создать турнир»."""
    user_id = callback.from_user.id
    
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    await state.set_state(CreateEventFSM.waiting_title)
    await callback.message.edit_text(
        "🏆 <b>Создание турнира</b>\n\n"
        "Шаг 1/5: Введите название турнира:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search_events")
async def cb_search_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Поиск турниров»."""
    user_id = callback.from_user.id
    
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    events = await db_queries.list_open_events(db)
    
    if not events:
        await callback.message.edit_text(
            "🔎 <b>Поиск турниров</b>\n\n"
            "Пока нет открытых турниров.\n"
            "Создайте первый!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        # Добавляем информацию о дате
        for event in events:
            event_date = event.get("event_date")
            if event_date:
                days_until = get_days_until(event_date)
                event["date_badge"] = days_until
            else:
                event["date_badge"] = ""
        
        await callback.message.edit_text(
            f"🔎 <b>Открытые турниры ({len(events)})</b>\n\n"
            "Выберите турнир:",
            reply_markup=events_list_kb(events, action="view"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "my_events")
async def cb_my_events(callback: CallbackQuery, db: aiosqlite.Connection):
    """Кнопка «Мои турниры»."""
    user_id = callback.from_user.id
    
    if not await db_queries.is_profile_complete(db, user_id):
        await callback.answer("❌ Сначала завершите регистрацию (/start)", show_alert=True)
        return
    
    events = await db_queries.list_user_events(db, user_id)
    
    if not events:
        await callback.message.edit_text(
            "📋 <b>Мои турниры</b>\n\n"
            "У вас пока нет созданных турниров.\n"
            "Создайте первый!",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        # Добавляем информацию о дате
        for event in events:
            event_date = event.get("event_date")
            if event_date:
                days_until = get_days_until(event_date)
                event["date_badge"] = days_until
            else:
                event["date_badge"] = ""
        
        await callback.message.edit_text(
            f"📋 <b>Мои турниры ({len(events)})</b>\n\n"
            "Выберите турнир для управления:",
            reply_markup=events_list_kb(events, action="manage"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("event:view:"))
async def cb_view_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Просмотр конкретного турнира."""
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    await show_event_details(callback, db, event_id, user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("event:manage:"))
async def cb_manage_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Управление турниром (для владельца)."""
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    await show_event_details(callback, db, event_id, user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("close_event:"))
async def cb_close_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Закрыть турнир (кнопка) — показать подтверждение."""
    event_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    if event["owner_id"] != user_id:
        await callback.answer("❌ Вы не являетесь владельцем этого турнира", show_alert=True)
        return
    
    if event["status"] == "closed":
        await callback.answer("❌ Этот турнир уже закрыт", show_alert=True)
        return
    
    stats = await db_queries.get_event_statistics(db, event_id)
    
    await callback.message.edit_text(
        f"🔒 <b>Закрытие турнира «{event['title']}»</b>\n\n"
        f"⚠️ <b>Внимание!</b>\n"
        f"После закрытия новые элементы и запросы не будут приниматься.\n\n"
        f"📊 Текущая статистика:\n"
        f"• Активных элементов: {stats['active_elements']}\n"
        f"• Ожидающих запросов: {stats['pending_requests']}\n"
        f"• Сформированных групп: {stats['total_groups']}\n\n"
        f"Вы уверены?",
        reply_markup=confirm_kb("close_event", event_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:close_event:"))
async def cb_confirm_close_event(callback: CallbackQuery, db: aiosqlite.Connection):
    """Подтверждение закрытия турнира."""
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    
    success = await db_queries.close_event(db, event_id, user_id)
    
    if success:
        event = await db_queries.get_event(db, event_id)
        await db_queries.create_log(db, "event_closed", f"event_id={event_id}, owner_id={user_id}")
        
        await callback.message.edit_text(
            f"✅ <b>Турнир «{event['title']}» закрыт</b>\n\n"
            f"Новые элементы и запросы больше не принимаются.\n"
            f"Уже сформированные группы сохранены.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
        await callback.answer("Турнир закрыт")
    else:
        await callback.answer("❌ Не удалось закрыть турнир", show_alert=True)


@router.callback_query(F.data.startswith("event_groups:"))
async def cb_event_groups(callback: CallbackQuery, db: aiosqlite.Connection):
    """Показать сформированные группы в турнире."""
    event_id = int(callback.data.split(":")[1])
    
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    groups = await db_queries.get_event_groups(db, event_id)
    
    if not groups:
        await callback.answer("📭 Пока нет сформированных групп", show_alert=True)
        return
    
    groups_text = ""
    for i, group in enumerate(groups[:10], 1):
        members = group.get("members", [])
        members_names = ", ".join([m.get("username", "?") for m in members])
        avg_rating = group.get("rating_avg", 0)
        groups_text += f"\n{i}. ⭐ {avg_rating:.0f} — {members_names}"
    
    total = len(groups)
    shown = min(total, 10)
    more_text = f"\n\n... и ещё {total - shown}" if total > shown else ""
    
    await callback.message.edit_text(
        f"✅ <b>Сформированные группы</b>\n"
        f"Турнир: {event['title']}\n"
        f"Всего групп: {total}\n"
        f"{groups_text}{more_text}",
        reply_markup=event_menu_kb(event_id, is_owner=(event["owner_id"] == callback.from_user.id)),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_event:"))
async def cb_edit_event(callback: CallbackQuery):
    """Редактирование турнира (пока не реализовано)."""
    await callback.answer("✏️ Редактирование турнира пока недоступно", show_alert=True)


# ==================== FSM HANDLERS ====================

@router.message(CreateEventFSM.waiting_title)
async def fsm_event_title(message: Message, state: FSMContext):
    """Получили название турнира."""
    title = message.text.strip()
    
    if not title:
        await message.answer(
            "❌ Название не может быть пустым.\n\n"
            "Введите название турнира:"
        )
        return
    
    if len(title) > 100:
        await message.answer(
            "❌ Название слишком длинное (максимум 100 символов).\n\n"
            "Введите название турнира:"
        )
        return
    
    await state.update_data(title=title)
    await state.set_state(CreateEventFSM.waiting_type)
    
    await message.answer(
        f"✅ Название: <b>{title}</b>\n\n"
        "Шаг 2/5: Выберите тип турнира:",
        reply_markup=event_type_kb(),
        parse_mode="HTML"
    )


@router.callback_query(CreateEventFSM.waiting_type, F.data.startswith("event_type:"))
async def fsm_event_type(callback: CallbackQuery, state: FSMContext):
    """Выбрали тип турнира."""
    event_type = callback.data.split(":")[1]
    await state.update_data(type=event_type)
    
    if event_type == "team":
        await state.set_state(CreateEventFSM.waiting_team_size)
        await callback.message.edit_text(
            "Шаг 3/5: Выберите размер команды:",
            reply_markup=team_size_kb()
        )
    else:
        await state.update_data(team_size=2)
        await state.set_state(CreateEventFSM.waiting_date)
        
        # Показываем календарь
        today = date.today()
        await callback.message.edit_text(
            "✅ Тип: <b>👥 Пары (2 человека)</b>\n\n"
            "Шаг 3/5: Выберите дату проведения турнира:\n\n"
            "<i>Турнир автоматически закроется на следующий день после указанной даты</i>",
            reply_markup=date_picker_kb(today.year, today.month),
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_team_size, F.data.startswith("team_size:"))
async def fsm_team_size(callback: CallbackQuery, state: FSMContext):
    """Выбрали размер команды."""
    team_size = int(callback.data.split(":")[1])
    await state.update_data(team_size=team_size)
    await state.set_state(CreateEventFSM.waiting_date)
    
    # Показываем календарь
    today = date.today()
    await callback.message.edit_text(
        f"✅ Размер команды: <b>{team_size} человек</b>\n\n"
        "Шаг 4/5: Выберите дату проведения турнира:\n\n"
        "<i>Турнир автоматически закроется на следующий день после указанной даты</i>",
        reply_markup=date_picker_kb(today.year, today.month),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== КАЛЕНДАРЬ ====================

@router.callback_query(CreateEventFSM.waiting_date, F.data.startswith("cal_nav:"))
async def fsm_calendar_nav(callback: CallbackQuery, state: FSMContext):
    """Навигация по календарю."""
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)
    
    await callback.message.edit_reply_markup(
        reply_markup=date_picker_kb(year, month)
    )
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_date, F.data.startswith("cal_select:"))
async def fsm_calendar_select(callback: CallbackQuery, state: FSMContext):
    """Выбрали дату."""
    date_str = callback.data.split(":")[1]
    
    await state.update_data(event_date=date_str)
    
    date_formatted = format_date_ru(date_str)
    
    await callback.message.edit_text(
        f"📅 Выбранная дата: <b>{date_formatted}</b>\n\n"
        "Подтвердите выбор:",
        reply_markup=date_confirm_kb(date_str),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_date, F.data.startswith("cal_confirm:"))
async def fsm_calendar_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтвердили дату."""
    date_str = callback.data.split(":")[1]
    await state.update_data(event_date=date_str)
    await state.set_state(CreateEventFSM.waiting_description)
    
    date_formatted = format_date_ru(date_str)
    
    await callback.message.edit_text(
        f"✅ Дата: <b>{date_formatted}</b>\n\n"
        "Шаг 5/5: Введите описание турнира\n"
        "(или отправьте <code>-</code> чтобы пропустить):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_date, F.data == "cal_change")
async def fsm_calendar_change(callback: CallbackQuery, state: FSMContext):
    """Изменить дату."""
    today = date.today()
    await callback.message.edit_text(
        "📅 Выберите дату проведения турнира:",
        reply_markup=date_picker_kb(today.year, today.month)
    )
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_date, F.data == "cal_skip")
async def fsm_calendar_skip(callback: CallbackQuery, state: FSMContext):
    """Пропустить выбор даты."""
    await state.update_data(event_date=None)
    await state.set_state(CreateEventFSM.waiting_description)
    
    await callback.message.edit_text(
        "⏭ Дата не указана\n\n"
        "Шаг 5/5: Введите описание турнира\n"
        "(или отправьте <code>-</code> чтобы пропустить):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CreateEventFSM.waiting_date, F.data == "cal_ignore")
async def fsm_calendar_ignore(callback: CallbackQuery):
    """Игнорировать клик на неактивную кнопку календаря."""
    await callback.answer()


@router.message(CreateEventFSM.waiting_description)
async def fsm_event_description(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили описание, создаём турнир."""
    description = message.text.strip()
    if description == "-":
        description = None
    elif len(description) > 500:
        await message.answer(
            "❌ Описание слишком длинное (максимум 500 символов).\n\n"
            "Введите описание или отправьте <code>-</code> чтобы пропустить:",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    await state.clear()
    
    user_id = message.from_user.id
    
    # Создаём событие в БД
    event_id = await db_queries.create_event(
        db,
        owner_id=user_id,
        title=data["title"],
        event_type=data["type"],
        team_size=data["team_size"],
        description=description,
        event_date=data.get("event_date")
    )
    
    # Логируем
    await db_queries.create_log(
        db,
        "event_created",
        f"event_id={event_id}, owner_id={user_id}, title={data['title']}, date={data.get('event_date')}"
    )
    
    type_label = "👥 Пары" if data["type"] == "pair" else f"👨‍👩‍👧‍👦 Команды ({data['team_size']} чел.)"
    
    event_date = data.get("event_date")
    date_text = format_date_ru(event_date) if event_date else "Не указана"
    auto_close_text = "\n\n<i>⏰ Турнир автоматически закроется на следующий день после указанной даты</i>" if event_date else ""
    
    await message.answer(
        f"🎉 <b>Турнир создан!</b>\n\n"
        f"📌 Название: {data['title']}\n"
        f"🎯 Тип: {type_label}\n"
        f"📅 Дата: {date_text}\n"
        f"📝 Описание: {description or '—'}\n\n"
        f"🆔 ID турнира: <code>{event_id}</code>"
        f"{auto_close_text}",
        reply_markup=event_menu_kb(event_id, is_owner=True),
        parse_mode="HTML"
    )

# ==================== РЕДАКТИРОВАНИЕ ТУРНИРА ====================

@router.callback_query(F.data.startswith("edit_event:"))
async def cb_edit_event(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Начать редактирование турнира."""
    event_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем событие
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    # Проверяем, что пользователь — владелец
    if event["owner_id"] != user_id:
        await callback.answer("❌ Только владелец может редактировать турнир", show_alert=True)
        return
    
    # Сохраняем event_id в state
    await state.update_data(event_id=event_id, event_title=event["title"])
    await state.set_state(EditEventFSM.waiting_field_choice)
    
    # Текущие данные
    event_date = event.get("event_date")
    date_text = format_date_ru(event_date) if event_date else "Не указана"
    description = event.get("description") or "Не указано"
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование турнира</b>\n\n"
        f"📌 <b>Текущие данные:</b>\n\n"
        f"<b>Название:</b> {event['title']}\n"
        f"<b>Дата:</b> {date_text}\n"
        f"<b>Описание:</b> {description}\n\n"
        f"Что вы хотите изменить?",
        reply_markup=edit_event_kb(event_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== ВЫБОР ПОЛЯ ДЛЯ РЕДАКТИРОВАНИЯ ====================

@router.callback_query(EditEventFSM.waiting_field_choice, F.data == "edit_event_title")
async def cb_edit_event_title(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Редактировать название."""
    data = await state.get_data()
    event_id = data["event_id"]
    
    event = await db_queries.get_event(db, event_id)
    
    await state.set_state(EditEventFSM.waiting_new_title)
    
    await callback.message.edit_text(
        f"✏️ <b>Изменение названия</b>\n\n"
        f"Текущее название: <b>{event['title']}</b>\n\n"
        f"Введите новое название турнира:",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(EditEventFSM.waiting_field_choice, F.data == "edit_event_date")
async def cb_edit_event_date(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Редактировать дату."""
    data = await state.get_data()
    event_id = data["event_id"]
    
    event = await db_queries.get_event(db, event_id)
    event_date = event.get("event_date")
    date_text = format_date_ru(event_date) if event_date else "Не указана"
    
    await state.set_state(EditEventFSM.waiting_new_date)
    
    # Показываем календарь
    today = date.today()
    
    await callback.message.edit_text(
        f"✏️ <b>Изменение даты</b>\n\n"
        f"Текущая дата: <b>{date_text}</b>\n\n"
        f"Выберите новую дату проведения турнира:\n\n"
        f"<i>Турнир автоматически закроется на следующий день после указанной даты</i>",
        reply_markup=date_picker_kb(today.year, today.month),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(EditEventFSM.waiting_field_choice, F.data == "edit_event_description")
async def cb_edit_event_description(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Редактировать описание."""
    data = await state.get_data()
    event_id = data["event_id"]
    
    event = await db_queries.get_event(db, event_id)
    description = event.get("description") or "Не указано"
    
    await state.set_state(EditEventFSM.waiting_new_description)
    
    await callback.message.edit_text(
        f"✏️ <b>Изменение описания</b>\n\n"
        f"Текущее описание:\n{description}\n\n"
        f"Введите новое описание турнира\n"
        f"(или отправьте <code>-</code> чтобы удалить описание):",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== FSM: ОБРАБОТКА НОВЫХ ЗНАЧЕНИЙ ====================

@router.message(EditEventFSM.waiting_new_title)
async def fsm_edit_title(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили новое название."""
    new_title = message.text.strip()
    
    if not new_title:
        await message.answer(
            "❌ Название не может быть пустым.\n\n"
            "Введите новое название:"
        )
        return
    
    if len(new_title) > 100:
        await message.answer(
            "❌ Название слишком длинное (максимум 100 символов).\n\n"
            "Введите новое название:"
        )
        return
    
    data = await state.get_data()
    await state.clear()
    
    event_id = data["event_id"]
    user_id = message.from_user.id
    old_title = data["event_title"]
    
    # Обновляем в БД
    success = await db_queries.update_event(
        db,
        event_id=event_id,
        owner_id=user_id,
        title=new_title
    )
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "event_title_updated",
            f"event_id={event_id}, old_title={old_title}, new_title={new_title}"
        )
        
        await message.answer(
            f"✅ <b>Название обновлено</b>\n\n"
            f"Было: {old_title}\n"
            f"Стало: {new_title}",
            reply_markup=event_menu_kb(event_id, is_owner=True),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось обновить название.",
            reply_markup=event_menu_kb(event_id, is_owner=True)
        )


@router.message(EditEventFSM.waiting_new_description)
async def fsm_edit_description(message: Message, state: FSMContext, db: aiosqlite.Connection):
    """Получили новое описание."""
    new_description = message.text.strip()
    
    if new_description == "-":
        new_description = None
    elif len(new_description) > 500:
        await message.answer(
            "❌ Описание слишком длинное (максимум 500 символов).\n\n"
            "Введите новое описание или отправьте <code>-</code> чтобы удалить:",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    await state.clear()
    
    event_id = data["event_id"]
    user_id = message.from_user.id
    
    # Обновляем в БД
    success = await db_queries.update_event(
        db,
        event_id=event_id,
        owner_id=user_id,
        description=new_description
    )
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "event_description_updated",
            f"event_id={event_id}"
        )
        
        desc_text = new_description or "Удалено"
        
        await message.answer(
            f"✅ <b>Описание обновлено</b>\n\n"
            f"Новое описание:\n{desc_text}",
            reply_markup=event_menu_kb(event_id, is_owner=True),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось обновить описание.",
            reply_markup=event_menu_kb(event_id, is_owner=True)
        )


# ==================== FSM: ОБРАБОТКА НОВОЙ ДАТЫ ====================

@router.callback_query(EditEventFSM.waiting_new_date, F.data.startswith("cal_nav:"))
async def fsm_edit_date_nav(callback: CallbackQuery, state: FSMContext):
    """Навигация по календарю при редактировании."""
    _, year, month = callback.data.split(":")
    year, month = int(year), int(month)
    
    await callback.message.edit_reply_markup(
        reply_markup=date_picker_kb(year, month)
    )
    await callback.answer()


@router.callback_query(EditEventFSM.waiting_new_date, F.data.startswith("cal_select:"))
async def fsm_edit_date_select(callback: CallbackQuery, state: FSMContext):
    """Выбрали новую дату."""
    date_str = callback.data.split(":")[1]
    
    await state.update_data(new_date=date_str)
    
    date_formatted = format_date_ru(date_str)
    
    await callback.message.edit_text(
        f"📅 Выбранная дата: <b>{date_formatted}</b>\n\n"
        "Подтвердите выбор:",
        reply_markup=date_confirm_kb(date_str),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(EditEventFSM.waiting_new_date, F.data.startswith("cal_confirm:"))
async def fsm_edit_date_confirm(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Подтвердили новую дату."""
    date_str = callback.data.split(":")[1]
    
    data = await state.get_data()
    await state.clear()
    
    event_id = data["event_id"]
    user_id = callback.from_user.id
    
    # Получаем старую дату для логирования
    event = await db_queries.get_event(db, event_id)
    old_date = event.get("event_date")
    old_date_text = format_date_ru(old_date) if old_date else "Не указана"
    
    # Обновляем в БД
    success = await db_queries.update_event(
        db,
        event_id=event_id,
        owner_id=user_id,
        event_date=date_str
    )
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "event_date_updated",
            f"event_id={event_id}, old_date={old_date}, new_date={date_str}"
        )
        
        date_formatted = format_date_ru(date_str)
        
        await callback.message.edit_text(
            f"✅ <b>Дата обновлена</b>\n\n"
            f"Было: {old_date_text}\n"
            f"Стало: {date_formatted}",
            reply_markup=event_menu_kb(event_id, is_owner=True),
            parse_mode="HTML"
        )
        await callback.answer("Дата обновлена")
    else:
        await callback.answer("❌ Не удалось обновить дату", show_alert=True)


@router.callback_query(EditEventFSM.waiting_new_date, F.data == "cal_change")
async def fsm_edit_date_change(callback: CallbackQuery, state: FSMContext):
    """Изменить дату (вернуться к календарю)."""
    today = date.today()
    await callback.message.edit_text(
        "📅 Выберите новую дату проведения турнира:",
        reply_markup=date_picker_kb(today.year, today.month)
    )
    await callback.answer()


@router.callback_query(EditEventFSM.waiting_new_date, F.data == "cal_skip")
async def fsm_edit_date_skip(callback: CallbackQuery, state: FSMContext, db: aiosqlite.Connection):
    """Удалить дату (установить NULL)."""
    data = await state.get_data()
    await state.clear()
    
    event_id = data["event_id"]
    user_id = callback.from_user.id
    
    # Получаем старую дату
    event = await db_queries.get_event(db, event_id)
    old_date = event.get("event_date")
    old_date_text = format_date_ru(old_date) if old_date else "Не указана"
    
    # Обновляем в БД (устанавливаем NULL)
    success = await db_queries.update_event(
        db,
        event_id=event_id,
        owner_id=user_id,
        event_date=None
    )
    
    if success:
        # Логируем
        await db_queries.create_log(
            db,
            "event_date_removed",
            f"event_id={event_id}, old_date={old_date}"
        )
        
        await callback.message.edit_text(
            f"✅ <b>Дата удалена</b>\n\n"
            f"Было: {old_date_text}\n"
            f"Стало: Не указана",
            reply_markup=event_menu_kb(event_id, is_owner=True),
            parse_mode="HTML"
        )
        await callback.answer("Дата удалена")
    else:
        await callback.answer("❌ Не удалось удалить дату", show_alert=True)


@router.callback_query(EditEventFSM.waiting_new_date, F.data == "cal_ignore")
async def fsm_edit_date_ignore(callback: CallbackQuery):
    """Игнорировать клик на неактивную кнопку календаря."""
    await callback.answer()


# ==================== ВОЗВРАТ К РЕДАКТИРОВАНИЮ ====================

@router.callback_query(F.data.startswith("back_edit_event:"))
async def cb_back_edit_event(callback: CallbackQuery, db: aiosqlite.Connection, state: FSMContext):
    """Вернуться к выбору поля для редактирования."""
    event_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Получаем событие
    event = await db_queries.get_event(db, event_id)
    if not event:
        await callback.answer("❌ Турнир не найден", show_alert=True)
        return
    
    # Проверяем, что пользователь — владелец
    if event["owner_id"] != user_id:
        await callback.answer("❌ Только владелец может редактировать турнир", show_alert=True)
        return
    
    # Сохраняем event_id в state
    await state.update_data(event_id=event_id, event_title=event["title"])
    await state.set_state(EditEventFSM.waiting_field_choice)
    
    # Текущие данные
    event_date = event.get("event_date")
    date_text = format_date_ru(event_date) if event_date else "Не указана"
    description = event.get("description") or "Не указано"
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование турнира</b>\n\n"
        f"📌 <b>Текущие данные:</b>\n\n"
        f"<b>Название:</b> {event['title']}\n"
        f"<b>Дата:</b> {date_text}\n"
        f"<b>Описание:</b> {description}\n\n"
        f"Что вы хотите изменить?",
        reply_markup=edit_event_kb(event_id),
        parse_mode="HTML"
    )
    await callback.answer()