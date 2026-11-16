"""Descriptive analysis and exportable figures; no causal or population claims."""
import json
import importlib.metadata
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pipeline import GOOGLE_METRICS, PROCESSED, REPORTS, ROOT

FIGURES = ROOT / "figures"
COLORS = ["#2563eb", "#f97316", "#059669", "#9333ea", "#dc2626", "#64748b"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "white",
                     "axes.prop_cycle": plt.cycler(color=COLORS), "savefig.dpi": 160})


def save(fig, name):
    FIGURES.mkdir(exist_ok=True)
    fig.savefig(FIGURES / f"{name}.png", bbox_inches="tight", facecolor="white")
    return fig


def date_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y", alpha=.2)


def load_outputs():
    outputs = {}
    for name in ["presence_hourly_clean", "kapanewon_daily", "diy_daily", "regency_daily", "google_diy_daily", "integrated_daily", "od_monthly_clean"]:
        outputs[name] = pd.read_csv(PROCESSED / f"{name}.csv", dtype={"kab_code": str, "kapanewon_code": str, "origin_code": str, "dest_code": str})
        if "date" in outputs[name]:
            outputs[name]["date"] = pd.to_datetime(outputs[name]["date"])
    return outputs


def quality_figure(daily):
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True, layout="constrained")
    axes[0].plot(daily.date, daily.published_device_presence_units / 1e6, lw=1.5)
    axes[0].set(ylabel="Juta unit kehadiran", title="Cakupan sampel berubah: hitungan mentah bukan tren populasi")
    axes[1].plot(daily.date, daily.coverage_pct, label="Slot kapanewon-jam terpublikasi (%)")
    axes[1].plot(daily.date, daily.complete_kapanewon_days / 78 * 100, label="Kapanewon dengan 24 jam lengkap (%)", color=COLORS[1])
    axes[1].set(ylabel="Cakupan (%)", ylim=(0, 105))
    axes[1].legend(loc="lower left", fontsize=9)
    for ax in axes:
        for date, label in [("2022-01-01", "Pergantian sampel"), ("2022-02-16", "Pergantian sampel"), ("2022-03-08", "Anomali")]:
            ax.axvline(pd.Timestamp(date), color="#64748b", ls="--", lw=.8)
        date_axis(ax)
    fig.supxlabel("WIB | 78 kapanewon x 24 jam per hari; unit kehadiran dapat menghitung perangkat yang sama berulang", fontsize=9)
    return save(fig, "01_sample_coverage")


def hourly_figure(hourly):
    clean = hourly[hourly.complete_day & ~hourly.known_anomaly]
    # First average unit-days within each date, then days, so days are equally weighted.
    by_date = clean.groupby(["date", "day_type", "hour"], as_index=False).hourly_share_pct.mean()
    profile = by_date.groupby(["day_type", "hour"]).hourly_share_pct.mean().unstack(0)
    fig, ax = plt.subplots(figsize=(10, 4.6), layout="constrained")
    for kind in ["Weekday", "Weekend"]:
        ax.plot(profile.index, profile[kind], marker="o", ms=3, label=kind)
    ax.axvspan(8, 17, color=COLORS[0], alpha=.06)
    ax.set(title="Bagaimana kehadiran terdistribusi sepanjang hari?", xlabel="Jam (WIB)",
           ylabel="Rata-rata pangsa kehadiran harian (%)", xticks=range(0, 24, 2))
    ax.grid(alpha=.2)
    ax.legend()
    fig.supxlabel("Hanya kapanewon-hari dengan 24 jam lengkap; 8 Maret dikecualikan. Komposisi wilayah dapat berubah.", fontsize=9)
    return save(fig, "02_hourly_profile"), profile


