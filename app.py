from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import hashlib
import os

app = Flask(__name__)

# Password handling: store only SHA-256 hashes.
# Preferred: set the environment variable `SONG_CATALOG_PASSWORD_HASH` to the
# hex SHA-256 hash of the password. As a convenience you may set
# `SONG_CATALOG_PASSWORD` (plain) and the app will compute the hash at startup.
# If neither is set, a default hash for the original development password is
# used (warning printed) — change in production.
PASSWORD_HASH = os.environ.get("SONG_CATALOG_PASSWORD_HASH")
if not PASSWORD_HASH:
    plain = os.environ.get("SONG_CATALOG_PASSWORD")
    print(plain)
    if plain:
        PASSWORD_HASH = hashlib.sha256(plain.encode()).hexdigest()
    else:
        # Fallback: hash of the original dev password.
        # This keeps comparisons as hashes (no plaintext comparison), but
        # you should override with an env var in real deployments.
        PASSWORD_HASH = "11fe08866b4c8d56a96799c1f2487fbbf6e84928e2212e59b716bfd69b1b6ec8"
        print("Warning: using default password hash. Please set SONG_CATALOG_PASSWORD_HASH environment variable.")

# Version loading
try:
    with open("version.txt", "r") as f:
        APP_VERSION = f.read().strip()
except FileNotFoundError:
    APP_VERSION = "unknown"

# -------------------------------
# Database Setup
# -------------------------------
def init_db():
    with sqlite3.connect("songs.db") as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            artist TEXT,
            genre TEXT,
            tuning TEXT,
            link TEXT,
            note TEXT
        )
        """)

init_db()

# -------------------------------
# Routes
# -------------------------------
@app.route("/")
def index():
    search = request.args.get("search", "")
    genre = request.args.get("genre", "")
    tuning = request.args.get("tuning", "")
    with sqlite3.connect("songs.db") as conn:
        conn.row_factory = sqlite3.Row

        # Fetch distinct genres and tunings for the filter dropdowns
        genres = [r[0] for r in conn.execute(
            "SELECT DISTINCT genre FROM songs WHERE genre IS NOT NULL AND genre != '' ORDER BY genre"
        ).fetchall()]
        tunings = [r[0] for r in conn.execute(
            "SELECT DISTINCT tuning FROM songs WHERE tuning IS NOT NULL AND tuning != '' ORDER BY tuning"
        ).fetchall()]

        # Build query with optional filters
        query = "SELECT * FROM songs"
        conditions = []
        params = []
        if search:
            conditions.append("(name LIKE ? OR artist LIKE ? OR genre LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if genre:
            conditions.append("genre = ?")
            params.append(genre)
        if tuning:
            conditions.append("tuning = ?")
            params.append(tuning)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        rows = conn.execute(query, params).fetchall()

    return render_template("index.html", songs=rows, search=search,
                           genres=genres, tunings=tunings,
                           selected_genre=genre, selected_tuning=tuning,
                           app_version=APP_VERSION)

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        password = request.form.get("password", "")
        if not password:
            return "Unauthorized", 403
        # Compare SHA-256 hash of submitted password to stored hash
        if hashlib.sha256(password.encode()).hexdigest() != PASSWORD_HASH:
            return "Unauthorized", 403

        data = (
            request.form["name"],
            request.form["artist"],
            request.form["genre"],
            request.form["tuning"],
            request.form["link"],
            request.form["note"]
        )
        with sqlite3.connect("songs.db") as conn:
            conn.execute(
                "INSERT INTO songs (name, artist, genre, tuning, link, note) VALUES (?, ?, ?, ?, ?, ?)",
                data
            )
        return redirect(url_for("index"))
    return render_template("add.html")

@app.route("/delete/<int:song_id>", methods=["POST"])
def delete(song_id):
    password = request.form.get("password", "")
    if not password:
        return "Unauthorized", 403
    if hashlib.sha256(password.encode()).hexdigest() != PASSWORD_HASH:
        return "Unauthorized", 403

    with sqlite3.connect("songs.db") as conn:
        conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
