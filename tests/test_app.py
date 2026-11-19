import re
from contextlib import contextmanager
import sqlite3
import tempfile
import time
import unittest
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from PIL import Image
from app import create_app
from werkzeug.security import check_password_hash, generate_password_hash

class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.database, "SECRET_KEY": "test-only-secret"})
        self.client = self.app.test_client()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database)
        try:
            with db:
                yield db
        finally:
            db.close()

    def tearDown(self):
        self.temp.cleanup()

    def csrf(self, client=None, path="/login"):
        client = client or self.client
        response = client.get(path)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def register(self, email="client@example.com", **extra):
        data = {"csrf_token": self.csrf(path="/register"), "name": "Klien Anumata", "email": email,
                "password": "Sandi-klien-123", "confirm_password": "Sandi-klien-123"}
        data.update(extra)
        return self.client.post("/register", data=data)

    def login(self, email="client@example.com", password="Sandi-klien-123"):
        return self.client.post("/login", data={"csrf_token": self.csrf(), "email": email, "password": password})

    def test_registration_login_role_and_logout(self):
        self.assertEqual(self.register(role="admin").status_code, 302)
        with self.connect() as db:
            row = db.execute("SELECT password_hash, role FROM users").fetchone()
        self.assertEqual(row[1], "user")
        self.assertNotEqual(row[0], "Sandi-klien-123")
        self.assertTrue(check_password_hash(row[0], "Sandi-klien-123"))
        self.assertTrue(self.login().location.endswith("/dashboard"))
        page = self.client.get("/dashboard")
        self.assertIn(b"Klien Anumata", page.data)
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.assertIn(b"Akun saya", self.client.get("/").data)
        old_cookie = self.client.get_cookie("session").value
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.post("/logout", data={"csrf_token": self.csrf(path="/dashboard")}).status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        self.client.set_cookie("session", old_cookie)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_validation_and_duplicates(self):
        self.assertEqual(self.register(password="short", confirm_password="short").status_code, 400)
        self.assertEqual(self.register(email="invalid").status_code, 400)
        self.assertEqual(self.register(confirm_password="different").status_code, 400)
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(self.register(email="CLIENT@EXAMPLE.COM").status_code, 400)
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_csrf_and_no_unrestricted_file_server(self):
        self.assertEqual(self.client.post("/register", data={}).status_code, 400)
        self.assertEqual(self.client.post("/login", data={"csrf_token": "fake"}).status_code, 400)
        self.csrf()
        self.assertEqual(self.client.post("/login", data={"csrf_token": "?ASCII"}).status_code, 400)
        for path in ["/app.py", "/instance/anumata.sqlite3", "/instance/secret.key", "/backup_sebelum_login/index.html"]:
            self.assertEqual(self.client.get(path).status_code, 404)
        for path in ["/dashboard", "/admin"]:
            self.assertTrue(self.client.get(path).location.endswith("/login"))

    def test_login_throttle(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong").status_code, 400)
        self.assertEqual(self.login(password="wrong").status_code, 429)

    def test_expired_session(self):
        self.register()
        self.login()
        with self.connect() as db:
            db.execute("UPDATE sessions SET expires_at = ?", (time.time() - 1,))
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_admin_access_and_xss_escape(self):
        with self.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                       ("Admin", "admin@example.com", generate_password_hash("Admin-sandi-123"), "admin"))
        self.register(name="<script>alert(1)</script>")
        response = self.login("admin@example.com", "Admin-sandi-123")
        self.assertTrue(response.location.endswith("/admin"))
        page = self.client.get("/admin")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"client@example.com", page.data)
        self.assertNotIn(b"<script>alert(1)</script>", page.data)
        self.assertIn(b"&lt;script&gt;", page.data)
        self.assertNotIn(b"scrypt:", page.data)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertIn(b"Dashboard admin", self.client.get("/").data)

    def test_admin_cli(self):
        result = self.app.test_cli_runner().invoke(args=["create-admin", "--name", "Admin", "--email", "admin@example.com"], input="Admin-sandi-123\nAdmin-sandi-123\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(self.login("admin@example.com", "Admin-sandi-123").location.endswith("/admin"))

    def test_profile_updates_require_password_and_revoke_other_sessions(self):
        self.assertEqual(self.client.get("/profil").location, "/login")
        self.assertEqual(self.register(email="taken@example.com").status_code, 302)
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(self.login().status_code, 302)

        other_client = self.app.test_client()
        other_login = other_client.post("/login", data={
            "csrf_token": self.csrf(client=other_client),
            "email": "client@example.com",
            "password": "Sandi-klien-123",
        })
        self.assertEqual(other_login.status_code, 302)
        profile_data = {
            "csrf_token": self.csrf(path="/profil"),
            "name": "Nama Baru",
            "email": "baru@example.com",
            "current_password": "Sandi-klien-123",
            "new_password": "Sandi-baru-123",
            "confirm_password": "Sandi-baru-123",
        }
        self.assertEqual(self.client.post("/profil", data={**profile_data, "csrf_token": "invalid"}).status_code, 400)
        self.assertEqual(self.client.post("/profil", data={**profile_data, "current_password": "salah"}).status_code, 400)
        self.assertEqual(self.client.post("/profil", data={**profile_data, "email": "taken@example.com"}).status_code, 400)
        self.assertEqual(self.client.post("/profil", data=profile_data).location, "/profil")
        page = self.client.get("/profil")
        self.assertIn(b"Perubahan profil tersimpan.", page.data)
        self.assertIn(b"baru@example.com", page.data)
        self.assertIn(b"Nama Baru", page.data)
        self.assertEqual(other_client.get("/profil").location, "/login")
        self.assertEqual(self.client.post("/logout", data={"csrf_token": self.csrf(path="/profil")}).status_code, 302)
        self.assertEqual(self.login("baru@example.com").status_code, 400)
        self.assertEqual(self.login("baru@example.com", "Sandi-baru-123").status_code, 302)

    def test_only_admin_can_replace_and_reset_home_image(self):
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(self.login().status_code, 302)
        denied = self.client.post("/admin/gambar/hero", data={
            "csrf_token": self.csrf(path="/profil"), "action": "reset",
        })
        self.assertEqual(denied.status_code, 403)

        admin = self.app.test_client()
        with self.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                       ("Admin", "admin@example.com", generate_password_hash("Admin-sandi-123"), "admin"))
        response = admin.post("/login", data={
            "csrf_token": self.csrf(client=admin),
            "email": "admin@example.com", "password": "Admin-sandi-123",
        })
        self.assertEqual(response.location, "/admin")
        token = self.csrf(client=admin, path="/admin")
        self.assertIn(b"Gambar beranda", admin.get("/admin").data)

        invalid = admin.post("/admin/gambar/hero", data={
            "csrf_token": token, "action": "upload",
            "image": (BytesIO(b"<svg/>"), "file.png"),
        }, follow_redirects=True)
        self.assertIn(b"gambar JPG, PNG, atau WebP yang valid", invalid.data)

        with Image.new("RGB", (32, 18), "white") as image, BytesIO() as upload:
            image.save(upload, "PNG")
            response = admin.post("/admin/gambar/hero", data={
                "csrf_token": token, "action": "upload",
                "image": (BytesIO(upload.getvalue()), "hero.png"),
            })
        self.assertEqual(response.location, "/admin#image-hero")
        public = self.app.test_client()
        self.assertIn(b'src="/gambar-beranda/hero?v=', public.get("/").data)
        result = public.get("/gambar-beranda/hero")
        self.assertEqual(result.mimetype, "image/webp")
        with Image.open(BytesIO(result.data)) as image:
            self.assertEqual(image.size, (32, 18))

        reset = admin.post("/admin/gambar/hero", data={"csrf_token": token, "action": "reset"})
        self.assertEqual(reset.location, "/admin#image-hero")
        self.assertIn(b'src="assets/hero.jpeg"', public.get("/").data)
        self.assertEqual(public.get("/gambar-beranda/hero").status_code, 404)

    def test_home_assets_and_fragments(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        class Collector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.fragments, self.assets = [], [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if "id" in attrs:
                    self.ids.append(attrs["id"])
                if attrs.get("href", "").startswith("#"):
                    self.fragments.append(attrs["href"][1:])
                for key in ("src", "href"):
                    value = attrs.get(key, "")
                    if value.startswith("assets/") or value in ("style.css", "script.js"):
                        self.assets.append("/" + value)
        collector = Collector()
        collector.feed(page.get_data(as_text=True))
        self.assertEqual(len(collector.ids), len(set(collector.ids)))
        self.assertFalse(set(collector.fragments) - set(collector.ids))
        for asset in collector.assets:
            with self.client.get(asset) as response:
                self.assertEqual(response.status_code, 200, asset)
        for path in ["/login", "/register", "/not-found"]:
            self.assertIn(self.client.get(path).status_code, (200, 404))

if __name__ == "__main__":
    unittest.main()
