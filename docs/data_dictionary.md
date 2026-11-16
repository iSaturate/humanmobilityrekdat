# Kamus data dan kontrak transformasi

Semua tabel olahan berada di `data/processed/`. Tanggal/jam adalah lokal WIB, tidak dikonversi ke UTC. Kode wilayah dipertahankan sebagai string. Periode terpilih 2021-12-01 hingga 2022-04-30, inklusif.

## Grain dan natural key

| Tabel | Satu baris mewakili | Natural key |
|---|---|---|
| `presence_hourly_clean.csv` | Slot kapanewon-jam terpublikasi | `kapanewon_code, date, hour` |
| `kapanewon_daily.csv` | Kapanewon-hari, termasuk unit-hari tidak terpublikasi | `kapanewon_code, date` |
| `diy_daily.csv` | Hari provinsi DIY, agregasi JogjaPulse | `date` |
| `regency_daily.csv` | Kabupaten/kota-hari | `kab_code, date` |
| `google_diy_daily.csv` | Hari provinsi DIY, Google | `date` |
| `integrated_daily.csv` | Hari provinsi DIY, kedua sumber | `date` |
| `od_monthly_clean.csv` | Pasangan asal-tujuan bulanan terpublikasi | `month, origin_code, dest_code` |

## Kolom kehadiran dan kalender

| Kolom | Definisi / satuan |
|---|---|
| `kab_code`, `kab_kota` | Kode/nama kabupaten atau kota DIY; kode string seperti `34.01` |
| `kapanewon_code`, `kapanewon` | Kode/nama kapanewon; 78 unit pada record v1 |
| `date`, `hour` | Tanggal `YYYY-MM-DD`; jam 0–23, WIB |
| `n_maids` | Perangkat unik dalam **satu slot** lokasi-jam, minimal 5 pada baris terpublikasi |
| `n_pings` | Jumlah ping dalam slot yang sama; bukan perjalanan |
| `published_device_presence_units` | Jumlah `n_maids` pada slot terpublikasi; **tidak unik lintas lokasi/jam** |
| `published_pings` | Jumlah ping dari slot terpublikasi |
| `published_hours` | Jumlah jam terpublikasi pada kapanewon-hari, 0–24 |
| `published_slots` | Jumlah slot kapanewon-jam terpublikasi pada provinsi/kabupaten-hari |
| `coverage_pct` | Slot terpublikasi / kerangka slot ×100; 24 per kapanewon, 78×24 per provinsi, jumlah kapanewon×24 per kabupaten |
| `complete_day` | True hanya jika seluruh 24 jam kapanewon-hari terpublikasi |
| `complete_kapanewon_days` | Jumlah kapanewon dengan 24 jam lengkap pada tanggal itu |
| `daytime_presence_units` | Jumlah `n_maids` pada jam 08–17 WIB terpublikasi; tidak unik sepanjang siang |
| `daytime_share_pct` | Pada unit-hari lengkap: 100 × unit kehadiran 08–17 / unit kehadiran 00–23. Pada DIY: rata-rata pangsa kapanewon-hari lengkap dengan bobot sama |
| `hourly_share_pct` | Pada unit-hari lengkap: 100 × n_maids jam tersebut / total unit kehadiran hari itu; lainnya NA |
| `ping_intensity` | published_pings / published_device_presence_units; diagnostik aktivitas pencatatan, bukan intensitas perjalanan |
| `published_presence_share_pct` | Unit kehadiran kabupaten-hari / total unit kehadiran DIY pada tanggal itu ×100; bukan pangsa populasi |
| `weekday` | 0=Senin sampai 6=Minggu |
| `day_type` | Weekday (Senin–Jumat) atau Weekend (Sabtu–Minggu); tidak memakai kalender hari libur |
| `sample_regime` | Desember; 1 Januari–15 Februari; 16 Februari–30 April. Berdasarkan batas perubahan sampel di dokumentasi sumber |
| `known_anomaly` | True pada 8 Maret 2022; dikecualikan dari profil jam/korelasi/temuan weekday-weekend |
| `reduced_quality_period` | Flag tanggal Maret–April untuk kehati-hatian; flag kualitas resmi `reduced_quality` pada OD dipertahankan terpisah |

