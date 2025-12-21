"""
Inline‑клавиатуры для бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import GENDER_MALE, GENDER_FEMALE, GENDER_LABELS


# ==================== ГЛАВНОЕ МЕНЮ ====================

def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню после /start."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Мои турниры", callback_data="my_events"),
        InlineKeyboardButton(text="🔎 Поиск турниров", callback_data="search_events")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Создать турнир", callback_data="create_event")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="help")
    )
    return builder.as_markup()


# ==================== ВЫБОР ПОЛА ====================

def gender_kb() -> InlineKeyboardMarkup:
    """Выбор пола."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=GENDER_LABELS[GENDER_MALE], callback_data=f"set_gender:{GENDER_MALE}"),
        InlineKeyboardButton(text=GENDER_LABELS[GENDER_FEMALE], callback_data=f"set_gender:{GENDER_FEMALE}")
    )
    return builder.as_markup()


def gender_with_cancel_kb() -> InlineKeyboardMarkup:
    """Выбор пола с кнопкой отмены."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=GENDER_LABELS[GENDER_MALE], callback_data=f"set_gender:{GENDER_MALE}"),
        InlineKeyboardButton(text=GENDER_LABELS[GENDER_FEMALE], callback_data=f"set_gender:{GENDER_FEMALE}")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


# ==================== ПРОФИЛЬ ====================

def profile_menu_kb() -> InlineKeyboardMarkup:
    """Меню профиля."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📛 Изменить имя", callback_data="change_username")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Изменить рейтинг", callback_data="change_rating"),
        InlineKeyboardButton(text="🚻 Изменить пол", callback_data="change_gender")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main"))
    return builder.as_markup()


# ==================== ВЫБОР ТИПА СОБЫТИЯ ====================

def event_type_kb() -> InlineKeyboardMarkup:
    """Выбор типа события: пара или команда."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Пара (2 человека)", callback_data="event_type:pair"),
        InlineKeyboardButton(text="👨‍👩‍👧‍👦 Команда", callback_data="event_type:team")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


# ==================== ВЫБОР РАЗМЕРА КОМАНДЫ ====================

def team_size_kb() -> InlineKeyboardMarkup:
    """Выбор размера команды."""
    builder = InlineKeyboardBuilder()
    for size in [3, 4, 5, 6]:
        builder.add(InlineKeyboardButton(text=str(size), callback_data=f"team_size:{size}"))
    builder.adjust(4)  # 4 кнопки в ряд
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


# ==================== ВЫБОР ДАТЫ ====================

def date_picker_kb(year: int, month: int) -> InlineKeyboardMarkup:
    """Простой выбор даты (календарь на месяц)."""
    import calendar
    from datetime import date
    
    builder = InlineKeyboardBuilder()
    
    # Заголовок с месяцем и годом
    month_names = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    # Кнопки навигации по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    builder.row(
        InlineKeyboardButton(text="◀️", callback_data=f"cal_nav:{prev_year}:{prev_month}"),
        InlineKeyboardButton(text=f"{month_names[month]} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_nav:{next_year}:{next_month}")
    )
    
    # Дни недели
    builder.row(
        *[InlineKeyboardButton(text=day, callback_data="cal_ignore") 
          for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]
    )
    
    # Дни месяца
    cal = calendar.Calendar(firstweekday=0)  # Понедельник первый
    today = date.today()
    
    for week in cal.monthdayscalendar(year, month):
        row_buttons = []
        for day in week:
            if day == 0:
                row_buttons.append(InlineKeyboardButton(text=" ", callback_data="cal_ignore"))
            else:
                current_date = date(year, month, day)
                # Нельзя выбрать прошедшие даты
                if current_date < today:
                    row_buttons.append(InlineKeyboardButton(text="·", callback_data="cal_ignore"))
                else:
                    date_str = current_date.strftime("%Y-%m-%d")
                    # Выделяем сегодняшний день
                    day_text = f"[{day}]" if current_date == today else str(day)
                    row_buttons.append(InlineKeyboardButton(text=day_text, callback_data=f"cal_select:{date_str}"))
        builder.row(*row_buttons)
    
    # Кнопка пропуска и отмены
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="cal_skip"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    
    return builder.as_markup()


def date_confirm_kb(date_str: str) -> InlineKeyboardMarkup:
    """Подтверждение выбранной даты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"cal_confirm:{date_str}"),
        InlineKeyboardButton(text="🔄 Изменить", callback_data="cal_change")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


