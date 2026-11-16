# Human Mobility in Yogyakarta

Data engineering, analytics, dan visualization untuk mobilitas DIY, menggunakan **dua sumber independen**:

1. **JogjaPulse**, Widyawan et al. (2026), [Zenodo record v1](https://doi.org/10.5281/zenodo.23157460), CC BY 4.0. Kehadiran perangkat per kapanewon-jam dan kunjungan asal–tujuan bulanan.
2. **Google LLC, Google COVID-19 Community Mobility Reports**, [sumber](https://www.google.com/covid19/mobility/) dan [dokumentasi](https://www.google.com/covid19/mobility/data_documentation.html). Ekstrak Indonesia 2021/2022, difilter ke provinsi `ID-YO`.

Periode integrasi: **1 Desember 2021–30 April 2022**, 151 hari lokal WIB. Cuaca dan kalender libur tidak termasuk lingkup implementasi ini. Beberapa CSV JogjaPulse tetap dihitung sebagai satu sumber.

## Hasil yang bisa ditinjau

- [Notebook yang sudah dieksekusi](notebooks/human_mobility_analysis.ipynb): proses, tabel, enam grafik, pembahasan, dan sumber.
- [Temuan dan keterbatasan](reports/findings.md), [audit kualitas](reports/data_quality.json), [provenance dan checksum](reports/data_manifest.json).
- [Preview integrasi 151 hari](reports/integrated_daily_preview.csv), [korelasi dan sensitivitas periode](reports/correlations.csv), [sensitivitas panel wilayah tetap](reports/fixed_panel_correlations.csv).
- [Kamus data dan keputusan transformasi](docs/data_dictionary.md).

Hasil diperoleh dari data asli: 230.418 baris kapanewon-jam, 78 kapanewon, serta Google DIY. Raw/processed CSV disimpan lokal dan diabaikan Git; notebook dengan output, grafik, dan laporan ringkas disimpan agar bisa ditinjau tanpa mengunduh ulang.

## Menjalankan di Windows (PowerShell)

Gunakan **Python 3.12**. Dari root repo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/run_project.py
```

Perintah terakhir mengunduh/memverifikasi dua sumber, membentuk notebook, lalu menjalankan semua sel menggunakan interpreter yang sama. Kernel sementara tidak dipasang secara permanen ke profil pengguna. Output notebook, grafik, dan laporan diperbarui; simpan perubahan manual pada notebook sebelum regenerasi, karena `create_notebook.py` adalah sumber notebook yang akan menimpanya.

Jika data dan manifest sudah diunduh, proses bisa dijalankan tanpa jaringan:

```powershell
.\.venv\Scripts\python.exe src/run_project.py --offline
```

Atau jalankan tahap terpisah:

```powershell
.\.venv\Scripts\python.exe src/download_data.py
.\.venv\Scripts\python.exe src/pipeline.py
.\.venv\Scripts\python.exe src/analysis.py
```

Notebook dapat dibuka di VS Code/Jupyter dengan memilih environment `.venv`, lalu **Run All**. JupyterLab/server UI tidak dibutuhkan untuk runner otomatis ini. Di Linux/macOS, ganti `.venv\Scripts\python.exe` dengan `.venv/bin/python`.

Downloader memakai file sementara, retry, cache, checksum penerbit Zenodo, dan hash SHA-256 seluruh input. Google tidak menyediakan checksum penerbit di endpoint CSV; SHA-256 lokal mencatat versi yang dipakai. Pipeline memverifikasi hash manifest sebelum transformasi. Gunakan `python src/download_data.py --force` untuk mengunduh ulang sumber. Kegagalan download/validasi menghentikan proses; tidak ada fallback ke data sintetis.

## Keputusan analisis

- Duplikasi persis dihapus dengan audit; konflik natural key, schema, kode wilayah, nilai tak valid, tanggal hilang, dan join yang gagal akan menghentikan proses.
- Integrasi menggunakan **satu baris per tanggal provinsi**, tanpa menjumlahkan baris provinsi dan subwilayah Google.
- Kehadiran perangkat yang dijumlahkan lintas jam/lokasi disebut **unit kehadiran**, bukan perangkat unik, orang, atau perjalanan.
- Slot yang tidak terpublikasi tetap missing; tidak diisi nol. Pangsa siang dan profil jam hanya memakai kapanewon-hari dengan 24 jam lengkap.
- Perubahan sampel 1 Januari/16 Februari dan anomali 8 Maret ditandai. Analisis OD dibatasi Desember–Februari; Maret–April ditandai kualitas lebih rendah.
- Hubungan kedua sumber diuji secara deskriptif menggunakan nilai mentah, penyesuaian hari × rezim sampel, dan selisih 7 hari. Tersedia sensitivitas periode sebelum 16 Februari serta panel empat wilayah yang lengkap pada seluruh hari non-anomali. Panel kecil tersebut juga tidak mewakili DIY.
- Normalisasi tidak menghilangkan bias komposisi. Tidak ada klaim kausalitas, validasi jumlah perjalanan, atau signifikansi statistik.

## Struktur

```text
src/download_data.py       download atomik, verifikasi, manifest sumber
src/pipeline.py            cleaning, validasi, agregasi, integrasi
src/analysis.py            analisis, ekspor grafik dan laporan
src/create_notebook.py     sumber notebook dengan narasi berbahasa Indonesia
src/run_project.py         runner download + eksekusi notebook
notebooks/                notebook dengan output yang sudah dieksekusi
data/raw/                 input asli dan manifest lokal (git-ignored)
data/processed/           tujuh tabel olahan (git-ignored)
figures/                  enam grafik PNG
reports/                  audit, temuan, tabel ringkas, provenance, environment
docs/                     kamus data
tests/                    regresi asumsi data dan keamanan cache unduhan
```

## Verifikasi

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tes memakai fixture kecil offline untuk memeriksa duplikasi, suppression, filter provinsi, flag kualitas, serta file unduhan yang gagal checksum. Pemeriksaan data asli dijalankan dalam pipeline dan seluruh sel notebook dieksekusi oleh runner. Versi environment eksekusi dicatat di `reports/environment.json`.
