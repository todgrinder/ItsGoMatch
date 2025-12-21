-- ========================================
-- Схема базы данных для Tournament Bot
-- ========================================

-- Пользователи
CREATE TABLE IF NOT EXISTS users (
    user_id           INTEGER PRIMARY KEY,
    username          TEXT,
    telegram_username TEXT,  -- Реальный @username из Telegram
    rating            REAL,
    gender            TEXT CHECK (gender IN ('male', 'female')),
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- События/Турниры
CREATE TABLE IF NOT EXISTS events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id     INTEGER NOT NULL,
    title        TEXT NOT NULL,
    type         TEXT NOT NULL CHECK (type IN ('pair', 'team')),
    team_size    INTEGER,
    description  TEXT,
    event_date   TEXT,  -- Дата проведения в формате YYYY-MM-DD
    status       TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Элементы (части пар/команд)
CREATE TABLE IF NOT EXISTS elements (
    element_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL,
    creator_id   INTEGER NOT NULL,
    target_size  INTEGER NOT NULL,
    description  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    is_active    INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (event_id)   REFERENCES events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (creator_id) REFERENCES users(user_id)   ON DELETE CASCADE
);

-- Участники элементов
CREATE TABLE IF NOT EXISTS element_members (
    element_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (element_id, user_id),
    FOREIGN KEY (element_id) REFERENCES elements(element_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES users(user_id)       ON DELETE CASCADE
);

-- Запросы на присоединение
CREATE TABLE IF NOT EXISTS join_requests (
    join_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    element_id   INTEGER NOT NULL,
    requester_id INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected', 'expired')) DEFAULT 'pending',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT,
    FOREIGN KEY (element_id)   REFERENCES elements(element_id) ON DELETE CASCADE,
    FOREIGN KEY (requester_id) REFERENCES users(user_id)       ON DELETE CASCADE
);

-- Сформированные группы (пары/команды)
CREATE TABLE IF NOT EXISTS groups (
    group_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    rating_avg  REAL,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

-- Участники групп
CREATE TABLE IF NOT EXISTS group_members (
    group_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(user_id)   ON DELETE CASCADE
);

-- Логи (опционально)
CREATE TABLE IF NOT EXISTS logs (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    details    TEXT,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Чёрный список пользователей
CREATE TABLE IF NOT EXISTS blacklist (
    user_id      INTEGER PRIMARY KEY,
    reason       TEXT,
    banned_by    INTEGER,
    banned_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (banned_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- ========================================
-- Индексы
-- ========================================
CREATE INDEX IF NOT EXISTS idx_elements_event_active ON elements(event_id, is_active);
CREATE INDEX IF NOT EXISTS idx_element_members_elem ON element_members(element_id);
CREATE INDEX IF NOT EXISTS idx_join_requests_status_elem ON join_requests(element_id, status);
CREATE INDEX IF NOT EXISTS idx_groups_event ON groups(event_id);
CREATE INDEX IF NOT EXISTS idx_users_gender ON users(gender);
CREATE INDEX IF NOT EXISTS idx_users_rating ON users(rating);
CREATE INDEX IF NOT EXISTS idx_blacklist_user ON blacklist(user_id);
CREATE INDEX IF NOT EXISTS idx_events_date_status ON events(event_date, status);