# ==================== СПИСОК ТУРНИРОВ ====================

def events_list_kb(events: list, action: str = "view") -> InlineKeyboardMarkup:
    """
    Список турниров с кнопками.
    action: 'view' — просмотр, 'join' — присоединение, 'manage' — управление.
    """
    from datetime import datetime
    
    builder = InlineKeyboardBuilder()
    for event in events:
        event_id = event.get("event_id") or event.get("id")
        title = event.get("title", "Без названия")
        event_type = event.get("type", "")
        type_icon = "👥" if event_type == "pair" else "👨‍👩‍👧‍👦"
        
        # Статус для закрытых турниров
        status = event.get("status", "open")
        status_icon = "" if status == "open" else "🔒 "
        
        # Форматируем дату проведения
        event_date = event.get("event_date")
        if event_date:
            try:
                dt = datetime.strptime(event_date, "%Y-%m-%d")
                # Короткий формат даты: ДД.ММ
                date_text = f" • {dt.day:02d}.{dt.month:02d}"
                
                # Добавляем бейдж с количеством дней до события
                date_badge = event.get("date_badge", "")
                if date_badge:
                    date_text = f" • {date_badge}"
            except:
                date_text = ""
        else:
            date_text = ""
        
        button_text = f"{status_icon}{type_icon} {title}{date_text}"
        
        # Ограничиваем длину текста кнопки (макс 64 символа для Telegram)
        if len(button_text) > 60:
            # Обрезаем название, оставляя иконки и дату
            max_title_len = 60 - len(status_icon) - len(type_icon) - len(date_text) - 2
            title_short = title[:max_title_len] + "..."
            button_text = f"{status_icon}{type_icon} {title_short}{date_text}"
        
        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"event:{action}:{event_id}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    return builder.as_markup()


# ==================== МЕНЮ ТУРНИРА ====================