def regency_figure(regency):
    wide = regency.pivot(index="date", columns="kab_kota", values="published_presence_share_pct").sort_index()
    smoothed = wide.rolling(7, min_periods=7).mean().dropna()
    fig, ax = plt.subplots(figsize=(11, 4.7), layout="constrained")
    ax.stackplot(smoothed.index, smoothed.T, labels=smoothed.columns, alpha=.9)
    ax.set(title="Komposisi kehadiran terpublikasi per kabupaten/kota", ylabel="Pangsa unit kehadiran (%)", ylim=(0, 100))
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.13), ncol=5, fontsize=8)
    date_axis(ax)
    fig.supxlabel("Rata-rata bergerak 7 hari; bukan pangsa penduduk. Pergantian sampel dan suppression memengaruhi komposisi.", fontsize=9)
    return save(fig, "03_regency_composition")


def google_figure(google):
    fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True, layout="constrained")
    for ax, (key, label) in zip(axes.flat, GOOGLE_METRICS.items()):
        s = google.set_index("date")[f"google_{key}_pct"]
        ax.plot(s.index, s, color="#94a3b8", alpha=.6, lw=.7)
        ax.plot(s.index, s.rolling(7, min_periods=7).mean(), lw=1.8)
        ax.axhline(0, color="#64748b", ls="--", lw=.7)
        ax.set(title=label, ylabel="Perubahan dari baseline (%)")
        date_axis(ax)
    fig.suptitle("Google Mobility DIY: pola relatif terhadap baseline masing-masing kategori", fontsize=13)
    fig.supxlabel("Garis tebal: rata-rata 7 hari | Baseline: median hari sejenis, 3 Jan-6 Feb 2020; bukan jumlah pengunjung.", fontsize=9)
    return save(fig, "04_google_mobility")


def correlation_tables(joined):
    """Compare unlike proxies cautiously, preserving matching weekdays and regimes."""
    rows = []
    windows = {"all_valid": joined.date.notna(), "before_feb16": joined.date.lt("2022-02-16")}
    for window, mask in windows.items():
        data = joined[mask].sort_values("date").copy()
        for key, label in GOOGLE_METRICS.items():
            cols = ["daytime_share_pct", f"google_{key}_pct"]
            x = data.set_index("date")[cols].reindex(pd.date_range(data.date.min(), data.date.max()))
            meta = data.set_index("date").reindex(x.index)
            valid = ~meta.known_anomaly.fillna(True)
            x = x.where(valid, np.nan)
            adjusted = x - x.groupby([meta.sample_regime, meta.weekday]).transform("mean")
            # A 7-day difference compares matching weekdays; skip sample breaks and gaps.
            weekly = (x - x.shift(7)).where(meta.sample_regime.eq(meta.sample_regime.shift(7)), np.nan)
            for method, pairs in [("raw", x), ("weekday_regime_adjusted", adjusted), ("7day_difference", weekly)]:
                pairs = pairs.dropna()
                r = float(pairs.iloc[:, 0].corr(pairs.iloc[:, 1])) if len(pairs) >= 10 and pairs.nunique().min() > 1 else np.nan
                rows.append({"window": window, "category": label, "method": method, "n_pairs": len(pairs), "pearson_r": r})
    return pd.DataFrame(rows)


