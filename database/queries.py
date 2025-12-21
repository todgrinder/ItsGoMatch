"""
Функции для работы с базой данных.
Полная реализация всех запросов.
"""

import aiosqlite
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


# ==================== HELPERS ====================

def row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
    """Преобразовать Row в словарь."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: List[aiosqlite.Row]) -> List[Dict[str, Any]]:
    """Преобразовать список Row в список словарей."""
    return [dict(row) for row in rows]


# ==================== USERS ====================

async def get_user(db: aiosqlite.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    """Получить пользователя по ID."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def create_user(db: aiosqlite.Connection, user_id: int, telegram_username: Optional[str] = None) -> None:
    """Создать нового пользователя (без данных профиля)."""
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, telegram_username) VALUES (?, ?)",
        (user_id, telegram_username)
    )
    await db.commit()


async def update_telegram_username(db: aiosqlite.Connection, user_id: int, telegram_username: Optional[str]) -> None:
    """Обновить Telegram username пользователя."""
    await db.execute(
        "UPDATE users SET telegram_username = ? WHERE user_id = ?",
        (telegram_username, user_id)
    )
    await db.commit()


async def update_user_profile(
    db: aiosqlite.Connection,
    user_id: int,
    username: Optional[str] = None,
    rating: Optional[float] = None,
    gender: Optional[str] = None,
    telegram_username: Optional[str] = None  # Новый параметр
) -> None:
    """Обновить профиль пользователя (любые поля)."""
    updates = []
    params = []
    
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    
    if rating is not None:
        updates.append("rating = ?")
        params.append(rating)
    
    if gender is not None:
        updates.append("gender = ?")
        params.append(gender)
    
    if telegram_username is not None:
        updates.append("telegram_username = ?")
        params.append(telegram_username)
    
    if not updates:
        return
    
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
    
    await db.execute(query, params)
    await db.commit()

async def update_username(db: aiosqlite.Connection, user_id: int, username: str) -> None:
    """Обновить имя пользователя."""
    await db.execute(
        "UPDATE users SET username = ? WHERE user_id = ?",
        (username, user_id)
    )
    await db.commit()


async def update_rating(db: aiosqlite.Connection, user_id: int, rating: float) -> None:
    """Обновить рейтинг пользователя."""
    await db.execute(
        "UPDATE users SET rating = ? WHERE user_id = ?",
        (rating, user_id)
    )
    await db.commit()


async def update_gender(db: aiosqlite.Connection, user_id: int, gender: str) -> None:
    """Обновить пол пользователя."""
    await db.execute(
        "UPDATE users SET gender = ? WHERE user_id = ?",
        (gender, user_id)
    )
    await db.commit()


