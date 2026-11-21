"""EventHub - a small event management website built with Flask and SQLite."""
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES = ["Conference", "Workshop", "Meetup", "Concert", "Wedding", "Sports", "Other"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CURRENCY = os.environ.get("CURRENCY_SYMBOL", "₹")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["DATABASE"] = os.environ.get("EVENTS_DB", str(BASE_DIR / "events.db"))


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist yet (safe to call repeatedly)."""
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript((BASE_DIR / "schema.sql").read_text())
    db.commit()
    db.close()


EVENT_SELECT = """
    SELECT e.*, COUNT(r.id) AS registered
    FROM events e
    LEFT JOIN registrations r ON r.event_id = e.id
"""


def get_event(event_id):
    row = get_db().execute(EVENT_SELECT + " WHERE e.id = ? GROUP BY e.id", (event_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def get_attendee(attendee_id):
    row = get_db().execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def add_registration(db, event, attendee_id):
    """Register an attendee. Returns (ok, message). The capacity check and the
    insert happen in one SQL statement so two requests cannot overbook."""
    if event["event_date"] < date.today().isoformat():
        return False, "This event has already taken place."
    try:
        cur = db.execute(
            """INSERT INTO registrations (event_id, attendee_id)
               SELECT ?, ?
               WHERE (SELECT COUNT(*) FROM registrations WHERE event_id = ?)
                     < (SELECT capacity FROM events WHERE id = ?)""",
            (event["id"], attendee_id, event["id"], event["id"]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return False, "That attendee is already registered for this event."
    if cur.rowcount == 0:
        return False, "Sorry, this event is full."
    return True, "Registration confirmed."


def safe_next(default):
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return default


# --------------------------------------------------------------------------
# Template helpers
# --------------------------------------------------------------------------
@app.template_filter("fmt_date")
def fmt_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%a, %d %b %Y")
    except (TypeError, ValueError):
        return value


@app.template_filter("fmt_time")
def fmt_time(value):
    try:
        return datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return value


@app.template_filter("money")
def money(value):
    return "Free" if not value else f"{CURRENCY}{float(value):,.2f}"


@app.context_processor
def inject_globals():
    return {"today": date.today().isoformat(), "categories": CATEGORIES}


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/")
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    stats = {
        "upcoming": db.execute("SELECT COUNT(*) FROM events WHERE event_date >= ?", (today,)).fetchone()[0],
        "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "attendees": db.execute("SELECT COUNT(*) FROM attendees").fetchone()[0],
        "registrations": db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0],
    }
    upcoming = db.execute(
        EVENT_SELECT + " WHERE e.event_date >= ? GROUP BY e.id ORDER BY e.event_date, e.event_time LIMIT 5",
        (today,),
    ).fetchall()
    recent = db.execute(
        """SELECT r.registered_at, a.id AS attendee_id, a.name, e.id AS event_id, e.title
           FROM registrations r
           JOIN attendees a ON a.id = r.attendee_id
           JOIN events e ON e.id = r.event_id
           ORDER BY r.id DESC LIMIT 6"""
    ).fetchall()
    return render_template("dashboard.html", stats=stats, upcoming=upcoming, recent=recent)


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
@app.route("/events")
def events_list():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    when = request.args.get("when", "upcoming")
    today = date.today().isoformat()

    conditions, params = [], []
    if q:
        conditions.append("(e.title LIKE ? OR e.location LIKE ? OR e.description LIKE ?)")
        params += [f"%{q}%"] * 3
    if category in CATEGORIES:
        conditions.append("e.category = ?")
        params.append(category)
    if when == "upcoming":
        conditions.append("e.event_date >= ?")
        params.append(today)
    elif when == "past":
        conditions.append("e.event_date < ?")
        params.append(today)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order = "DESC" if when == "past" else "ASC"
    events = get_db().execute(
        f"{EVENT_SELECT} {where} GROUP BY e.id ORDER BY e.event_date {order}, e.event_time {order}", params
    ).fetchall()
    return render_template("events.html", events=events, q=q, category=category, when=when)


def parse_event_form(form):
    data = {k: form.get(k, "").strip() for k in ("title", "description", "category", "event_date", "event_time", "location")}
    errors = []
    if not data["title"]:
        errors.append("Title is required.")
    if not data["location"]:
        errors.append("Location is required.")
    if data["category"] not in CATEGORIES:
        errors.append("Choose a valid category.")
    try:
        datetime.strptime(data["event_date"], "%Y-%m-%d")
    except ValueError:
        errors.append("Enter a valid date.")
    try:
        datetime.strptime(data["event_time"], "%H:%M")
    except ValueError:
        errors.append("Enter a valid start time.")
    try:
        data["capacity"] = int(form.get("capacity", ""))
        if data["capacity"] < 1:
            raise ValueError
    except ValueError:
        errors.append("Capacity must be a whole number of at least 1.")
        data["capacity"] = form.get("capacity", "")
    try:
        data["price"] = float(form.get("price") or 0)
        if data["price"] < 0:
            raise ValueError
    except ValueError:
        errors.append("Price must be 0 or more.")
        data["price"] = form.get("price", "")
    return data, errors


@app.route("/events/new", methods=["GET", "POST"])
def event_new():
    if request.method == "POST":
        data, errors = parse_event_form(request.form)
        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template("event_form.html", event=data, mode="new")
        db = get_db()
        cur = db.execute(
            """INSERT INTO events (title, description, category, event_date, event_time, location, capacity, price)
               VALUES (:title, :description, :category, :event_date, :event_time, :location, :capacity, :price)""",
            data,
        )
        db.commit()
        flash("Event created.", "success")
        return redirect(url_for("event_detail", event_id=cur.lastrowid))
    blank = {"title": "", "description": "", "category": "Meetup", "event_date": "", "event_time": "",
             "location": "", "capacity": 50, "price": 0}
    return render_template("event_form.html", event=blank, mode="new")


@app.route("/events/<int:event_id>")
def event_detail(event_id):
    event = get_event(event_id)
    attendees = get_db().execute(
        """SELECT r.id AS reg_id, r.registered_at, a.id, a.name, a.email, a.phone
           FROM registrations r JOIN attendees a ON a.id = r.attendee_id
           WHERE r.event_id = ? ORDER BY r.id""",
        (event_id,),
    ).fetchall()
    return render_template("event_detail.html", event=event, attendees=attendees)


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def event_edit(event_id):
    event = get_event(event_id)
    if request.method == "POST":
        data, errors = parse_event_form(request.form)
        if not errors and data["capacity"] < event["registered"]:
            errors.append(f"Capacity cannot be lower than the {event['registered']} people already registered.")
        if errors:
            for msg in errors:
                flash(msg, "error")
            data["id"] = event_id
            return render_template("event_form.html", event=data, mode="edit")
        data["id"] = event_id
        db = get_db()
        db.execute(
            """UPDATE events SET title=:title, description=:description, category=:category,
               event_date=:event_date, event_time=:event_time, location=:location,
               capacity=:capacity, price=:price WHERE id=:id""",
            data,
        )
        db.commit()
        flash("Event updated.", "success")
        return redirect(url_for("event_detail", event_id=event_id))
    return render_template("event_form.html", event=event, mode="edit")


@app.post("/events/<int:event_id>/delete")
def event_delete(event_id):
    get_event(event_id)
    db = get_db()
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()
    flash("Event deleted.", "success")
    return redirect(url_for("events_list"))


@app.post("/events/<int:event_id>/register")
def event_register(event_id):
    """Register someone for an event. Creates the attendee if the email is new."""
    event = get_event(event_id)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    if not name or not EMAIL_RE.match(email):
        flash("Enter a name and a valid email address.", "error")
        return redirect(url_for("event_detail", event_id=event_id))

    db = get_db()
    row = db.execute("SELECT id FROM attendees WHERE email = ?", (email,)).fetchone()
    if row:
        attendee_id = row["id"]
    else:
        attendee_id = db.execute(
            "INSERT INTO attendees (name, email, phone) VALUES (?, ?, ?)", (name, email, phone)
        ).lastrowid
        db.commit()
    ok, msg = add_registration(db, event, attendee_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("event_detail", event_id=event_id))


@app.post("/registrations/<int:reg_id>/cancel")
def registration_cancel(reg_id):
    db = get_db()
    db.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    db.commit()
    flash("Registration cancelled.", "success")
    return redirect(safe_next(url_for("events_list")))


# --------------------------------------------------------------------------
# Attendees
# --------------------------------------------------------------------------
@app.route("/attendees")
def attendees_list():
    q = request.args.get("q", "").strip()
    params, where = [], ""
    if q:
        where = "WHERE a.name LIKE ? OR a.email LIKE ?"
        params = [f"%{q}%"] * 2
    attendees = get_db().execute(
        f"""SELECT a.*, COUNT(r.id) AS events_count
            FROM attendees a LEFT JOIN registrations r ON r.attendee_id = a.id
            {where} GROUP BY a.id ORDER BY a.name COLLATE NOCASE""",
        params,
    ).fetchall()
    return render_template("attendees.html", attendees=attendees, q=q)


def parse_attendee_form(form):
    data = {k: form.get(k, "").strip() for k in ("name", "email", "phone")}
    data["email"] = data["email"].lower()
    errors = []
    if not data["name"]:
        errors.append("Name is required.")
    if not EMAIL_RE.match(data["email"]):
        errors.append("Enter a valid email address.")
    return data, errors


@app.route("/attendees/new", methods=["GET", "POST"])
def attendee_new():
    if request.method == "POST":
        data, errors = parse_attendee_form(request.form)
        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template("attendee_form.html", attendee=data, mode="new")
        db = get_db()
        try:
            cur = db.execute("INSERT INTO attendees (name, email, phone) VALUES (:name, :email, :phone)", data)
            db.commit()
        except sqlite3.IntegrityError:
            flash("An attendee with that email already exists.", "error")
            return render_template("attendee_form.html", attendee=data, mode="new")
        flash("Attendee added.", "success")
        return redirect(url_for("attendee_detail", attendee_id=cur.lastrowid))
    return render_template("attendee_form.html", attendee={"name": "", "email": "", "phone": ""}, mode="new")


@app.route("/attendees/<int:attendee_id>")
def attendee_detail(attendee_id):
    attendee = get_attendee(attendee_id)
    db = get_db()
    today = date.today().isoformat()
    registrations = db.execute(
        """SELECT r.id AS reg_id, e.id AS event_id, e.title, e.event_date, e.event_time, e.location
           FROM registrations r JOIN events e ON e.id = r.event_id
           WHERE r.attendee_id = ? ORDER BY e.event_date DESC""",
        (attendee_id,),
    ).fetchall()
    open_events = db.execute(
        """SELECT e.id, e.title, e.event_date FROM events e
           WHERE e.event_date >= ?
             AND e.id NOT IN (SELECT event_id FROM registrations WHERE attendee_id = ?)
           ORDER BY e.event_date""",
        (today, attendee_id),
    ).fetchall()
    return render_template("attendee_detail.html", attendee=attendee, registrations=registrations, open_events=open_events)


@app.route("/attendees/<int:attendee_id>/edit", methods=["GET", "POST"])
def attendee_edit(attendee_id):
    attendee = get_attendee(attendee_id)
    if request.method == "POST":
        data, errors = parse_attendee_form(request.form)
        if errors:
            for msg in errors:
                flash(msg, "error")
            data["id"] = attendee_id
            return render_template("attendee_form.html", attendee=data, mode="edit")
        data["id"] = attendee_id
        db = get_db()
        try:
            db.execute("UPDATE attendees SET name=:name, email=:email, phone=:phone WHERE id=:id", data)
            db.commit()
        except sqlite3.IntegrityError:
            flash("Another attendee already uses that email.", "error")
            return render_template("attendee_form.html", attendee=data, mode="edit")
        flash("Attendee updated.", "success")
        return redirect(url_for("attendee_detail", attendee_id=attendee_id))
    return render_template("attendee_form.html", attendee=attendee, mode="edit")


@app.post("/attendees/<int:attendee_id>/delete")
def attendee_delete(attendee_id):
    get_attendee(attendee_id)
    db = get_db()
    db.execute("DELETE FROM attendees WHERE id = ?", (attendee_id,))
    db.commit()
    flash("Attendee deleted.", "success")
    return redirect(url_for("attendees_list"))


@app.post("/attendees/<int:attendee_id>/register")
def attendee_register(attendee_id):
    get_attendee(attendee_id)
    try:
        event_id = int(request.form.get("event_id", ""))
    except ValueError:
        flash("Choose an event.", "error")
        return redirect(url_for("attendee_detail", attendee_id=attendee_id))
    event = get_event(event_id)
    ok, msg = add_registration(get_db(), event, attendee_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("attendee_detail", attendee_id=attendee_id))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


init_db()

# Demo hosting: free hosts wipe the database file on restart, so optionally
# refill it with sample data whenever it is empty.
if os.environ.get("AUTO_SEED") == "1":
    from seed import seed_if_empty

    seed_if_empty()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
