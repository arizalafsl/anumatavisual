# Laporan QA ? Anumata Visual

Tanggal: 15 November 2026. Lingkup: website lokal, login pengguna/admin, navigasi dan aset.

## Hasil verifikasi

**Lulus: 8 tes integrasi otomatis** (`python -m unittest discover -s tests -v`). Tes menggunakan database sementara.

| Skenario | Hasil |
| --- | --- |
| Registrasi, hashing kata sandi, login, profil, logout | Lulus |
| Pendaftaran dengan role admin tetap menjadi pengguna | Lulus |
| Pengguna biasa membuka /admin | Ditolak 403 |
| Pengunjung membuka /admin atau /dashboard | Dialihkan ke login |
| Cookie sesi lama dipakai kembali setelah logout | Ditolak |
| Sesi melewati waktu kedaluwarsa | Ditolak |
| CSRF hilang, palsu, atau berisi Unicode | Ditolak 400 |
| Email tidak valid/duplikat, kata sandi pendek, konfirmasi berbeda | Ditolak |
| Percobaan login gagal melewati batas | Dibatasi 429 |
| Pembuatan admin lewat CLI dan login admin | Lulus |
| Nama pengguna berisi HTML/script di dashboard admin | Di-escape |
| Source backend, database, secret, folder cadangan melalui HTTP | Tidak tersedia 404 |
| Aset lokal, tujuan anchor, ID halaman | Lulus |

Smoke test server HTTP nyata: `/`, `/login`, `/register`, `/style.css`, `/script.js`, `/assets/hero.jpeg` mengembalikan 200. Server pengujian dihentikan setelah selesai.

## Perbaikan

- Menambahkan backend Flask, database SQLite, registrasi, login, logout, dan pemeriksaan role pada server.
- Sesi dibatasi 8 jam, dapat dicabut saat logout; form POST memakai CSRF; login gagal dibatasi.
- Admin dibuat melalui CLI tanpa kredensial bawaan. Dashboard menampilkan ringkasan dan daftar akun; pengguna memiliki halaman profil sendiri.
- Navigasi menampilkan Masuk/Daftar, Akun saya, atau Dashboard admin sesuai sesi.
- Galeri dapat diaktifkan dengan Enter/Space; lightbox mengelola fokus, Escape, dan memblokir interaksi latar.
- Filter memakai aria-pressed; tombol menu memakai aria-controls dan status yang sesuai; menu tertutup tidak menerima fokus.
- Konten tetap terlihat jika JavaScript tidak tersedia; menghormati preferensi pengurangan gerak.
- Menambahkan skip link, fokus keyboard, rel pada tautan eksternal, dan memperbaiki jumlah layanan dari 3 menjadi 4.
- Memperbarui dokumentasi dan mencadangkan empat file awal di backup_sebelum_login.

## Batas verifikasi dan lingkup

Tidak tersedia alat browser interaktif dalam sesi ini. Tampilan desktop/mobile, fokus keyboard aktual, dan perilaku JavaScript belum diuji di browser; perubahan tersebut ditinjau dari kode. Foto eksternal dan Google Fonts memerlukan internet dan belum diverifikasi ketersediaannya. Data pencapaian dan kontak perlu dikonfirmasi pemilik.

Fitur saat ini belum mencakup CMS, booking, reset kata sandi, atau verifikasi email. Server Flask bawaan untuk pengembangan lokal. Untuk publikasi diperlukan server WSGI dan HTTPS; set ANUMATA_HTTPS=1 dan secret tetap melalui ANUMATA_SECRET_KEY. Pembatasan login menggunakan SQLite dan belum ditujukan untuk deployment terdistribusi.