def comparison_figure(joined, correlations):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout="constrained")
    data = joined.set_index("date").copy()
    cols = ["daytime_share_pct", "google_workplaces_pct"]
    x = data[cols].where(~data.known_anomaly, np.nan)
    z = (x - x.mean()) / x.std(ddof=0)
    for col, label in zip(cols, ["JogjaPulse: pangsa kehadiran 08-17", "Google: perubahan workplaces"]):
        axes[0].plot(z.index, z[col].rolling(7, min_periods=7).mean(), label=label)
    axes[0].set(title="Dua proksi berbeda: perbandingan pola secara eksploratif", ylabel="Z-score; rata-rata 7 hari")
    axes[0].legend(fontsize=9)
    date_axis(axes[0])
    table = correlations[(correlations.window == "all_valid") & (correlations.method != "raw")].pivot(index="category", columns="method", values="pearson_r")
    table = table.rename(columns={"weekday_regime_adjusted": "Dikurangi rerata hari & rezim", "7day_difference": "Selisih 7 hari"})
    pos = np.arange(len(table))
    for offset, (col, color) in enumerate(zip(table.columns, COLORS)):
        axes[1].barh(pos + (offset - .5) * .32, table[col], height=.3, color=color, label=col)
    axes[1].set(yticks=pos, yticklabels=table.index, xlim=(-1, 1), xlabel="Pearson r terhadap pangsa kehadiran siang JogjaPulse")
    axes[1].axvline(0, color="#64748b", lw=.8)
    axes[1].legend(loc="lower right", fontsize=8)
    axes[1].grid(axis="x", alpha=.2)
    fig.supxlabel("8 Maret dikecualikan. Korelasi deskriptif; tidak membuktikan sebab-akibat atau validasi jumlah perjalanan.", fontsize=9)
    return save(fig, "05_two_source_comparison")


def od_figure(od):
    reliable = od[(~od.reduced_quality) & od.inter_kapanewon].copy()
    # Rank observed pair-specific shares; never add distinct visitors across destinations.
    pairs = reliable.groupby(["origin_code", "origin_kapanewon", "dest_code", "dest_kapanewon"]).agg(
        months_published=("month", "nunique"), mean_visit_share_pct=("visit_share_pct", "mean")).reset_index()
    top = pairs[pairs.months_published.eq(3)].nlargest(10, "mean_visit_share_pct").sort_values("mean_visit_share_pct")
    fig, ax = plt.subplots(figsize=(10, 5.8), layout="constrained")
    labels = top.origin_kapanewon + " → " + top.dest_kapanewon
    ax.barh(labels, top.mean_visit_share_pct, color=COLORS[0])
    ax.set(title="10 pasangan antar-kapanewon dengan pangsa kunjungan tertinggi", xlabel="Rata-rata perangkat asal yang mengunjungi tujuan (%)", xlim=(0, 100))
    ax.grid(axis="x", alpha=.2)
    fig.supxlabel("Des 2021-Feb 2022; pasangan terpublikasi pada ketiga bulan. Pengunjung teramati, bukan jumlah perjalanan.", fontsize=9)
    return save(fig, "06_od_visit_shares"), top


def fixed_panel_sensitivity(outputs):
    """Hold geographical membership constant; this small panel is not DIY-representative."""
    kd = outputs["kapanewon_daily"]
    valid = kd[~kd.known_anomaly]
    counts = valid.groupby("kapanewon_code").complete_day.sum()
    units = counts[counts.eq(valid.date.nunique())].index
    panel = valid[valid.kapanewon_code.isin(units)]
    daily = panel.groupby("date").daytime_share_pct.mean()
    joined = outputs["integrated_daily"].copy()
    joined["daytime_share_pct"] = joined.date.map(daily)
    correlations = correlation_tables(joined)
    names = panel[["kapanewon_code", "kapanewon", "kab_kota"]].drop_duplicates().sort_values("kapanewon_code")
    return names, correlations


