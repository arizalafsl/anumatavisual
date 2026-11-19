import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from io import BytesIO
from pathlib import Path

import click
from flask import (
    Flask, abort, flash, g, redirect, render_template, request,
    send_file, send_from_directory, session, url_for,
)
from jinja2 import ChoiceLoader, DictLoader
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
SESSION_SECONDS = 8 * 60 * 60
ATTEMPT_WINDOW = 15 * 60
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
IMAGE_SLOTS = {
    "hero": "Foto utama",
    "portfolio-concert": "Portofolio – Kerumunan konser",
    "portfolio-wedding": "Portofolio – Pernikahan",
    "portfolio-graduation": "Portofolio – Wisuda",
    "portfolio-event": "Portofolio – Acara",
    "portfolio-performer": "Portofolio – Penampil",
    "portfolio-rings": "Portofolio – Cincin pernikahan",
    "team-arizal": "Tim – Arizal",
    "team-daffa": "Tim – Daffa",
    "team-diva": "Tim – Diva",
}
HOME_IMAGE_PATTERN = re.compile(r'(<img data-home-image="([^"]+)" src=")([^"]+)(")')

SCHEMA = """
CREATE TABLE IF NOT EXISTS home_images (
    slot TEXT PRIMARY KEY,
    image BLOB NOT NULL,
    revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    key TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(key, created_at);
"""


def valid_email(email):
    return len(email) <= 254 and EMAIL_PATTERN.fullmatch(email) is not None


