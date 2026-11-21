PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT 'Other',
    event_date  TEXT    NOT NULL,              -- YYYY-MM-DD
    event_time  TEXT    NOT NULL,              -- HH:MM (24h)
    location    TEXT    NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    price       REAL    NOT NULL DEFAULT 0 CHECK (price >= 0),
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendees (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    phone      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many link: one attendee can join many events, one event has many attendees.
CREATE TABLE IF NOT EXISTS registrations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES events(id)    ON DELETE CASCADE,
    attendee_id   INTEGER NOT NULL REFERENCES attendees(id) ON DELETE CASCADE,
    registered_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (event_id, attendee_id)
);

CREATE INDEX IF NOT EXISTS idx_events_date       ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_reg_event         ON registrations(event_id);
CREATE INDEX IF NOT EXISTS idx_reg_attendee      ON registrations(attendee_id);