def summarize(outputs, correlations, profile, top):
    daily = outputs["integrated_daily"]
    hourly = outputs["presence_hourly_clean"]
    audit = json.loads((REPORTS / "data_quality.json").read_text())
    valid = daily[~daily.known_anomaly]
    daytypes = valid.groupby("day_type").daytime_share_pct.mean()
    monthly = daily.groupby(daily.date.dt.to_period("M")).agg(mean_coverage_pct=("coverage_pct", "mean"), mean_complete_kapanewon=("complete_kapanewon_days", "mean"))
    panel_names, panel_correlations = fixed_panel_sensitivity(outputs)
    panel_correlations.to_csv(REPORTS / "fixed_panel_correlations.csv", index=False)
    panel_names.to_csv(REPORTS / "fixed_panel_members.csv", index=False)
    strongest = correlations[(correlations.window == "all_valid") & (correlations.method == "7day_difference")].dropna(subset="pearson_r")
    strongest = strongest.loc[strongest.pearson_r.abs().idxmax()]
    summary = {
        "days_joined": len(daily), "presence_rows": len(hourly),
        "weekday_daytime_share_pct": float(daytypes["Weekday"]), "weekend_daytime_share_pct": float(daytypes["Weekend"]),
        "weekday_peak_hour": int(profile["Weekday"].idxmax()), "weekend_peak_hour": int(profile["Weekend"].idxmax()),
        "min_complete_kapanewon_per_day": int(daily.complete_kapanewon_days.min()),
        "max_complete_kapanewon_per_day": int(daily.complete_kapanewon_days.max()),
        "strongest_7day_correlation": strongest.to_dict(),
        "fixed_panel_units": len(panel_names),
    }
    same_category = panel_correlations[(panel_correlations.window == "all_valid") & (panel_correlations.method == "7day_difference") & (panel_correlations.category == strongest['category'])].iloc[0]
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   "packages": {name: importlib.metadata.version(name) for name in ["pandas", "numpy", "matplotlib", "nbformat", "nbclient", "ipykernel"]}}
    (REPORTS / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((REPORTS / "data_manifest.json").read_text(encoding="utf-8"))
    accessed = max(entry["recorded_at_utc"][:10] for entry in manifest["files"] if entry["source"] == "Google Community Mobility")
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    monthly.to_csv(REPORTS / "monthly_coverage.csv")
    correlations.to_csv(REPORTS / "correlations.csv", index=False)
    top.to_csv(REPORTS / "top_od_pairs.csv", index=False)
    daily.to_csv(REPORTS / "integrated_daily_preview.csv", index=False, date_format="%Y-%m-%d")
    text = f"""# Hasil analisis mobilitas DIY

Analisis deskriptif dua sumber independen, 1 Desember 2021-30 April 2022 (WIB).
Angka di bawah dihasilkan oleh `src/analysis.py`, bukan ditulis sebelum data diperiksa.

## Data dan validasi

- JogjaPulse: {len(hourly):,} baris kapanewon-jam, 78 kapanewon.
- Integrasi dengan Google DIY: {len(daily)} hari, satu baris per tanggal; tidak ada tanggal gagal join.
- Duplikasi persis yang dihapus pada presence: {audit['presence']['exact_duplicates_removed']}.
- Cakupan minimum slot kapanewon-jam: {daily.coverage_pct.min():.1f}%.
- Kapanewon dengan data 24 jam lengkap per hari: {daily.complete_kapanewon_days.min()}-{daily.complete_kapanewon_days.max()} dari 78.
- Nilai Google yang kosong tetap kosong; lihat `data_quality.json` untuk rincian per kolom.

## Temuan

1. Pangsa kehadiran siang (08-17 WIB) rata-rata {daytypes['Weekday']:.2f}% pada hari kerja dan {daytypes['Weekend']:.2f}% pada akhir pekan, selisih {daytypes['Weekend']-daytypes['Weekday']:+.2f} poin persentase. Ini adalah pembagian unit kehadiran sepanjang hari, bukan persentase orang yang bepergian. Angka menggunakan kapanewon-hari lengkap, pembobotan merata per kapanewon dalam hari lalu per hari, dan mengecualikan 8 Maret.
2. Puncak profil jam rata-rata: pukul {summary['weekday_peak_hour']:02d} WIB pada hari kerja dan {summary['weekend_peak_hour']:02d} WIB pada akhir pekan. Komposisi kapanewon lengkap dapat berbeda antarhari, sehingga pola bersifat deskriptif.
3. Korelasi selisih 7 hari dengan nilai absolut terbesar terdapat pada kategori Google **{strongest['category']}**: r = {strongest['pearson_r']:.3f}, n = {strongest['n_pairs']}. Pemilihan nilai terbesar dari enam kategori bersifat eksploratif. Bandingkan seluruh kategori, penyesuaian hari/rezim, dan periode sebelum 16 Februari pada `correlations.csv`; jangan menafsirkannya sebagai validasi atau kausalitas.
4. Analisis OD dibatasi Desember-Februari. Grafik merangking rata-rata pangsa kunjungan tiap pasangan asal-tujuan yang terpublikasi pada ketiga bulan. Perangkat yang sama dapat mengunjungi beberapa tujuan; pangsa antar-tujuan tidak dijumlahkan menjadi total perjalanan.
5. Hanya **{len(panel_names)} kapanewon** memiliki data 24 jam lengkap pada seluruh 150 hari non-anomali. Pada panel wilayah tetap ini, korelasi selisih 7 hari untuk kategori {strongest['category']} adalah r = {same_category['pearson_r']:.3f} (n = {same_category['n_pairs']}). Bandingkan dengan r = {strongest['pearson_r']:.3f} pada panel yang berubah. Perbandingan ini memeriksa sensitivitas terhadap komposisi; kemiripan korelasi satu kategori tidak membuktikan tidak ada bias, dan panel kecil ini tidak mewakili seluruh DIY. Anggota dan semua korelasinya disimpan di `fixed_panel_members.csv` dan `fixed_panel_correlations.csv`.

## Batas interpretasi

Jumlah sampel JogjaPulse berubah pada 1 Januari dan 16 Februari; 8 Maret ditandai sebagai anomali. Periode Maret-April memiliki cakupan lebih lemah dan OD ditandai reduced quality. Normalisasi mengurangi pengaruh skala sampel, tetapi tidak menghilangkan bias perubahan komposisi. Slot yang tidak dipublikasikan bukan nol. Cakupan dalam laporan dihitung terhadap kerangka 78 x 24 slot per hari, bukan persentase penduduk yang terwakili.

Google mengukur perubahan kunjungan/durasi relatif terhadap median hari sejenis pada 3 Januari-6 Februari 2020. Residential terutama terkait durasi di rumah. JogjaPulse mengukur kehadiran perangkat dari sumber SDK berbeda. Kedua metrik tidak setara; z-score hanya membantu melihat pola. Selisih 7 hari menjaga kecocokan hari dalam minggu, melewati batas rezim sampel dikecualikan. Autokorelasi, musim, pemilihan sampel dan kategori tidak dikendalikan sepenuhnya; tidak dihitung p-value atau klaim signifikansi.

## Sumber

- Widyawan et al. (2026), JogjaPulse, https://doi.org/10.5281/zenodo.23157460 (CC BY 4.0; lihat metadata record).
- Google LLC, Google COVID-19 Community Mobility Reports, https://www.google.com/covid19/mobility/ (versi unduhan dicatat {accessed}). Dokumentasi: https://www.google.com/covid19/mobility/data_documentation.html dan https://support.google.com/covid19-mobility/answer/9824897.
- URL unduhan, SHA-256 lokal dan checksum penerbit jika tersedia: `data_manifest.json`.
"""
    (REPORTS / "findings.md").write_text(text, encoding="utf-8")
    return summary


def run_analysis(outputs=None):
    outputs = outputs if outputs is not None else load_outputs()
    REPORTS.mkdir(exist_ok=True)
    figures = [quality_figure(outputs["diy_daily"])]
    fig, profile = hourly_figure(outputs["presence_hourly_clean"])
    figures.extend([fig, regency_figure(outputs["regency_daily"]), google_figure(outputs["google_diy_daily"])])
    correlations = correlation_tables(outputs["integrated_daily"])
    figures.append(comparison_figure(outputs["integrated_daily"], correlations))
    fig, top = od_figure(outputs["od_monthly_clean"])
    figures.append(fig)
    summary = summarize(outputs, correlations, profile, top)
    return figures, correlations, summary


if __name__ == "__main__":
    figs, _, summary = run_analysis()
    for fig in figs:
        plt.close(fig)
    print(json.dumps(summary, indent=2))
