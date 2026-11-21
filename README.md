# EventHub – Event Management System

A small event management website built with **Python (Flask)**, **HTML/CSS (Jinja templates)** and a **SQLite database**.

## Features

- **Dashboard** – upcoming events, totals, latest registrations
- **Events** – create, view, edit, delete; search by text, filter by category and upcoming/past
- **Attendees** – add, edit, delete, search; see every event a person has joined
- **Registrations** – register from an event page (new people are created automatically by email) or from an attendee page; cancel any time
- **Safety rules** – capacity can never be exceeded, no duplicate registrations, no registering for past events, capacity can't be set below current sign-ups

## Run it

```bash
cd event_manager
pip install -r requirements.txt
python seed.py        # optional: adds sample events and attendees
python app.py
```

Open http://127.0.0.1:5000

The database file `events.db` is created automatically on first run.

## Project layout

```
event_manager/
├── app.py            # Flask routes, validation, database helpers
├── schema.sql        # Table definitions (events, attendees, registrations)
├── seed.py           # Sample data
├── requirements.txt
├── static/style.css
└── templates/        # HTML pages (base layout + one file per page)
```

## Database

| Table           | Purpose                                                        |
|-----------------|----------------------------------------------------------------|
| `events`        | title, description, category, date, time, location, capacity, price |
| `attendees`     | name, unique email, phone                                      |
| `registrations` | links an attendee to an event (unique pair, cascades on delete)|

## Configuration (environment variables)

| Variable          | Default            | Meaning                              |
|-------------------|--------------------|--------------------------------------|
| `EVENTS_DB`       | `./events.db`      | Path of the SQLite file              |
| `SECRET_KEY`      | dev value          | **Set this before deploying**        |
| `CURRENCY_SYMBOL` | `₹`                | Symbol shown before prices           |
| `FLASK_DEBUG`     | off                | Set to `1` for auto-reload while developing |
| `AUTO_SEED`       | off                | Set to `1` to load sample data whenever the database is empty |

## Deploy on Render

1. Push this repo to GitHub (done if you're reading this there).
2. In Render choose **New → Blueprint** (or **New → Web Service**) and select this repo.
   - Blueprint: Render reads `render.yaml` automatically.
   - Manual web service: build command `pip install -r requirements.txt`, start command `gunicorn app:app`, and add `SECRET_KEY` (any long random string) and optionally `AUTO_SEED=1`.
3. Open the URL Render gives you.

**Important – data persistence.** Free Render services have an ephemeral filesystem and spin down after 15 minutes without traffic, so the SQLite file is wiped each time (that's why `AUTO_SEED=1` is set: the demo data comes back). This is fine for a demo or class project but not for real bookings. To keep data you can:

- use a paid Render instance with a **persistent disk** mounted at e.g. `/var/data`, and set `EVENTS_DB=/var/data/events.db`, or
- move the app to Render Postgres (needs a code change from SQLite).

## Before putting it on the internet

This is a learning/small-team project. For public use you would also want to add: user login (so only admins can edit or delete), and CSRF protection (e.g. Flask-WTF).
