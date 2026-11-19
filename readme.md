# Anumata Visual

Company profile photography/videography dengan login pengguna dan admin.
Backend: Flask. Database: SQLite lokal. Frontend: HTML, CSS, JavaScript.

## Menjalankan di VS Code (PowerShell)

Buka terminal pada direktori proyek:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Buka http://127.0.0.1:5000. Gunakan server Flask untuk fitur akun; Live Server atau membuka index.html langsung hanya menampilkan profil statis.
Jika belum ada .venv, buat dengan instalasi Python Anda: `python -m venv .venv`.

## Akun pengguna

Klik **Masuk / Daftar**, daftar dengan nama, email, kata sandi 8?128 karakter dan konfirmasi. Semua pendaftaran publik berperan pengguna. Setelah login, pengguna masuk ke `/dashboard` dan bisa melihat profil serta menghubungi tim.

## Membuat admin

Pada terminal kedua, jalankan:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app create-admin
```

Masukkan nama, email, dan kata sandi ketika diminta. Kata sandi disembunyikan. Tidak ada akun atau kata sandi admin bawaan. Admin login melalui formulir yang sama dan diarahkan ke `/admin`. Dashboard admin menampilkan jumlah dan daftar akun; menyediakan panel **Gambar beranda** untuk mengganti atau memulihkan foto utama, portofolio, dan tim. Gambar unggahan disimpan di database SQLite.

## Data dan sesi

Database otomatis dibuat di `instance/anumata.sqlite3`. Kata sandi di-hash menggunakan Werkzeug; cookie tidak berisi kata sandi. Sesi memiliki batas 8 jam dan dihapus dari database saat logout. Form POST memakai token CSRF. Percobaan login gagal dibatasi selama 15 menit. Role selalu diperiksa backend. Database dan secret lokal dikecualikan dari Git. Jangan membagikan folder `instance`.

Untuk hosting HTTPS, set `ANUMATA_HTTPS=1` dan gunakan `ANUMATA_SECRET_KEY` yang acak dan tetap. Server `python app.py` untuk pengembangan lokal; deployment memerlukan WSGI server dan konfigurasi HTTPS. Reset kata sandi dan verifikasi email belum tersedia.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tes memakai database sementara, tanpa mengubah akun asli. Lihat `QA_REPORT.md` untuk hasil dan batas verifikasi.

## Struktur

- `index.html`, `style.css`, `script.js`: company profile dan galeri.
- `app.py`: route, autentikasi, otorisasi, database, CLI admin.
- `templates/`: halaman login, daftar, akun, admin, dan error.
- `assets/`: foto lokal; sebagian foto lain dan Google Fonts membutuhkan internet.
- `tests/`: tes integrasi autentikasi dan aset.
- `backup_sebelum_login/`: salinan empat file awal sebelum perubahan.

Informasi kontak, angka pencapaian, dan foto contoh perlu dikonfirmasi pemilik sebelum dipublikasikan.
