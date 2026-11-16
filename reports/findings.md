# Hasil analisis mobilitas DIY

Analisis deskriptif dua sumber independen, 1 Desember 2021-30 April 2022 (WIB).
Angka di bawah dihasilkan oleh `src/analysis.py`, bukan ditulis sebelum data diperiksa.

## Data dan validasi

- JogjaPulse: 230,418 baris kapanewon-jam, 78 kapanewon.
- Integrasi dengan Google DIY: 151 hari, satu baris per tanggal; tidak ada tanggal gagal join.
- Duplikasi persis yang dihapus pada presence: 0.
- Cakupan minimum slot kapanewon-jam: 40.5%.
- Kapanewon dengan data 24 jam lengkap per hari: 6-68 dari 78.
- Nilai Google yang kosong tetap kosong; lihat `data_quality.json` untuk rincian per kolom.

## Temuan

1. Pangsa kehadiran siang (08-17 WIB) rata-rata 50.45% pada hari kerja dan 48.84% pada akhir pekan, selisih -1.62 poin persentase. Ini adalah pembagian unit kehadiran sepanjang hari, bukan persentase orang yang bepergian. Angka menggunakan kapanewon-hari lengkap, pembobotan merata per kapanewon dalam hari lalu per hari, dan mengecualikan 8 Maret.
2. Puncak profil jam rata-rata: pukul 12 WIB pada hari kerja dan 18 WIB pada akhir pekan. Komposisi kapanewon lengkap dapat berbeda antarhari, sehingga pola bersifat deskriptif.
3. Korelasi selisih 7 hari dengan nilai absolut terbesar terdapat pada kategori Google **Transit stations**: r = -0.393, n = 128. Pemilihan nilai terbesar dari enam kategori bersifat eksploratif. Bandingkan seluruh kategori, penyesuaian hari/rezim, dan periode sebelum 16 Februari pada `correlations.csv`; jangan menafsirkannya sebagai validasi atau kausalitas.
4. Analisis OD dibatasi Desember-Februari. Grafik merangking rata-rata pangsa kunjungan tiap pasangan asal-tujuan yang terpublikasi pada ketiga bulan. Perangkat yang sama dapat mengunjungi beberapa tujuan; pangsa antar-tujuan tidak dijumlahkan menjadi total perjalanan.
5. Hanya **4 kapanewon** memiliki data 24 jam lengkap pada seluruh 150 hari non-anomali. Pada panel wilayah tetap ini, korelasi selisih 7 hari untuk kategori Transit stations adalah r = -0.395 (n = 128). Bandingkan dengan r = -0.393 pada panel yang berubah. Perbandingan ini memeriksa sensitivitas terhadap komposisi; kemiripan korelasi satu kategori tidak membuktikan tidak ada bias, dan panel kecil ini tidak mewakili seluruh DIY. Anggota dan semua korelasinya disimpan di `fixed_panel_members.csv` dan `fixed_panel_correlations.csv`.

## Batas interpretasi

Jumlah sampel JogjaPulse berubah pada 1 Januari dan 16 Februari; 8 Maret ditandai sebagai anomali. Periode Maret-April memiliki cakupan lebih lemah dan OD ditandai reduced quality. Normalisasi mengurangi pengaruh skala sampel, tetapi tidak menghilangkan bias perubahan komposisi. Slot yang tidak dipublikasikan bukan nol. Cakupan dalam laporan dihitung terhadap kerangka 78 x 24 slot per hari, bukan persentase penduduk yang terwakili.

Google mengukur perubahan kunjungan/durasi relatif terhadap median hari sejenis pada 3 Januari-6 Februari 2020. Residential terutama terkait durasi di rumah. JogjaPulse mengukur kehadiran perangkat dari sumber SDK berbeda. Kedua metrik tidak setara; z-score hanya membantu melihat pola. Selisih 7 hari menjaga kecocokan hari dalam minggu, melewati batas rezim sampel dikecualikan. Autokorelasi, musim, pemilihan sampel dan kategori tidak dikendalikan sepenuhnya; tidak dihitung p-value atau klaim signifikansi.

## Sumber

- Widyawan et al. (2026), JogjaPulse, https://doi.org/10.5281/zenodo.23157460 (CC BY 4.0; lihat metadata record).
- Google LLC, Google COVID-19 Community Mobility Reports, https://www.google.com/covid19/mobility/ (versi unduhan dicatat 2026-11-16). Dokumentasi: https://www.google.com/covid19/mobility/data_documentation.html dan https://support.google.com/covid19-mobility/answer/9824897.
- URL unduhan, SHA-256 lokal dan checksum penerbit jika tersedia: `data_manifest.json`.
