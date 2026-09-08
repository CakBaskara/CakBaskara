# Profile art — cara pakai

Semua gerak hidup di dalam file SVG. GitHub membuang `<script>` dan hampir semua
CSS inline dari README, tapi tetap merender SVG yang dipasang lewat `<img>`
berikut animasinya (CSS keyframes + SMIL). Jadi tidak ada layanan pihak ketiga
di sini — semua digenerate sendiri di repo ini.

## 1. Isi config.json

```json
{
  "username": "usernamekamu",       <- dipakai untuk scrape kalender kontribusi
  "name": "Nama Kamu",
  "handle": "kamu@github",          <- teks prompt palsu di pojok tiap kartu
  "info": [["Now", "..."], ...],    <- isi kartu neofetch, bebas tambah/kurang
  "theme": { ... }                  <- warna
}
```

## 2. Generate

```bash
pip install -r requirements.txt

python build.py                    # semua aset, potret pakai placeholder
python build.py --photo foto.jpg   # pakai foto sungguhan
```

Skrip satuan kalau mau atur satu-satu:

| Skrip | Hasil |
|---|---|
| `scripts/fetch_contributions.py` | `assets/contributions.json` (scrape, tanpa token) |
| `scripts/render_heatmap_svg.py` | `assets/contrib-heatmap.svg` |
| `scripts/make_info_card.py` | `assets/info-card.svg` |
| `scripts/make_ascii_svg.py` | `assets/portrait-ascii.svg` |

Opsi potret: `--gamma 1.4` (atur terang/gelap), `--invert` (foto berlatar gelap),
`--cols 90` (lebih detail). Foto yang bagus buat ASCII = subjek terang, latar
polos, kontras tinggi. Kalau latarnya ramai, hapus dulu backgroundnya di editor
foto — hasilnya jauh lebih kebaca.

Set `STATIC=1` untuk merender versi tanpa animasi (berguna buat preview/thumbnail):

```bash
STATIC=1 python build.py
```

## 3. Taruh di repo profil

Repo profil GitHub itu repo yang namanya **sama persis dengan usernamemu**
(`usernamekamu/usernamekamu`), public, dengan `README.md` di root.

```bash
git init && git add . && git commit -m "profile art"
git branch -M main
git remote add origin https://github.com/USERNAME/USERNAME.git
git push -u origin main
```

## 4. Otomatis update tiap hari

`.github/workflows/update-profile-art.yml` sudah siap: jalan tiap hari 06:17 UTC,
regenerate heatmap + kartu info, lalu commit sendiri kalau ada perubahan.
Potret ASCII tidak ikut diregenerate (fotonya kan tidak berubah), jadi commit
hasil `make_ascii_svg.py` sekali saja secara manual.

Yang perlu dicek sekali di repo: **Settings → Actions → General → Workflow
permissions → Read and write permissions**, supaya bot boleh commit.

## Catatan soal README

- GitHub membuang atribut `style=` di README — jarak antar elemen atur pakai `<br>`.
- Pakai `<h3>` bukan `#`, supaya tidak muncul garis bawah.
- Lebar sengaja dibuat 370 + 490 = 860 biar sejajar dengan heatmap.
- Animasi SVG jalan sekali tiap kali gambar dimuat ulang (bukan loop).