## Google

Kolom `google_{category}_pct` mempertahankan perubahan persen dari baseline penerbit. Kategori: `retail_and_recreation`, `grocery_and_pharmacy`, `parks`, `transit_stations`, `workplaces`, `residential`.

Baseline merupakan median hari sejenis dalam 3 Januari–6 Februari 2020, bukan satu nilai yang sama untuk semua hari. Data berkaitan dengan kunjungan/durasi; residential terutama durasi. Tidak ada konversi menjadi jumlah orang, imputasi, atau penjumlahan antar-kategori.

Filter: `country_region_code == ID`, `iso_3166_2_code == ID-YO`, `sub_region_2` kosong, `metro_area` kosong. Input ekstrak tahunan dapat mencakup tanggal di luar periode; output hanya 151 hari terpilih. Nilai kosong tetap NA.

## OD

Kolom asli: `month`, kode/nama kabupaten dan kapanewon asal/tujuan, `n_maids`, `reduced_quality`. Data asal ditambahkan melalui join many-to-one pada `(month, origin_code)`.

| Kolom tambahan | Definisi |
|---|---|
| `n_homed_maids_daytime` | Perangkat dengan home bulanan di asal yang teramati pada jam siang dalam bulan yang sama; denominator resmi, bukan populasi |
| `visit_share_pct` | 100 × perangkat asal yang teramati di tujuan / n_homed_maids_daytime |
| `inter_kapanewon` | Asal dan tujuan berbeda |

Home bulanan menggunakan aturan malam penerbit. Satu perangkat dapat mengunjungi beberapa tujuan dan hanya dihitung sekali per pasangan-bulan, sehingga **bukan jumlah perjalanan**. Pangsa tidak dijumlahkan lintas tujuan. Denominator kosong tetap NA. Analisis ranking hanya pasangan antar-kapanewon yang terpublikasi pada Desember, Januari, dan Februari; rata-rata tiga pangsa bulanan berbobot sama. Baris Maret–April tetap ada pada tabel, dengan `reduced_quality=True`, tetapi dikecualikan dari ranking.

## Missingness dan bias

Baris tidak terpublikasi tidak dianggap nol. Pada kerangka kapanewon-hari, `published_hours=0` berarti tidak ada jam terpublikasi, sementara hitungan kehadirannya tetap NA. Pangsa siang/hari tidak lengkap tidak dihitung. Unit-hari lengkap tidak menjamin sampel mewakili populasi; wilayah lengkap dapat berubah tiap hari.

Sensitivitas panel tetap hanya menggunakan kapanewon yang lengkap pada semua hari non-anomali (empat pada unduhan yang dianalisis). Anggotanya tersedia di `reports/fixed_panel_members.csv`. Panel ini menahan komposisi geografis tetapi kecil dan tidak representatif DIY. Korelasi utama dan sensitivitas mempertahankan batas interpretasi tersebut.

`reports/correlations.csv` mencatat window, kategori, metode, jumlah pasangan valid, serta Pearson r. Metode: raw; pengurangan rerata kelompok weekday×sample_regime; selisih tujuh hari dengan hari sejenis dan rezim sama. Window: seluruh periode non-anomali, serta sebelum 16 Februari. Nilai kosong/8 Maret dikecualikan; pada selisih tujuh hari kedua endpoint harus valid. Angka ini deskriptif, tanpa p-value atau klaim kausal.

## Provenance dan reproduksi

`reports/data_manifest.json` mencatat URL file, ukuran, SHA-256 lokal, checksum penerbit Zenodo jika tersedia, dan waktu pencatatan UTC. Manifest diperiksa terhadap data lokal sebelum transformasi. Google tidak menyediakan checksum penerbit pada endpoint yang dipakai. `--force` mengunduh ulang; perubahan file lokal tanpa pembaruan manifest ditolak pipeline.

Referensi: [JogjaPulse dan dokumentasinya](https://zenodo.org/records/23157460), [CSV Google](https://www.google.com/covid19/mobility/data_documentation.html), [panduan interpretasi Google](https://support.google.com/covid19-mobility/answer/9824897).
