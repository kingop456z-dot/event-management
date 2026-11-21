"""Fill the database with sample data so the site has something to show.

Usage:  python seed.py
Safe to run more than once: it does nothing if events already exist.
"""
from datetime import date, timedelta

from app import app, get_db, init_db

init_db()

today = date.today()


def d(days):
    return (today + timedelta(days=days)).isoformat()


EVENTS = [
    ("Python Web Dev Workshop", "Hands-on Flask and SQLite session for beginners. Bring a laptop.",
     "Workshop", d(7), "10:00", "Innovation Lab, Room 204", 30, 0),
    ("Annual Tech Conference", "Two days of talks on AI, cloud and open source.",
     "Conference", d(21), "09:00", "City Convention Centre", 300, 1500),
    ("Open Mic Night", "Music, poetry and stand-up. Sign up to perform or just enjoy the show.",
     "Concert", d(10), "19:30", "The Blue Door Cafe", 80, 200),
    ("Startup Founders Meetup", "Casual evening to swap stories and find co-founders.",
     "Meetup", d(14), "18:00", "Co-working Hub, Level 3", 40, 0),
    ("Charity Football Match", "Friendly match to raise funds for the local school.",
     "Sports", d(30), "16:00", "Riverside Stadium", 500, 100),
    ("Winter Hackathon (past)", "24-hour build event. Already finished.",
     "Conference", d(-12), "09:00", "Engineering Campus", 120, 0),
]

PEOPLE = [
    ("Aarav Sharma", "aarav@example.com", "9000000001"),
    ("Diya Patel", "diya@example.com", "9000000002"),
    ("Rohan Iyer", "rohan@example.com", "9000000003"),
    ("Meera Nair", "meera@example.com", ""),
    ("Kabir Singh", "kabir@example.com", "9000000005"),
]

with app.app_context():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM events").fetchone()[0]:
        print("Database already has events - nothing to do.")
    else:
        db.executemany(
            """INSERT INTO events (title, description, category, event_date, event_time, location, capacity, price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            EVENTS,
        )
        db.executemany("INSERT INTO attendees (name, email, phone) VALUES (?, ?, ?)", PEOPLE)
        # Everyone joins the workshop; a few join other events.
        pairs = [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (3, 2), (3, 4), (4, 5), (6, 1), (6, 3)]
        db.executemany("INSERT INTO registrations (event_id, attendee_id) VALUES (?, ?)", pairs)
        db.commit()
        print(f"Added {len(EVENTS)} events, {len(PEOPLE)} attendees, {len(pairs)} registrations.")