def valid_password(password):
    return 8 <= len(password) <= 128


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def prepare_home_image(upload):
    if not upload or not upload.filename:
        raise ValueError("Pilih gambar yang ingin diunggah.")
    raw = upload.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Ukuran file maksimal 5 MB.")
    try:
        with Image.open(BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Resolusi gambar maksimal 16 megapiksel.")
            if getattr(source, "is_animated", False):
                raise ValueError("Pilih gambar tanpa animasi.")
            with ImageOps.exif_transpose(source) as oriented:
                oriented.thumbnail((2400, 2400))
                mode = "RGBA" if oriented.has_transparency_data else "RGB"
                with oriented.convert(mode) as image, BytesIO() as output:
                    image.save(output, "WEBP", quality=88)
                    return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as error:
        raise ValueError("Gunakan gambar JPG, PNG, atau WebP yang valid.") from error


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        DATABASE=Path(app.instance_path) / "anumata.sqlite3",
        SECRET_KEY=os.environ.get("ANUMATA_SECRET_KEY"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.environ.get("ANUMATA_HTTPS") == "1",
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=SESSION_SECONDS,
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.secret_key:
        instance = Path(app.instance_path)
        instance.mkdir(parents=True, exist_ok=True)
        key_file = instance / "secret.key"
        try:
            with key_file.open("x", encoding="utf-8") as key:
                key.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.secret_key = key_file.read_text(encoding="utf-8").strip()
        if not app.secret_key:
            raise RuntimeError("Isi instance/secret.key atau set ANUMATA_SECRET_KEY.")

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    for css_class in ("nav-cta", "nav-login-mobile"):
        link = f'<a class="{css_class}" href="login.html">Login</a>'
        account_nav = (
            '{% with account_class="' + css_class + '" %}'
            '{% include "account_nav.html" %}{% endwith %}'
        )
        index = index.replace(link, account_nav)
    default_images = {match[2]: match[3] for match in HOME_IMAGE_PATTERN.finditer(index)}

    def image_source(match):
        prefix, slot, fallback, suffix = match.groups()
        return (
            prefix
            + "{% if home_images.get('" + slot + "') %}"
            + "{{ home_images['" + slot + "'] }}"
            + "{% else %}" + fallback + "{% endif %}"
            + suffix
        )

    index = HOME_IMAGE_PATTERN.sub(image_source, index)
    app.jinja_loader = ChoiceLoader([DictLoader({"index.html": index}), app.jinja_loader])

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    with app.app_context():
        db().executescript(SCHEMA)

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.before_request
    def load_account():
        g.user = None
        token = session.get("account_token")
        if token:
            g.user = db().execute(
                """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
                   WHERE token_hash = ? AND expires_at > ?""",
                (token_hash(token), time.time()),
            ).fetchone()
            if g.user is None:
                session.clear()
        if request.endpoint == "admin_image" and g.user and g.user["role"] == "admin":
            request.max_content_length = MAX_IMAGE_BYTES + 16 * 1024
        if request.method == "POST":
            expected = session.get("csrf_token")
            supplied = request.form.get("csrf_token", "")
            if not expected or not supplied.isascii() or not hmac.compare_digest(expected, supplied):
                abort(400, description="Formulir kedaluwarsa. Muat ulang halaman dan coba lagi.")

    @app.context_processor
    def account_context():
        return {"current_user": g.user, "csrf_token": csrf_token}

    @app.after_request
    def protect_account_pages(response):
        if request.endpoint not in {"stylesheet", "javascript", "asset"}:
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/index.html")
    @app.get("/")
    def home():
        return render_template("home.html", home_images=custom_image_urls())

    @app.get("/style.css")
    def stylesheet():
        return send_from_directory(ROOT, "style.css")

    @app.get("/script.js")
    def javascript():
        return send_from_directory(ROOT, "script.js")

    @app.get("/assets/<path:filename>")
    def asset(filename):
        return send_from_directory(ROOT / "assets", filename)

    def custom_image_urls():
        return {
            row["slot"]: url_for("home_image", slot=row["slot"], v=row["revision"])
            for row in db().execute("SELECT slot, revision FROM home_images")
        }

    @app.get("/gambar-beranda/<slot>")
    def home_image(slot):
        if slot not in default_images:
            abort(404)
        row = db().execute("SELECT image FROM home_images WHERE slot = ?", (slot,)).fetchone()
        if row is None:
            abort(404)
        return send_file(BytesIO(row["image"]), mimetype="image/webp")

    def account_destination():
        return url_for("admin" if g.user["role"] == "admin" else "dashboard")

    def auth_page(mode, error=None, status=200):
        return render_template("auth.html", mode=mode, error=error), status

    @app.get("/register.html")
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(account_destination())
        if request.method == "GET":
            return auth_page("register")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not 2 <= len(name) <= 80 or not valid_email(email):
            return auth_page("register", "Periksa nama dan alamat email Anda.", 400)
        if not valid_password(password) or password != request.form.get("confirm_password"):
            return auth_page("register", "Gunakan 8–128 karakter dan pastikan kedua kata sandi sama.", 400)
        try:
            with db() as connection:
                connection.execute(
                    "INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return auth_page("register", "Email tersebut sudah digunakan.", 400)
        return redirect(url_for("login", registered=1))

    dummy_hash = generate_password_hash(secrets.token_urlsafe(32))

    @app.get("/login.html")
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(account_destination())
        if request.method == "GET":
            return auth_page("login")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        now = time.time()
        key = token_hash(f"{request.remote_addr}:{email}")
        with db() as connection:
            connection.execute("DELETE FROM attempts WHERE created_at <= ?", (now - ATTEMPT_WINDOW,))
            attempts = connection.execute("SELECT COUNT(*) FROM attempts WHERE key = ?", (key,)).fetchone()[0]
            if attempts >= 5:
                return auth_page("login", "Terlalu banyak percobaan. Coba lagi dalam 15 menit.", 429)
            connection.execute("INSERT INTO attempts VALUES (?, ?)", (key, now))
        user = db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        stored_hash = user["password_hash"] if user else dummy_hash
        if not 1 <= len(password) <= 128 or not check_password_hash(stored_hash, password) or user is None:
            return auth_page("login", "Email atau kata sandi salah.", 400)
        token = secrets.token_urlsafe(32)
        with db() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            inserted = connection.execute(
                """INSERT INTO sessions(token_hash, user_id, expires_at)
                   SELECT ?, id, ? FROM users WHERE id = ? AND password_hash = ? AND email = ?""",
                (token_hash(token), now + SESSION_SECONDS, user["id"], stored_hash, user["email"]),
            )
            if not inserted.rowcount:
                return auth_page("login", "Data akun berubah. Silakan coba lagi.", 400)
            connection.execute("DELETE FROM attempts WHERE key = ?", (key,))
        session.clear()
        session["account_token"] = token
        session.permanent = True
        g.user = user
        return redirect(account_destination())

    @app.post("/logout")
    def logout():
        token = session.get("account_token")
        if token:
            with db() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        session.clear()
        return redirect(url_for("login", logged_out=1))

    @app.get("/dashboard")
    def dashboard():
        if not g.user:
            return redirect(url_for("login"))
        return render_template("dashboard.html", users=None)

    @app.get("/admin")
    def admin():
        if not g.user:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            abort(403)
        users = db().execute("SELECT name, email, role, created_at FROM users ORDER BY id DESC").fetchall()
        image_urls = custom_image_urls()
        images = [
            (slot, label, image_urls.get(slot, default_images[slot]), slot in image_urls)
            for slot, label in IMAGE_SLOTS.items() if slot in default_images
        ]
        return render_template("dashboard.html", users=users, images=images)

    @app.post("/admin/gambar/<slot>")
    def admin_image(slot):
        if not g.user:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            abort(403)
        if slot not in IMAGE_SLOTS or slot not in default_images:
            abort(404)

        action = request.form.get("action")
        if action == "reset":
            with db() as connection:
                connection.execute("DELETE FROM home_images WHERE slot = ?", (slot,))
            flash("Gambar bawaan dipulihkan.", "success")
        elif action == "upload":
            upload = request.files.get("image")
            try:
                data = prepare_home_image(upload)
            except ValueError as error:
                flash(str(error), "error")
            else:
                with db() as connection:
                    connection.execute(
                        """INSERT INTO home_images(slot, image, revision) VALUES (?, ?, ?)
                           ON CONFLICT(slot) DO UPDATE SET image = excluded.image, revision = excluded.revision""",
                        (slot, data, hashlib.sha256(data).hexdigest()[:16]),
                    )
                flash("Gambar beranda berhasil diganti.", "success")
        else:
            abort(400)
        return redirect(url_for("admin", _anchor="image-" + slot))

    @app.route("/profil", methods=["GET", "POST"])
    def profile():
        if not g.user:
            return redirect(url_for("login"))
        if request.method == "GET":
            return render_template("profile.html")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        current = request.form.get("current_password", "")
        password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        def invalid(message):
            return render_template("profile.html", error=message), 400

        if not 2 <= len(name) <= 80 or not valid_email(email):
            return invalid("Periksa nama dan alamat email Anda.")
        if (password or confirm) and (not valid_password(password) or password != confirm):
            return invalid("Gunakan 8–128 karakter dan pastikan kedua kata sandi baru sama.")
        old_hash = g.user["password_hash"]
        if not 1 <= len(current) <= 128 or not check_password_hash(old_hash, current):
            return invalid("Kata sandi saat ini salah.")
        new_hash = generate_password_hash(password) if password else old_hash
        active_token_hash = token_hash(session["account_token"])
        try:
            with db() as connection:
                updated = connection.execute(
                    """UPDATE users SET name = ?, email = ?, password_hash = ?
                       WHERE id = ? AND password_hash = ? AND name = ? AND email = ?
                         AND EXISTS (SELECT 1 FROM sessions WHERE token_hash = ? AND expires_at > ?)""",
                    (name, email, new_hash, g.user["id"], old_hash, g.user["name"], g.user["email"],
                     active_token_hash, time.time()),
                )
                if not updated.rowcount:
                    return invalid("Akun atau sesi berubah. Muat ulang halaman dan coba lagi.")
                if password:
                    connection.execute(
                        "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                        (g.user["id"], active_token_hash),
                    )
        except sqlite3.IntegrityError:
            return invalid("Email tersebut sudah digunakan.")
        flash("Perubahan profil tersimpan.")
        return redirect(url_for("profile"))

    for code in (400, 403, 404, 405, 413):
        app.register_error_handler(code, lambda error: (render_template("error.html", error=error), error.code))

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Nama")
    @click.option("--email", prompt="Email")
    def create_admin(name, email):
        name, email = name.strip(), email.strip().lower()
        if not 2 <= len(name) <= 80 or not valid_email(email):
            raise click.ClickException("Nama atau email tidak valid.")
        password = click.prompt("Kata sandi", hide_input=True, confirmation_prompt=True)
        if not valid_password(password):
            raise click.ClickException("Gunakan 8–128 karakter.")
        try:
            with db() as connection:
                connection.execute(
                    "INSERT INTO users(name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                    (name, email, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError as error:
            raise click.ClickException("Email tersebut sudah digunakan.") from error
        click.echo("Akun admin berhasil dibuat.")

    return app


if __name__ == "__main__":
    create_app().run()