async def is_profile_complete(db: aiosqlite.Connection, user_id: int) -> bool:
    """Проверить, заполнен ли профиль (имя, рейтинг и пол)."""
    cursor = await db.execute(
        "SELECT username, rating, gender FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    if row is None:
        return False
    
    username, rating, gender = row
    return all([username is not None, rating is not None, gender is not None])


async def get_group_members_with_contacts(db: aiosqlite.Connection, group_id: int) -> List[Dict[str, Any]]:
    """Получить участников группы с контактной информацией."""
    cursor = await db.execute(
        """
        SELECT 
            u.user_id,
            u.username,
            u.telegram_username,
            u.rating,
            u.gender,
            gm.joined_at
        FROM group_members gm
        JOIN users u ON gm.user_id = u.user_id
        WHERE gm.group_id = ?
        ORDER BY gm.joined_at ASC
        """,
        (group_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)

async def delete_user(db: aiosqlite.Connection, user_id: int) -> None:
    """Удалить пользователя и все связанные данные (каскадно)."""
    await db.execute(
        "DELETE FROM users WHERE user_id = ?",
        (user_id,)
    )
    await db.commit()


# ==================== EVENTS ====================

async def create_event(
    db: aiosqlite.Connection,
    owner_id: int,
    title: str,
    event_type: str,
    team_size: Optional[int] = None,
    description: Optional[str] = None,
    event_date: Optional[str] = None  # Новый параметр
) -> int:
    """Создать новое событие. Возвращает event_id."""
    # Для пар устанавливаем team_size = 2
    if event_type == "pair":
        team_size = 2
    
    cursor = await db.execute(
        """
        INSERT INTO events (owner_id, title, type, team_size, description, event_date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (owner_id, title, event_type, team_size, description, event_date)
    )
    await db.commit()
    return cursor.lastrowid


async def get_event(db: aiosqlite.Connection, event_id: int) -> Optional[Dict[str, Any]]:
    """Получить событие по ID."""
    cursor = await db.execute(
        "SELECT * FROM events WHERE event_id = ?",
        (event_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def list_open_events(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Получить список открытых событий, отсортированных по дате."""
    cursor = await db.execute(
        """
        SELECT e.*, u.username as owner_name
        FROM events e
        LEFT JOIN users u ON e.owner_id = u.user_id
        WHERE e.status = 'open'
        ORDER BY 
            CASE WHEN e.event_date IS NULL THEN 1 ELSE 0 END,
            e.event_date ASC,
            e.created_at DESC
        """
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def list_user_events(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Получить список событий, созданных пользователем."""
    cursor = await db.execute(
        """
        SELECT * FROM events
        WHERE owner_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def close_event(db: aiosqlite.Connection, event_id: int, owner_id: int) -> bool:
    """Закрыть событие. Возвращает True если успешно."""
    cursor = await db.execute(
        """
        UPDATE events
        SET status = 'closed'
        WHERE event_id = ? AND owner_id = ?
        """,
        (event_id, owner_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_expired_events(db: aiosqlite.Connection, current_date: str) -> List[Dict[str, Any]]:
    """
    Получить события, которые нужно закрыть (дата проведения прошла).
    current_date в формате YYYY-MM-DD
    """
    cursor = await db.execute(
        """
        SELECT * FROM events
        WHERE status = 'open'
          AND event_date IS NOT NULL
          AND event_date < ?
        """,
        (current_date,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def close_expired_events(db: aiosqlite.Connection, current_date: str) -> int:
    """
    Закрыть все события, дата проведения которых прошла.
    Возвращает количество закрытых событий.
    """
    cursor = await db.execute(
        """
        UPDATE events
        SET status = 'closed'
        WHERE status = 'open'
          AND event_date IS NOT NULL
          AND event_date < ?
        """,
        (current_date,)
    )
    await db.commit()
    return cursor.rowcount


async def update_event(
    db: aiosqlite.Connection,
    event_id: int,
    owner_id: int,
    **kwargs  # title, description, event_date
) -> bool:
    """
    Обновить событие (только владелец).
    Принимает kwargs: title, description, event_date
    event_date может быть None для удаления даты.
    """
    updates = []
    params = []
    
    if "title" in kwargs:
        updates.append("title = ?")
        params.append(kwargs["title"])
    
    if "description" in kwargs:
        updates.append("description = ?")
        params.append(kwargs["description"])
    
    if "event_date" in kwargs:
        updates.append("event_date = ?")
        params.append(kwargs["event_date"])
    
    if not updates:
        return False
    
    params.extend([event_id, owner_id])
    query = f"UPDATE events SET {', '.join(updates)} WHERE event_id = ? AND owner_id = ?"
    
    cursor = await db.execute(query, params)
    await db.commit()
    return cursor.rowcount > 0


# ==================== ELEMENTS ====================

async def create_element(
    db: aiosqlite.Connection,
    event_id: int,
    creator_id: int,
    target_size: int,
    initial_members: List[int],
    description: Optional[str] = None
) -> int:
    """Создать новый элемент. Возвращает element_id."""
    cursor = await db.execute(
        """
        INSERT INTO elements (event_id, creator_id, target_size, description, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (event_id, creator_id, target_size, description)
    )
    element_id = cursor.lastrowid
    
    # Добавляем начальных участников
    for user_id in initial_members:
        await db.execute(
            """
            INSERT INTO element_members (element_id, user_id)
            VALUES (?, ?)
            """,
            (element_id, user_id)
        )
    
    await db.commit()
    return element_id


async def get_element(db: aiosqlite.Connection, element_id: int) -> Optional[Dict[str, Any]]:
    """Получить элемент по ID с дополнительной информацией."""
    cursor = await db.execute(
        """
        SELECT e.*, 
               ev.title as event_title,
               ev.type as event_type,
               ev.team_size as event_team_size,
               u.username as creator_name,
               (SELECT COUNT(*) FROM element_members em WHERE em.element_id = e.element_id) as members_count
        FROM elements e
        LEFT JOIN events ev ON e.event_id = ev.event_id
        LEFT JOIN users u ON e.creator_id = u.user_id
        WHERE e.element_id = ?
        """,
        (element_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def list_open_elements(db: aiosqlite.Connection, event_id: int) -> List[Dict[str, Any]]:
    """Получить список открытых элементов в событии с информацией об участниках."""
    cursor = await db.execute(
        """
        SELECT 
            e.element_id,
            e.event_id,
            e.creator_id,
            e.target_size,
            e.description,
            e.created_at,
            u.username as creator_name,
            u.rating as creator_rating,
            u.gender as creator_gender,
            (SELECT COUNT(*) FROM element_members em WHERE em.element_id = e.element_id) as members_count,
            (e.target_size - (SELECT COUNT(*) FROM element_members em WHERE em.element_id = e.element_id)) as spots_left
        FROM elements e
        LEFT JOIN users u ON e.creator_id = u.user_id
        WHERE e.event_id = ?
          AND e.is_active = 1
          AND (e.target_size - (SELECT COUNT(*) FROM element_members em WHERE em.element_id = e.element_id)) > 0
        ORDER BY e.created_at DESC
        """,
        (event_id,)
    )
    rows = await cursor.fetchall()
    elements = rows_to_list(rows)
    
    # Добавляем информацию об участниках для каждого элемента
    for elem in elements:
        members = await get_element_members(db, elem["element_id"])
        elem["members"] = members
        # Формируем краткую информацию для отображения
        if members:
            ratings = [m["rating"] for m in members if m.get("rating") is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            elem["members_info"] = f"⭐ {avg_rating:.0f}"
        else:
            elem["members_info"] = ""
    
    return elements


async def get_user_elements(db: aiosqlite.Connection, event_id: int, user_id: int) -> List[Dict[str, Any]]:
    """Получить элементы, где пользователь является создателем или участником, в событии."""
    cursor = await db.execute(
        """
        SELECT DISTINCT
            e.element_id,
            e.event_id,
            e.creator_id,
            e.target_size,
            e.description,
            e.created_at,
            e.is_active,
            (SELECT COUNT(*) FROM element_members em WHERE em.element_id = e.element_id) as members_count,
            (SELECT COUNT(*) FROM join_requests jr WHERE jr.element_id = e.element_id AND jr.status = 'pending') as pending_requests
        FROM elements e
        LEFT JOIN element_members em ON e.element_id = em.element_id
        WHERE e.event_id = ?
          AND e.is_active = 1
          AND (e.creator_id = ? OR em.user_id = ?)
        ORDER BY e.created_at DESC
        """,
        (event_id, user_id, user_id)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_all_user_active_elements(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Получить все активные элементы пользователя во всех событиях."""
    cursor = await db.execute(
        """
        SELECT DISTINCT e.*, ev.title as event_title
        FROM elements e
        LEFT JOIN element_members em ON e.element_id = em.element_id
        LEFT JOIN events ev ON e.event_id = ev.event_id
        WHERE e.is_active = 1
          AND (e.creator_id = ? OR em.user_id = ?)
        ORDER BY e.created_at DESC
        """,
        (user_id, user_id)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def deactivate_element(db: aiosqlite.Connection, element_id: int) -> None:
    """Деактивировать элемент (is_active = 0)."""
    await db.execute(
        "UPDATE elements SET is_active = 0 WHERE element_id = ?",
        (element_id,)
    )
    await db.commit()


async def delete_element(db: aiosqlite.Connection, element_id: int, user_id: int) -> bool:
    """Удалить элемент (только если пользователь — создатель)."""
    cursor = await db.execute(
        "DELETE FROM elements WHERE element_id = ? AND creator_id = ?",
        (element_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_element_members(db: aiosqlite.Connection, element_id: int) -> List[Dict[str, Any]]:
    """Получить список участников элемента с их профилями."""
    cursor = await db.execute(
        """
        SELECT 
            u.user_id,
            u.username,
            u.rating,
            u.gender,
            em.joined_at
        FROM element_members em
        JOIN users u ON em.user_id = u.user_id
        WHERE em.element_id = ?
        ORDER BY em.joined_at ASC
        """,
        (element_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def add_element_member(db: aiosqlite.Connection, element_id: int, user_id: int) -> None:
    """Добавить участника в элемент."""
    await db.execute(
        """
        INSERT OR IGNORE INTO element_members (element_id, user_id)
        VALUES (?, ?)
        """,
        (element_id, user_id)
    )
    await db.commit()


async def remove_element_member(db: aiosqlite.Connection, element_id: int, user_id: int) -> bool:
    """Удалить участника из элемента."""
    cursor = await db.execute(
        "DELETE FROM element_members WHERE element_id = ? AND user_id = ?",
        (element_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0


async def check_user_has_element(db: aiosqlite.Connection, event_id: int, user_id: int) -> bool:
    """Проверить, есть ли у пользователя активный элемент в событии (как создатель или участник)."""
    cursor = await db.execute(
        """
        SELECT 1 FROM elements e
        LEFT JOIN element_members em ON e.element_id = em.element_id
        WHERE e.event_id = ?
          AND e.is_active = 1
          AND (e.creator_id = ? OR em.user_id = ?)
        LIMIT 1
        """,
        (event_id, user_id, user_id)
    )
    row = await cursor.fetchone()
    return row is not None


async def check_user_in_element(db: aiosqlite.Connection, element_id: int, user_id: int) -> bool:
    """Проверить, является ли пользователь участником элемента."""
    cursor = await db.execute(
        "SELECT 1 FROM element_members WHERE element_id = ? AND user_id = ?",
        (element_id, user_id)
    )
    row = await cursor.fetchone()
    return row is not None


async def get_element_spots_left(db: aiosqlite.Connection, element_id: int) -> int:
    """Получить количество свободных мест в элементе."""
    cursor = await db.execute(
        """
        SELECT 
            e.target_size - COUNT(em.user_id) as spots_left
        FROM elements e
        LEFT JOIN element_members em ON e.element_id = em.element_id
        WHERE e.element_id = ?
        GROUP BY e.element_id
        """,
        (element_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return 0
    return row[0]


async def is_element_full(db: aiosqlite.Connection, element_id: int) -> bool:
    """Проверить, заполнен ли элемент."""
    spots = await get_element_spots_left(db, element_id)
    return spots <= 0


# ==================== JOIN REQUESTS ====================

async def create_join_request(
    db: aiosqlite.Connection,
    element_id: int,
    requester_id: int,
    expires_at: Optional[str] = None
) -> int:
    """Создать запрос на присоединение. Возвращает join_id."""
    if expires_at is None:
        # По умолчанию запрос истекает через 24 часа
        expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
    
    cursor = await db.execute(
        """
        INSERT INTO join_requests (element_id, requester_id, status, expires_at)
        VALUES (?, ?, 'pending', ?)
        """,
        (element_id, requester_id, expires_at)
    )
    await db.commit()
    return cursor.lastrowid


async def get_join_request(db: aiosqlite.Connection, join_id: int) -> Optional[Dict[str, Any]]:
    """Получить запрос по ID с информацией о пользователе и элементе."""
    cursor = await db.execute(
        """
        SELECT 
            jr.*,
            u.username,
            u.rating,
            u.gender,
            e.creator_id as element_creator_id,
            e.event_id,
            e.target_size
        FROM join_requests jr
        JOIN users u ON jr.requester_id = u.user_id
        JOIN elements e ON jr.element_id = e.element_id
        WHERE jr.join_id = ?
        """,
        (join_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def update_join_request_status(db: aiosqlite.Connection, join_id: int, status: str) -> None:
    """Обновить статус запроса."""
    await db.execute(
        "UPDATE join_requests SET status = ? WHERE join_id = ?",
        (status, join_id)
    )
    await db.commit()


async def get_pending_requests_for_element(db: aiosqlite.Connection, element_id: int) -> List[Dict[str, Any]]:
    """Получить ожидающие запросы для элемента."""
    cursor = await db.execute(
        """
        SELECT 
            jr.*,
            u.username,
            u.rating,
            u.gender
        FROM join_requests jr
        JOIN users u ON jr.requester_id = u.user_id
        WHERE jr.element_id = ?
          AND jr.status = 'pending'
        ORDER BY jr.created_at ASC
        """,
        (element_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_pending_requests_for_user(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Получить ожидающие запросы, отправленные пользователем."""
    cursor = await db.execute(
        """
        SELECT 
            jr.*,
            e.event_id,
            ev.title as event_title
        FROM join_requests jr
        JOIN elements e ON jr.element_id = e.element_id
        JOIN events ev ON e.event_id = ev.event_id
        WHERE jr.requester_id = ?
          AND jr.status = 'pending'
        ORDER BY jr.created_at DESC
        """,
        (user_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_incoming_requests_for_user(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Получить входящие запросы к элементам пользователя."""
    cursor = await db.execute(
        """
        SELECT 
            jr.*,
            u.username,
            u.rating,
            u.gender,
            e.event_id,
            ev.title as event_title
        FROM join_requests jr
        JOIN users u ON jr.requester_id = u.user_id
        JOIN elements e ON jr.element_id = e.element_id
        JOIN events ev ON e.event_id = ev.event_id
        WHERE e.creator_id = ?
          AND jr.status = 'pending'
        ORDER BY jr.created_at ASC
        """,
        (user_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def check_existing_request(db: aiosqlite.Connection, element_id: int, requester_id: int) -> bool:
    """Проверить, есть ли уже активный запрос от пользователя к элементу."""
    cursor = await db.execute(
        """
        SELECT 1 FROM join_requests
        WHERE element_id = ? AND requester_id = ? AND status = 'pending'
        LIMIT 1
        """,
        (element_id, requester_id)
    )
    row = await cursor.fetchone()
    return row is not None


async def reject_all_pending_requests(db: aiosqlite.Connection, element_id: int) -> int:
    """Отклонить все ожидающие запросы для элемента. Возвращает количество отклонённых."""
    cursor = await db.execute(
        """
        UPDATE join_requests
        SET status = 'rejected'
        WHERE element_id = ? AND status = 'pending'
        """,
        (element_id,)
    )
    await db.commit()
    return cursor.rowcount


async def expire_old_requests(db: aiosqlite.Connection) -> int:
    """Пометить просроченные запросы как expired. Возвращает количество."""
    now = datetime.now().isoformat()
    cursor = await db.execute(
        """
        UPDATE join_requests
        SET status = 'expired'
        WHERE status = 'pending' AND expires_at < ?
        """,
        (now,)
    )
    await db.commit()
    return cursor.rowcount


async def cancel_user_request(db: aiosqlite.Connection, join_id: int, requester_id: int) -> bool:
    """Отменить запрос (только отправитель может отменить)."""
    cursor = await db.execute(
        """
        UPDATE join_requests
        SET status = 'rejected'
        WHERE join_id = ? AND requester_id = ? AND status = 'pending'
        """,
        (join_id, requester_id)
    )
    await db.commit()
    return cursor.rowcount > 0


# ==================== GROUPS ====================

async def create_group(
    db: aiosqlite.Connection,
    event_id: int,
    member_ids: List[int]
) -> int:
    """Создать группу (полную пару/команду). Возвращает group_id."""
    # Рассчитываем средний рейтинг
    placeholders = ",".join("?" for _ in member_ids)
    cursor = await db.execute(
        f"SELECT AVG(rating) FROM users WHERE user_id IN ({placeholders})",
        member_ids
    )
    row = await cursor.fetchone()
    rating_avg = row[0] if row and row[0] else 0
    
    # Создаём группу
    cursor = await db.execute(
        """
        INSERT INTO groups (event_id, rating_avg)
        VALUES (?, ?)
        """,
        (event_id, rating_avg)
    )
    group_id = cursor.lastrowid
    
    # Добавляем участников
    for user_id in member_ids:
        await db.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id)
        )
    
    await db.commit()
    return group_id


async def get_group(db: aiosqlite.Connection, group_id: int) -> Optional[Dict[str, Any]]:
    """Получить группу по ID."""
    cursor = await db.execute(
        """
        SELECT g.*, ev.title as event_title, ev.type as event_type
        FROM groups g
        JOIN events ev ON g.event_id = ev.event_id
        WHERE g.group_id = ?
        """,
        (group_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def get_user_groups(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Получить группы пользователя."""
    cursor = await db.execute(
        """
        SELECT 
            g.*,
            ev.title as event_title,
            ev.type as event_type,
            (SELECT COUNT(*) FROM group_members gm2 WHERE gm2.group_id = g.group_id) as members_count
        FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        JOIN events ev ON g.event_id = ev.event_id
        WHERE gm.user_id = ?
        ORDER BY g.created_at DESC
        """,
        (user_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_group_members(db: aiosqlite.Connection, group_id: int) -> List[Dict[str, Any]]:
    """Получить участников группы."""
    cursor = await db.execute(
        """
        SELECT 
            u.user_id,
            u.username,
            u.rating,
            u.gender,
            gm.joined_at
        FROM group_members gm
        JOIN users u ON gm.user_id = u.user_id
        WHERE gm.group_id = ?
        ORDER BY gm.joined_at ASC
        """,
        (group_id,)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_event_groups(db: aiosqlite.Connection, event_id: int) -> List[Dict[str, Any]]:
    """Получить все сформированные группы в событии."""
    cursor = await db.execute(
        """
        SELECT 
            g.*,
            (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.group_id) as members_count
        FROM groups g
        WHERE g.event_id = ?
        ORDER BY g.created_at DESC
        """,
        (event_id,)
    )
    rows = await cursor.fetchall()
    groups = rows_to_list(rows)
    
    # Добавляем информацию об участниках
    for group in groups:
        members = await get_group_members(db, group["group_id"])
        group["members"] = members
    
    return groups


async def check_user_in_group(db: aiosqlite.Connection, event_id: int, user_id: int) -> bool:
    """Проверить, состоит ли пользователь в какой-либо группе в событии."""
    cursor = await db.execute(
        """
        SELECT 1 FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE g.event_id = ? AND gm.user_id = ?
        LIMIT 1
        """,
        (event_id, user_id)
    )
    row = await cursor.fetchone()
    return row is not None


# ==================== LOGS ====================

async def create_log(
    db: aiosqlite.Connection,
    event_type: str,
    details: Optional[str] = None
) -> int:
    """Создать запись в логе."""
    cursor = await db.execute(
        "INSERT INTO logs (event_type, details) VALUES (?, ?)",
        (event_type, details)
    )
    await db.commit()
    return cursor.lastrowid


async def get_logs(
    db: aiosqlite.Connection,
    event_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Получить записи из лога."""
    if event_type:
        cursor = await db.execute(
            """
            SELECT * FROM logs
            WHERE event_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (event_type, limit)
        )
    else:
        cursor = await db.execute(
            """
            SELECT * FROM logs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


# ==================== COMPLEX OPERATIONS ====================

async def accept_join_request(db: aiosqlite.Connection, join_id: int) -> Dict[str, Any]:
    """
    Принять запрос на присоединение.
    Возвращает словарь с информацией о результате:
    - success: bool
    - group_created: bool (если элемент заполнен)
    - group_id: int (если создана группа)
    - element_id: int
    - event_id: int
    - member_ids: List[int] (все участники)
    """
    result = {
        "success": False,
        "group_created": False,
        "group_id": None,
        "element_id": None,
        "event_id": None,
        "member_ids": []
    }
    
    # Получаем информацию о запросе
    request = await get_join_request(db, join_id)
    if not request or request["status"] != "pending":
        return result
    
    element_id = request["element_id"]
    requester_id = request["requester_id"]
    event_id = request["event_id"]
    
    result["element_id"] = element_id
    result["event_id"] = event_id
    
    # Проверяем, что в элементе есть место
    spots_left = await get_element_spots_left(db, element_id)
    if spots_left <= 0:
        await update_join_request_status(db, join_id, "rejected")
        return result
    
    # Принимаем запрос
    await update_join_request_status(db, join_id, "accepted")
    
    # Добавляем пользователя в элемент
    await add_element_member(db, element_id, requester_id)
    
    result["success"] = True
    
    # Проверяем, заполнен ли теперь элемент
    if await is_element_full(db, element_id):
        # Получаем всех участников
        members = await get_element_members(db, element_id)
        member_ids = [m["user_id"] for m in members]
        result["member_ids"] = member_ids
        
        # Создаём группу
        group_id = await create_group(db, event_id, member_ids)
        result["group_created"] = True
        result["group_id"] = group_id
        
        # Деактивируем элемент
        await deactivate_element(db, element_id)
        
        # Отклоняем все оставшиеся запросы
        await reject_all_pending_requests(db, element_id)
    else:
        members = await get_element_members(db, element_id)
        result["member_ids"] = [m["user_id"] for m in members]
    
    return result


async def get_event_statistics(db: aiosqlite.Connection, event_id: int) -> Dict[str, Any]:
    """Получить статистику по событию."""
    # Количество активных элементов
    cursor = await db.execute(
        "SELECT COUNT(*) FROM elements WHERE event_id = ? AND is_active = 1",
        (event_id,)
    )
    active_elements = (await cursor.fetchone())[0]
    
    # Количество сформированных групп
    cursor = await db.execute(
        "SELECT COUNT(*) FROM groups WHERE event_id = ?",
        (event_id,)
    )
    total_groups = (await cursor.fetchone())[0]
    
    # Количество участников в группах
    cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT gm.user_id)
        FROM group_members gm
        JOIN groups g ON gm.group_id = g.group_id
        WHERE g.event_id = ?
        """,
        (event_id,)
    )
    users_in_groups = (await cursor.fetchone())[0]
    
    # Количество ожидающих запросов
    cursor = await db.execute(
        """
        SELECT COUNT(*)
        FROM join_requests jr
        JOIN elements e ON jr.element_id = e.element_id
        WHERE e.event_id = ? AND jr.status = 'pending'
        """,
        (event_id,)
    )
    pending_requests = (await cursor.fetchone())[0]
    
    return {
        "active_elements": active_elements,
        "total_groups": total_groups,
        "users_in_groups": users_in_groups,
        "pending_requests": pending_requests
    }

# ==================== BLACKLIST ====================

async def is_user_banned(db: aiosqlite.Connection, user_id: int) -> bool:
    """Проверить, находится ли пользователь в чёрном списке."""
    cursor = await db.execute(
        "SELECT 1 FROM blacklist WHERE user_id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    return row is not None


async def get_ban_info(db: aiosqlite.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    """Получить информацию о бане пользователя."""
    cursor = await db.execute(
        """
        SELECT b.*, u.username as banned_user_name, admin.username as admin_name
        FROM blacklist b
        LEFT JOIN users u ON b.user_id = u.user_id
        LEFT JOIN users admin ON b.banned_by = admin.user_id
        WHERE b.user_id = ?
        """,
        (user_id,)
    )
    row = await cursor.fetchone()
    return row_to_dict(row)


async def add_to_blacklist(
    db: aiosqlite.Connection,
    user_id: int,
    banned_by: int,
    reason: Optional[str] = None
) -> bool:
    """
    Добавить пользователя в чёрный список.
    Возвращает True если добавлен, False если уже был в списке.
    """
    try:
        await db.execute(
            """
            INSERT INTO blacklist (user_id, banned_by, reason)
            VALUES (?, ?, ?)
            """,
            (user_id, banned_by, reason)
        )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        # Пользователь уже в чёрном списке
        return False


async def remove_from_blacklist(db: aiosqlite.Connection, user_id: int) -> bool:
    """
    Удалить пользователя из чёрного списка.
    Возвращает True если удалён, False если не был в списке.
    """
    cursor = await db.execute(
        "DELETE FROM blacklist WHERE user_id = ?",
        (user_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_blacklist(
    db: aiosqlite.Connection,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Получить список заблокированных пользователей."""
    cursor = await db.execute(
        """
        SELECT b.*, u.username as banned_user_name, admin.username as admin_name
        FROM blacklist b
        LEFT JOIN users u ON b.user_id = u.user_id
        LEFT JOIN users admin ON b.banned_by = admin.user_id
        ORDER BY b.banned_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_blacklist_count(db: aiosqlite.Connection) -> int:
    """Получить количество пользователей в чёрном списке."""
    cursor = await db.execute("SELECT COUNT(*) FROM blacklist")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def update_ban_reason(db: aiosqlite.Connection, user_id: int, reason: str) -> bool:
    """Обновить причину бана."""
    cursor = await db.execute(
        "UPDATE blacklist SET reason = ? WHERE user_id = ?",
        (reason, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0

# ==================== ADMIN FUNCTIONS ====================

async def delete_event(db: aiosqlite.Connection, event_id: int) -> bool:
    """
    Удалить событие (для администратора).
    Возвращает True если удалён.
    """
    cursor = await db.execute(
        "DELETE FROM events WHERE event_id = ?",
        (event_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_all_events(
    db: aiosqlite.Connection,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Получить все события (для администратора).
    status: 'open', 'closed' или None для всех.
    """
    if status:
        cursor = await db.execute(
            """
            SELECT e.*, u.username as owner_name, u.telegram_username as owner_telegram
            FROM events e
            LEFT JOIN users u ON e.owner_id = u.user_id
            WHERE e.status = ?
            ORDER BY e.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (status, limit, offset)
        )
    else:
        cursor = await db.execute(
            """
            SELECT e.*, u.username as owner_name, u.telegram_username as owner_telegram
            FROM events e
            LEFT JOIN users u ON e.owner_id = u.user_id
            ORDER BY e.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
    rows = await cursor.fetchall()
    return rows_to_list(rows)


async def get_events_count(db: aiosqlite.Connection, status: Optional[str] = None) -> int:
    """Получить количество событий."""
    if status:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE status = ?",
            (status,)
        )
    else:
        cursor = await db.execute("SELECT COUNT(*) FROM events")
    
    row = await cursor.fetchone()
    return row[0] if row else 0


async def get_event_full_info(db: aiosqlite.Connection, event_id: int) -> Optional[Dict[str, Any]]:
    """Получить полную информацию о турнире для администратора."""
    # Основная информация
    event = await get_event(db, event_id)
    if not event:
        return None
    
    # Статистика
    stats = await get_event_statistics(db, event_id)
    
    # Информация о владельце
    owner = await get_user(db, event["owner_id"])
    
    return {
        **event,
        "owner": owner,
        "stats": stats
    }
