"""Validate and transform JogjaPulse + Google Mobility to explicit analytical grains."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from download_data import digest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
START, END = "2021-12-01", "2022-04-30"
DATES = pd.date_range(START, END, name="date")
GOOGLE_METRICS = {
    "retail_and_recreation": "Retail & recreation",
    "grocery_and_pharmacy": "Grocery & pharmacy",
    "parks": "Parks", "transit_stations": "Transit stations",
    "workplaces": "Workplaces", "residential": "Residential",
}
KABUPATEN = {"34.01": "KULON PROGO", "34.02": "BANTUL", "34.03": "GUNUNGKIDUL",
             "34.04": "SLEMAN", "34.71": "YOGYAKARTA"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def clean_table(frame, columns, key, name):
    """Remove exact duplicates only; conflicting natural keys must be investigated."""
    require(set(columns).issubset(frame.columns), f"{name}: missing columns {set(columns) - set(frame.columns)}")
    result = frame[columns].copy()
    for col in result.select_dtypes(include=["object", "string"]).columns:
        result[col] = result[col].str.strip().replace("", pd.NA)
    before = len(result)
    result = result.drop_duplicates().copy()
    require(not result[key].isna().any().any(), f"{name}: null natural key")
    require(not result.duplicated(key).any(), f"{name}: conflicting duplicate natural key")
    return result, {"input_rows": before, "exact_duplicates_removed": before - len(result)}


def numeric(frame, cols, name, minimum=None, integer=False):
    for col in cols:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        require(frame[col].notna().all() and np.isfinite(frame[col]).all(), f"{name}: invalid {col}")
        if minimum is not None:
            require(frame[col].ge(minimum).all(), f"{name}: {col} < {minimum}")
        if integer:
            require(frame[col].mod(1).eq(0).all(), f"{name}: non-integer {col}")
            frame[col] = frame[col].astype("int64")


def add_calendar(frame):
    frame = frame.copy()
    frame["weekday"] = frame["date"].dt.dayofweek
    frame["day_type"] = np.where(frame["weekday"] >= 5, "Weekend", "Weekday")
    frame["sample_regime"] = np.select(
        [frame["date"] < "2022-01-01", frame["date"] < "2022-02-16"],
        ["Dec 2021", "Jan 1-Feb 15"], default="Feb 16-Apr 30")
    frame["known_anomaly"] = frame["date"].eq(pd.Timestamp("2022-03-08"))
    frame["reduced_quality_period"] = frame["date"].ge(pd.Timestamp("2022-03-01"))
    return frame


def prepare_presence(raw):
    columns = ["kab_code", "kab_kota", "kapanewon_code", "kapanewon", "date", "hour", "n_maids", "n_pings"]
    h, audit = clean_table(raw, columns, ["kapanewon_code", "date", "hour"], "presence")
    require(not h.isna().any().any(), "presence: unexpected missing values")
    h["date"] = pd.to_datetime(h["date"], format="%Y-%m-%d", errors="raise")
    numeric(h, ["hour"], "presence", 0, True)
    require(h["hour"].le(23).all(), "presence: hour outside 0..23")
    require(not h.duplicated(["kapanewon_code", "date", "hour"]).any(), "presence: duplicate key after type conversion")
    numeric(h, ["n_maids"], "presence", 5, True)
    numeric(h, ["n_pings"], "presence", 0, True)
    require(h["n_pings"].ge(h["n_maids"]).all(), "presence: pings < devices")
    require(h["kab_code"].map(KABUPATEN).eq(h["kab_kota"]).all(), "presence: unknown/mismatched regency")
    require(h["kapanewon_code"].str[:5].eq(h["kab_code"]).all(), "presence: mismatched administrative codes")
    units = h[["kab_code", "kab_kota", "kapanewon_code", "kapanewon"]].drop_duplicates()
    require(not units["kapanewon_code"].duplicated().any(), "presence: inconsistent names/codes")
    require(len(units) == 78, "presence: expected 78 kapanewon in record v1")
    selected = h["date"].between(START, END)
    audit["outside_period_rows"] = int((~selected).sum())
    h = h[selected].sort_values(["date", "kapanewon_code", "hour"]).copy()
    require(set(h["date"]) == set(DATES), "presence: missing calendar dates")
    h = add_calendar(h)
    # These sums are presence units, NOT distinct people or daily devices.
    h["daytime_presence"] = h["n_maids"].where(h["hour"].between(8, 17), 0)
    keys = ["date", "kab_code", "kab_kota", "kapanewon_code", "kapanewon"]
    kd = h.groupby(keys, as_index=False).agg(
        published_device_presence_units=("n_maids", "sum"), published_pings=("n_pings", "sum"),
        published_hours=("hour", "nunique"), daytime_presence_units=("daytime_presence", "sum"))
    grid = pd.MultiIndex.from_product([DATES, units["kapanewon_code"]], names=["date", "kapanewon_code"]).to_frame(index=False)
    kd = grid.merge(units, on="kapanewon_code", validate="many_to_one").merge(kd, on=keys, how="left", validate="one_to_one")
    kd["published_hours"] = kd["published_hours"].fillna(0).astype(int)
    kd["coverage_pct"] = kd["published_hours"] / 24 * 100
    kd["complete_day"] = kd["published_hours"].eq(24)
    kd["daytime_share_pct"] = (100 * kd["daytime_presence_units"] / kd["published_device_presence_units"]).where(kd["complete_day"])
    kd["ping_intensity"] = kd["published_pings"] / kd["published_device_presence_units"]
    kd = add_calendar(kd)
    h = h.merge(kd[["date", "kapanewon_code", "complete_day", "published_device_presence_units"]],
                on=["date", "kapanewon_code"], validate="many_to_one")
    h["hourly_share_pct"] = (100 * h["n_maids"] / h["published_device_presence_units"]).where(h["complete_day"])
    daily = kd.groupby("date").agg(
        published_device_presence_units=("published_device_presence_units", lambda x: x.sum(min_count=1)),
        published_pings=("published_pings", lambda x: x.sum(min_count=1)),
        published_slots=("published_hours", "sum"), complete_kapanewon_days=("complete_day", "sum"),
        daytime_share_pct=("daytime_share_pct", "mean"))
    daily["coverage_pct"] = daily["published_slots"] / (78 * 24) * 100
    daily["ping_intensity"] = daily["published_pings"] / daily["published_device_presence_units"]
    daily = add_calendar(daily.reset_index())
    regency = kd.groupby(["date", "kab_code", "kab_kota"], as_index=False).agg(
        published_device_presence_units=("published_device_presence_units", lambda x: x.sum(min_count=1)),
        published_slots=("published_hours", "sum"))
    regency["published_presence_share_pct"] = 100 * regency["published_device_presence_units"] / regency.groupby("date")["published_device_presence_units"].transform("sum")
    unit_counts = units.groupby("kab_code").size()
    regency["coverage_pct"] = 100 * regency["published_slots"] / (24 * regency["kab_code"].map(unit_counts))
    audit.update({"output_rows": len(h), "kapanewon": len(units), "dates": len(daily),
                  "minimum_daily_coverage_pct": float(daily.coverage_pct.min()),
                  "complete_unit_days": int(kd.complete_day.sum()),
                  "unpublished_unit_days": int(kd.published_hours.eq(0).sum())})
    return h.drop(columns="daytime_presence"), kd, daily, regency, audit


def prepare_google(raw):
    required = ["country_region_code", "sub_region_1", "sub_region_2", "metro_area", "iso_3166_2_code", "date"]
    metric_cols = [f"{k}_percent_change_from_baseline" for k in GOOGLE_METRICS]
    require(set(required + metric_cols).issubset(raw.columns), "google: missing columns")
    mask = raw["country_region_code"].eq("ID") & raw["iso_3166_2_code"].eq("ID-YO") & raw["sub_region_2"].isna() & raw["metro_area"].isna()
    g, audit = clean_table(raw.loc[mask], required + metric_cols, ["date"], "google DIY")
    audit["all_indonesia_input_rows"] = len(raw)
    audit["other_region_or_level_rows_excluded"] = int((~mask).sum())
    g["date"] = pd.to_datetime(g["date"], format="%Y-%m-%d", errors="raise")
    require(g["date"].is_unique, "google: duplicate date after type conversion")
    audit["outside_period_rows"] = int((~g["date"].between(START, END)).sum())
    g = g[g["date"].between(START, END)].copy()
    require(set(g["date"]) == set(DATES), "google: missing DIY calendar dates")
    for col in metric_cols:
        g[col] = pd.to_numeric(g[col], errors="raise")
        observed = g[col].dropna()
        require(np.isfinite(observed).all() and observed.ge(-100).all(), f"google: invalid {col}")
    g = g[["date"] + metric_cols].rename(columns={f"{k}_percent_change_from_baseline": f"google_{k}_pct" for k in GOOGLE_METRICS})
    audit.update({"output_rows": len(g), "missing_by_column": g.isna().sum().to_dict()})
    return g.sort_values("date"), audit


def prepare_od(raw, origins):
    keys = ["month", "origin_code", "dest_code"]
    columns = ["month", "origin_kab_code", "origin_kab_kota", "origin_code", "origin_kapanewon",
               "dest_kab_code", "dest_kab_kota", "dest_code", "dest_kapanewon", "n_maids", "reduced_quality"]
    origin_columns = ["month", "origin_kab_code", "origin_kab_kota", "origin_code", "origin_kapanewon",
                      "n_homed_maids", "n_homed_maids_daytime", "reduced_quality"]
    od, audit = clean_table(raw, columns, keys, "OD")
    orig, origin_audit = clean_table(origins, origin_columns, ["month", "origin_code"], "OD origins")
    require(not od.isna().any().any(), "OD: unexpected nulls")
    numeric(od, ["n_maids"], "OD", 5, True)
    numeric(orig, ["n_homed_maids"], "OD origins", 5, True)
    orig["n_homed_maids_daytime"] = pd.to_numeric(orig["n_homed_maids_daytime"], errors="raise")
    observed = orig["n_homed_maids_daytime"].dropna()
    require(np.isfinite(observed).all() and observed.ge(5).all() and observed.mod(1).eq(0).all(), "OD: invalid daytime denominator")
    require((orig["n_homed_maids_daytime"].le(orig["n_homed_maids"]) | orig["n_homed_maids_daytime"].isna()).all(), "OD: denominator exceeds homes")
    months = {"2021-12", "2022-01", "2022-02", "2022-03", "2022-04"}
    for frame in (od, orig):
        require(set(frame["month"]) == months, "OD: unexpected month coverage")
        flags = frame["reduced_quality"].astype(str).str.lower()
        require(flags.isin(["true", "false"]).all(), "OD: invalid quality flag")
        frame["reduced_quality"] = flags.eq("true")
        require(frame["reduced_quality"].eq(frame["month"].ge("2022-03")).all(), "OD: unexpected quality flags")
    od = od.merge(orig[["month", "origin_code", "n_homed_maids_daytime"]], on=["month", "origin_code"], how="left", validate="many_to_one", indicator=True)
    require(od["_merge"].eq("both").all(), "OD: unmatched origin denominator")
    od = od.drop(columns="_merge")
    od["visit_share_pct"] = 100 * od["n_maids"] / od["n_homed_maids_daytime"]
    require(od["visit_share_pct"].dropna().le(100).all(), "OD: visitors exceed denominator")
    od["inter_kapanewon"] = od["origin_code"].ne(od["dest_code"])
    audit.update({"output_rows": len(od), "missing_denominators": int(od.n_homed_maids_daytime.isna().sum()), "origins": origin_audit})
    return od.sort_values(keys), audit


def build():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    manifest = RAW / "manifest.json"
    require(manifest.exists(), "Missing source manifest; run python src/download_data.py first")
    entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    require(len(entries) == 7, "Source manifest: expected seven input files")
    for entry in entries:
        path = (ROOT / entry["path"]).resolve()
        require(path.parent == RAW.resolve(), "Source manifest: file must be in data/raw")
        require(path.exists(), f"Source manifest: missing {path.name}")
        require(digest(path) == entry["sha256"], f"Source manifest: changed file {path.name}; re-download/verify first")
    def read(name):
        path = RAW / name
        require(path.exists(), f"Missing {path.name}; run python src/download_data.py first")
        return pd.read_csv(path, dtype=str)
    h, kd, daily, regency, p_audit = prepare_presence(read("jogjapulse_presence_kapanewon_hourly.csv"))
    google_raw = pd.concat([read(f"google_{year}_ID_Region_Mobility_Report.csv") for year in (2021, 2022)], ignore_index=True)
    google, g_audit = prepare_google(google_raw)
    joined = daily.merge(google, on="date", how="outer", validate="one_to_one", indicator=True)
    require(joined["_merge"].eq("both").all(), "Integration: unmatched dates")
    joined = joined.drop(columns="_merge").sort_values("date")
    od, od_audit = prepare_od(read("jogjapulse_od_home_visits_kapanewon_monthly.csv"), read("jogjapulse_od_origin_homes_monthly.csv"))
    outputs = {"presence_hourly_clean": h, "kapanewon_daily": kd, "diy_daily": daily,
               "regency_daily": regency, "google_diy_daily": google, "integrated_daily": joined, "od_monthly_clean": od}
    for name, frame in outputs.items():
        frame.to_csv(PROCESSED / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    audit = {"period": {"start": START, "end": END, "days": len(DATES)}, "presence": p_audit, "google": g_audit, "od": od_audit,
             "integration": {"rows": len(joined), "unmatched_dates": 0, "grain": "one row per DIY province calendar day (WIB)"},
             "notes": ["Missing/suppressed presence is never zero-filled.", "Presence sums are device-location-hour units, not unique daily devices or trips.",
                       "Daytime share and hourly profiles use only complete 24h kapanewon-days; composition can still change.",
                       "Google metrics retain their original weekday-specific Jan 3-Feb 6 2020 baseline; no interpolation.",
                       "Sample breaks Jan 1 and Feb 16; anomaly Mar 8; March-April OD reduced quality."]}
    (REPORTS / "data_quality.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(manifest, REPORTS / "data_manifest.json")
    print(f"Prepared {len(outputs)} tables; joined {len(joined)} days with no unmatched dates.")
    return outputs, audit


if __name__ == "__main__":
    build()