def event_menu_kb(event_id: int, is_owner: bool = False) -> InlineKeyboardMarkup:
    """Меню конкретного турнира."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔎 Поиск свободных", callback_data=f"search_elements:{event_id}"),
        InlineKeyboardButton(text="➕ Добавить себя", callback_data=f"add_element:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Мои заявки", callback_data=f"my_elements:{event_id}"),
        InlineKeyboardButton(text="✅ Сформированные", callback_data=f"event_groups:{event_id}")
    )
    if is_owner:
        builder.row(
            InlineKeyboardButton(text="🔒 Закрыть турнир", callback_data=f"close_event:{event_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_event:{event_id}")
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    return builder.as_markup()


# ==================== РЕДАКТИРОВАНИЕ ТУРНИРА ====================

def edit_event_kb(event_id: int) -> InlineKeyboardMarkup:
    """Меню редактирования турнира."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Изменить название", callback_data="edit_event_title")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Изменить дату", callback_data="edit_event_date")
    )
    builder.row(
        InlineKeyboardButton(text="📄 Изменить описание", callback_data="edit_event_description")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К турниру", callback_data=f"event:view:{event_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


# ==================== СПИСОК ЭЛЕМЕНТОВ ====================

def elements_list_kb(elements: list, event_id: int) -> InlineKeyboardMarkup:
    """Список свободных заявок для присоединения."""
    builder = InlineKeyboardBuilder()
    for elem in elements:
        elem_id = elem.get("element_id")
        spots_left = elem.get("spots_left", "?")
        members_info = elem.get("members_info", "")
        gender_icon = "👨" if elem.get("gender") == "male" else "👩" if elem.get("gender") == "female" else "👤"
        username = elem.get("username", "Без имени")
        rating = elem.get("rating", "?")
        builder.row(
            InlineKeyboardButton(
                text=f"🎯 {gender_icon} {username} | {members_info}",
                callback_data=f"view_element:{elem_id}"
            )
        )
    if not elements:
        builder.row(
            InlineKeyboardButton(text="📭 Нет свободных заявок", callback_data="noop")
        )
    builder.row(InlineKeyboardButton(text="🔙 К турниру", callback_data=f"event:view:{event_id}"))
    return builder.as_markup()


# ==================== ДЕТАЛИ ЭЛЕМЕНТА ====================

def element_detail_kb(element_id: int, event_id: int, can_join: bool = True) -> InlineKeyboardMarkup:
    """Детали заявки с кнопкой присоединения."""
    builder = InlineKeyboardBuilder()
    if can_join:
        builder.row(
            InlineKeyboardButton(text="✅ Присоединиться", callback_data=f"join_element:{element_id}")
        )
    builder.row(InlineKeyboardButton(text="🔙 К поиску", callback_data=f"search_elements:{event_id}"))
    return builder.as_markup()


# ==================== УПРАВЛЕНИЕ ЗАПРОСОМ ====================

def join_request_kb(join_id: int) -> InlineKeyboardMarkup:
    """Кнопки принять/отклонить запрос на присоединение."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_request:{join_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_request:{join_id}")
    )
    return builder.as_markup()


# ==================== МОИ ЭЛЕМЕНТЫ ====================

def my_elements_kb(elements: list, event_id: int) -> InlineKeyboardMarkup:
    """Список собственных заявок пользователя."""
    builder = InlineKeyboardBuilder()
    for elem in elements:
        elem_id = elem.get("element_id")
        members_count = elem.get("members_count", 0)
        target = elem.get("target_size", 2)
        pending_count = elem.get("pending_requests", 0)
        pending_badge = f" 📩{pending_count}" if pending_count > 0 else ""
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {members_count}/{target} участников{pending_badge}",
                callback_data=f"manage_element:{elem_id}"
            )
        )
    if not elements:
        builder.row(
            InlineKeyboardButton(text="📭 У вас нет заявок", callback_data="noop")
        )
    builder.row(
        InlineKeyboardButton(text="➕ Создать новый", callback_data=f"add_element:{event_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К турниру", callback_data=f"event:view:{event_id}"))
    return builder.as_markup()


# ==================== УПРАВЛЕНИЕ ЭЛЕМЕНТОМ ====================

def manage_element_kb(element_id: int, event_id: int) -> InlineKeyboardMarkup:
    """Меню управления собственными заявками."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👀 Входящие запросы", callback_data=f"view_requests:{element_id}")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Участники", callback_data=f"element_members:{element_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_element:{element_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Мои заявки", callback_data=f"my_elements:{event_id}"))
    return builder.as_markup()


# ==================== СПИСОК ЗАПРОСОВ ====================

def requests_list_kb(requests: list, element_id: int, event_id: int) -> InlineKeyboardMarkup:
    """Список входящих запросов к заявке."""
    builder = InlineKeyboardBuilder()
    for req in requests:
        join_id = req.get("join_id")
        username = req.get("username", "Без имени")
        rating = req.get("rating", "?")
        gender = req.get("gender", "")
        gender_icon = "👨" if gender == "male" else "👩" if gender == "female" else "👤"
        builder.row(
            InlineKeyboardButton(
                text=f"{gender_icon} {username} (рейтинг: {rating})",
                callback_data=f"view_request:{join_id}"
            )
        )
    if not requests:
        builder.row(
            InlineKeyboardButton(text="📭 Нет входящих запросов", callback_data="noop")
        )
    builder.row(InlineKeyboardButton(text="🔙 К заявке", callback_data=f"manage_element:{element_id}"))
    return builder.as_markup()


# ==================== ДЕТАЛИ ЗАПРОСА ====================

def request_detail_kb(join_id: int, element_id: int) -> InlineKeyboardMarkup:
    """Детали запроса с кнопками принять/отклонить."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_request:{join_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_request:{join_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К запросам", callback_data=f"view_requests:{element_id}"))
    return builder.as_markup()


# ==================== АДМИН-ПАНЕЛЬ ====================

def admin_menu_kb() -> InlineKeyboardMarkup:
    """Меню администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Чёрный список", callback_data="admin_blacklist"),
        InlineKeyboardButton(text="🏆 Турниры", callback_data="admin_events")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin_add_ban"),
        InlineKeyboardButton(text="✅ Разблокировать", callback_data="admin_remove_ban")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main")
    )
    return builder.as_markup()


def blacklist_kb() -> InlineKeyboardMarkup:
    """Меню чёрного списка."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin_add_ban"),
        InlineKeyboardButton(text="✅ Разблокировать", callback_data="admin_remove_ban")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="back_admin")
    )
    return builder.as_markup()


# ==================== АДМИН: УПРАВЛЕНИЕ ТУРНИРАМИ ====================

def admin_events_menu_kb() -> InlineKeyboardMarkup:
    """Меню управления турнирами."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Все турниры", callback_data="admin_all_events"),
        InlineKeyboardButton(text="🟢 Открытые", callback_data="admin_open_events")
    )
    builder.row(
        InlineKeyboardButton(text="🔴 Закрытые", callback_data="admin_closed_events")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить турнир", callback_data="admin_delete_event_start")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="back_admin")
    )
    return builder.as_markup()


