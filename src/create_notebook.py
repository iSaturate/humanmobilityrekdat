"""Build the reviewable notebook source; execution is handled by run_project.py."""
from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "human_mobility_analysis.ipynb"


def create():
    cells = []
    def md(text):
        cells.append(nbf.v4.new_markdown_cell(dedent(text).strip()))
    def code(text):
        cells.append(nbf.v4.new_code_cell(dedent(text).strip()))
    md("""
    # Human Mobility in Yogyakarta
    **Data engineering, analytics, dan visualization — dua sumber independen**

    Periode: **1 Desember 2021–30 April 2022**, tanggal dan jam lokal WIB.

    Notebook ini memeriksa kualitas data, menghasilkan tabel analitis, dan membahas hasil secara deskriptif.
    Hasil grafik dan ringkasan disimpan dalam `figures/` dan `reports/`.
    Tidak ada data sintetis yang digunakan untuk temuan.

    Pertanyaan analisis:
    1. Seberapa lengkap data mobilitas yang tersedia, dan bagaimana cakupannya berubah?
    2. Bagaimana pola kehadiran per jam pada hari kerja dan akhir pekan?
    3. Bagaimana komposisi kehadiran terpublikasi antar-kabupaten/kota?
    4. Bagaimana pola proksi JogjaPulse berhubungan dengan enam kategori Google Mobility?
    5. Pasangan asal–tujuan mana yang memiliki pangsa kunjungan teramati tertinggi pada periode OD yang lebih andal?
    """)
    md("""
    ## 1. Sumber, cakupan, dan cara menjalankan

    | Sumber independen | Data yang digunakan | Peran |
    |---|---|---|
    | [JogjaPulse, Widyawan et al. (2026)](https://doi.org/10.5281/zenodo.23157460) | Kehadiran kapanewon-jam; kunjungan OD bulanan; denominator perangkat asal | Pola jam, distribusi wilayah, pangsa kunjungan |
    | [Google LLC, Community Mobility Reports](https://www.google.com/covid19/mobility/) | Ekstrak Indonesia 2021 dan 2022; hanya baris provinsi `ID-YO` | Perubahan terhadap baseline enam kategori tempat |

    Beberapa CSV JogjaPulse berasal dari **satu sumber**. Google adalah sumber kedua.
    Data cuaca/hari libur tidak digunakan dalam lingkup dua sumber ini.

    Dari root repo, jalankan `python src/run_project.py` untuk mengunduh dan mengeksekusi notebook.
    Atau jalankan `python src/download_data.py`, lalu **Run All** notebook ini dengan kernel Python environment proyek.
    Untuk meninjau hasil yang sudah dieksekusi di GitHub, unduhan ulang tidak diperlukan.
    Data mentah/olahan berukuran besar tidak dimasukkan ke Git; URL dan checksum tersedia di `reports/data_manifest.json`.
    """)
    code("""
    import sys, json
    from pathlib import Path
    ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src' / 'pipeline.py').exists()), None)
    if ROOT is None:
        raise RuntimeError('Buka notebook dari dalam folder repo.')
    sys.path.insert(0, str(ROOT / 'src'))
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from IPython.display import display, Markdown, Image
    from pipeline import build, RAW, PROCESSED, REPORTS, GOOGLE_METRICS
    import analysis as a
    pd.set_option('display.max_columns', 12)
    pd.set_option('display.float_format', lambda x: f'{x:,.3f}')
    print('Python:', sys.version.split()[0], '| pandas:', pd.__version__, '| NumPy:', np.__version__)
    """)
    md("""
    ## 2. Inspect data mentah dan asal-usulnya

    Downloader menggunakan file sementara dan penggantian atomik; file gagal tidak diperlakukan sebagai cache berhasil.
    File JogjaPulse diverifikasi dengan checksum dari API Zenodo. Semua sumber diberi SHA-256 lokal.
    Google tidak menyediakan checksum penerbit pada endpoint CSV; hash lokal mengidentifikasi versi unduhan,
    bukan bukti checksum independen dari penerbit.
    """)
    code("""
    manifest_path = RAW / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError('Jalankan python src/download_data.py terlebih dahulu.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    display(pd.DataFrame(manifest['files'])[['source', 'path', 'bytes', 'publisher_checksum']])
    raw_presence = pd.read_csv(RAW / 'jogjapulse_presence_kapanewon_hourly.csv', dtype=str)
    display(raw_presence.head())
    print('Baris mentah JogjaPulse:', len(raw_presence))
    """)
    md("""
    ## 3. Cleaning, validasi, dan integrasi

    Kode transformasi lengkap tersedia di `src/pipeline.py`. Notebook memanggil fungsi yang sama dengan CLI.

    - Kolom wajib, tipe data, rentang jam 0–23, ambang publikasi perangkat ≥5, dan konsistensi kode wilayah diperiksa.
    - Duplikasi persis dihapus dan dihitung; nilai berbeda pada natural key yang sama menghentikan proses.
    - Key presence: `(kapanewon_code, date, hour)`; key OD: `(month, origin_code, dest_code)`.
    - Google difilter `ID`, `ID-YO`, tanpa subwilayah/metro. Key integrasi: tanggal provinsi, **one-to-one**.
    - Semua 151 tanggal wajib tersedia; kegagalan join menghentikan proses.
    - Kerangka 78 kapanewon × 151 hari dibuat agar unit-hari tidak terpublikasi tetap terlihat.
      Nilai kehadiran yang hilang tetap **NA**; angka nol hanya digunakan untuk **jumlah slot terpublikasi**.
    """)
    code("""
    outputs, quality = build()
    display(pd.DataFrame([{'table': name, 'rows': len(frame), 'columns': len(frame.columns)} for name, frame in outputs.items()]))
    display(Markdown('**Audit kualitas**'))
    print(json.dumps(quality, indent=2))
    joined = outputs['integrated_daily']
    display(joined.head())
    assert len(joined) == 151 and joined.date.is_unique
    """)
    md(r"""
    ## 4. Definisi metrik dan batas pengukuran

    **Unit kehadiran perangkat** adalah penjumlahan `n_maids` pada slot lokasi-jam terpublikasi.
    Perangkat yang sama bisa dihitung pada beberapa jam dan lokasi; hasilnya **bukan perangkat unik harian, penduduk, atau perjalanan**.

    Untuk kapanewon-hari dengan 24 jam terpublikasi:

    $$\text{pangsa jam }h = 100\times\frac{n_{maids,h}}{\sum_{j=0}^{23} n_{maids,j}}$$

    $$\text{pangsa siang} = 100\times\frac{\sum_{h=8}^{17} n_{maids,h}}{\sum_{h=0}^{23}n_{maids,h}}$$

    Pangsa siang DIY adalah rata-rata pangsa siang kapanewon yang lengkap pada hari itu, dengan bobot sama.
    Profil jam dirata-ratakan antar-kapanewon dalam tanggal, lalu antar-tanggal agar hari berbobot sama.
    Kapanewon yang masuk dapat berubah: normalisasi tidak menyelesaikan seluruh bias komposisi.

    Pangsa wilayah adalah bagian dari **total unit kehadiran terpublikasi**, bukan bagian dari populasi.
    Cakupan adalah slot terpublikasi / (78 × 24) per hari; tidak sama dengan representativitas penduduk.

    Google mempertahankan perubahan (%) dari median **hari sejenis** pada 3 Januari–6 Februari 2020.
    Nilai ini tidak langsung dibandingkan dengan jumlah perangkat atau antar-kategori sebagai jumlah orang.
    Residential terutama terkait durasi di rumah. Nilai Google kosong tidak diinterpolasi.
    Lihat [dokumentasi Google](https://www.google.com/covid19/mobility/data_documentation.html).
    """)
    md("""
    ## 5. Cakupan data dan perubahan sampel

    Dokumentasi sumber menandai perubahan sampel 1 Januari dan 16 Februari, anomali 8 Maret, dan kualitas OD lebih rendah pada Maret–April.
    Penurunan hitungan mentah tidak dapat diartikan sebagai penurunan mobilitas penduduk.
    Flag tersebut dipertahankan dalam tabel analitis. Baris tidak terpublikasi tidak diasumsikan bernilai nol.
    """)
    code("""
    fig = a.quality_figure(outputs['diy_daily'])
    display(Image(filename=str(a.FIGURES / '01_sample_coverage.png')))
    plt.close(fig)
    display(joined.groupby(joined.date.dt.to_period('M')).agg(
        mean_coverage_pct=('coverage_pct', 'mean'),
        mean_complete_kapanewon=('complete_kapanewon_days', 'mean')))
    """)
    md("""
    ## 6. Pola per jam: hari kerja dan akhir pekan

    Gunakan unit-hari lengkap agar jam malam yang tersupresi tidak dianggap nol. Tanggal 8 Maret dikecualikan.
    Weekday berarti Senin–Jumat; Weekend berarti Sabtu–Minggu, **tanpa klasifikasi hari libur**.
    Pangsa jam menunjukkan distribusi kehadiran dalam sehari, bukan frekuensi perjalanan.
    """)
    code("""
    fig, profile = a.hourly_figure(outputs['presence_hourly_clean'])
    display(Image(filename=str(a.FIGURES / '02_hourly_profile.png')))
    plt.close(fig)
    display(profile)
    """)
    md("""
    ## 7. Distribusi antar-kabupaten/kota

    Rata-rata bergerak 7 hari dipakai untuk membantu membaca komposisi, dengan syarat tujuh hari tersedia.
    Selalu baca bersama cakupan: perubahan pangsa dapat berasal dari perubahan sampel dan suppression,
    bukan hanya perpindahan aktivitas. Tidak ada klaim bahwa grafik mengukur pangsa penduduk.
    """)
    code("""
    fig = a.regency_figure(outputs['regency_daily'])
    display(Image(filename=str(a.FIGURES / '03_regency_composition.png')))
    plt.close(fig)
    """)
    md("""
    ## 8. Google Community Mobility sebagai sumber kedua

    Grafik berikut memakai baris provinsi DIY saja. Garis tipis adalah data asli; garis tebal adalah rerata 7 hari.
    Setiap kategori memiliki baseline sendiri. Perbedaan persentase antar-kategori tidak memberi jumlah pengunjung.
    """)
    code("""
    fig = a.google_figure(outputs['google_diy_daily'])
    display(Image(filename=str(a.FIGURES / '04_google_mobility.png')))
    plt.close(fig)
    """)
    md("""
    ## 9. Analisis gabungan dua sumber dan pemeriksaan sensitivitas

    Pangsa kehadiran siang JogjaPulse dibandingkan dengan enam kategori Google pada tanggal yang sama.
    Kedua sumber mengukur konsep dan sampel berbeda; hubungan ini **eksploratif**, bukan validasi jumlah perjalanan.

    Tabel membandingkan korelasi Pearson mentah, korelasi setelah pengurangan rerata dalam kelompok hari-dalam-minggu × rezim sampel,
    dan korelasi **selisih 7 hari**. Selisih tujuh hari mempertahankan hari sejenis pada baseline Google.
    Pasangan yang melintasi pergantian rezim dikecualikan. 8 Maret dan pasangan dengan nilai kosong dikecualikan.
    Periode sebelum 16 Februari juga dihitung untuk memeriksa sensitivitas terhadap penurunan sampel berikutnya.

    Pemeriksaan tambahan menahan keanggotaan wilayah tetap pada kapanewon yang lengkap di seluruh hari non-anomali.
    Panel ini hanya mencakup empat kapanewon pada data saat ini, sehingga juga tidak representatif seluruh DIY.

    Z-score hanya menyetarakan skala tampilan. Korelasi tidak mengendalikan semua perubahan sampel,
    musim, dan autokorelasi; tidak dihitung p-value atau disimpulkan sebab-akibat.
    """)
    code("""
    correlations = a.correlation_tables(joined)
    display(correlations.round(3))
    fig = a.comparison_figure(joined, correlations)
    display(Image(filename=str(a.FIGURES / '05_two_source_comparison.png')))
    plt.close(fig)
    """)
    code("""
    panel_names, panel_correlations = a.fixed_panel_sensitivity(outputs)
    display(Markdown('**Sensitivitas: panel wilayah tetap, seluruh hari non-anomali**'))
    display(panel_names)
    display(panel_correlations.query("window == 'all_valid' and method == '7day_difference'"))
    """)
    md(r"""
    ## 10. Tambahan JogjaPulse: pangsa kunjungan asal–tujuan

    $$\text{pangsa kunjungan}_{i,j,m}=100\times\frac{\text{perangkat asal }i\text{ yang teramati di }j}{\text{perangkat ber-home }i\text{ yang teramati pada siang hari}}$$

    Analisis dibatasi **Desember 2021–Februari 2022**, antar-kapanewon, dan pasangan terpublikasi pada ketiga bulan.
    Ranking menggunakan rata-rata pangsa tiap pasangan. Satu perangkat bisa mengunjungi beberapa tujuan;
    pangsa tidak dijumlahkan antar-tujuan. Grafik ini adalah kunjungan perangkat teramati, bukan jumlah trip,
    dan tidak membandingkan perubahan populasi antarbulan.
    """)
    code("""
    fig, top = a.od_figure(outputs['od_monthly_clean'])
    display(Image(filename=str(a.FIGURES / '06_od_visit_shares.png')))
    plt.close(fig)
    display(top[['origin_kapanewon', 'dest_kapanewon', 'months_published', 'mean_visit_share_pct']].sort_values('mean_visit_share_pct', ascending=False))
    """)
    md("""
    ## 11. Temuan yang dihitung dari data

    Sel berikut memperbarui ringkasan, tabel korelasi, audit bulanan, dan preview integrasi di `reports/`.
    Interpretasi dibatasi pada sampel yang tersedia dan tidak dipakai sebagai klaim populasi atau kausalitas.
    """)
    code("""
    summary = a.summarize(outputs, correlations, profile, top)
    display(Markdown((REPORTS / 'findings.md').read_text(encoding='utf-8')))
    """)
    nb = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"}})
    # Stable IDs keep subsequent regeneration diffs readable.
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"mobility-{i:02d}"
    NOTEBOOK.parent.mkdir(exist_ok=True)
    nbf.write(nb, NOTEBOOK)
    return NOTEBOOK


if __name__ == "__main__":
    print(create())