def admin_events_list_kb(events: list) -> InlineKeyboardMarkup:
    """Список турниров для администратора."""
    builder = InlineKeyboardBuilder()
    
    for event in events[:15]:  # Показываем максимум 15
        event_id = event.get("event_id")
        title = event.get("title", "Без названия")
        event_type = event.get("type", "")
        type_icon = "👥" if event_type == "pair" else "👨‍👩‍👧‍👦"
        status = event.get("status", "open")
        status_icon = "🟢" if status == "open" else "🔴"
        
        # Обрезаем длинное название
        if len(title) > 25:
            title = title[:22] + "..."
        
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {type_icon} {title}",
                callback_data=f"admin_view_event:{event_id}"
            )
        )
    
    builder.row(InlineKeyboardButton(text="🔙 Управление турнирами", callback_data="admin_events"))
    return builder.as_markup()


def admin_event_detail_kb(event_id: int) -> InlineKeyboardMarkup:
    """Детали турнира для администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить турнир", callback_data=f"admin_confirm_delete_event:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Закрыть турнир", callback_data=f"admin_close_event:{event_id}"),
        InlineKeyboardButton(text="🔓 Открыть турнир", callback_data=f"admin_open_event:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="👤 Профиль владельца", callback_data=f"admin_view_owner:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 К списку", callback_data="admin_all_events")
    )
    return builder.as_markup()

# ==================== ПОДТВЕРЖДЕНИЕ ====================

def confirm_kb(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{action}:{target_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel")
    )
    return builder.as_markup()


# ==================== ОТМЕНА ====================

def cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


# ==================== ПУСТАЯ ЗАГЛУШКА ====================

def noop_kb() -> InlineKeyboardMarkup:
    """Пустая клавиатура (для callback noop)."""
    return InlineKeyboardMarkup(inline_keyboard=[])


# ==================== ВЫБОР ТИПА ДОБАВЛЕНИЯ ====================

def add_type_kb() -> InlineKeyboardMarkup:
    """Выбор типа добавления: один или команда."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Добавить себя одного", callback_data="add_type_solo")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Добавить команду", callback_data="add_type_team")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()
