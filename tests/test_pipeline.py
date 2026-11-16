"""Offline regression tests for assumptions that can silently distort mobility results."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pipeline as p
from download_data import digest, fetch


def test_exact_duplicates_are_removed_but_conflicting_keys_fail():
    raw = pd.DataFrame({"id": ["a", "a"], "count": ["5", "5"]})
    cleaned, audit = p.clean_table(raw, ["id", "count"], ["id"], "test")
    assert len(cleaned) == 1
    assert audit["exact_duplicates_removed"] == 1
    raw.loc[1, "count"] = "6"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        p.clean_table(raw, ["id", "count"], ["id"], "test")


def synthetic_presence():
    rows = []
    for unit in range(78):
        for day in ["2021-12-01", "2021-12-02"]:
            # Unit 0: partial on day 1, entirely unpublished day 2.
            for hour in range(24):
                if unit == 0 and (day == "2021-12-02" or hour == 3):
                    continue
                rows.append(["34.01", "KULON PROGO", f"34.01.{unit:02d}", f"UNIT {unit}", day, str(hour), "10", "20"])
    return pd.DataFrame(rows, columns=["kab_code", "kab_kota", "kapanewon_code", "kapanewon", "date", "hour", "n_maids", "n_pings"])


def test_suppressed_slots_stay_missing_and_partial_days_excluded(monkeypatch):
    monkeypatch.setattr(p, "START", "2021-12-01")
    monkeypatch.setattr(p, "END", "2021-12-02")
    monkeypatch.setattr(p, "DATES", pd.date_range(p.START, p.END, name="date"))
    hourly, unitdays, daily, regency, _ = p.prepare_presence(synthetic_presence())
    missing = unitdays[(unitdays.kapanewon_code == "34.01.00") & (unitdays.date == "2021-12-02")].iloc[0]
    assert missing.published_hours == 0
    assert pd.isna(missing.published_device_presence_units)
    assert pd.isna(missing.daytime_share_pct)
    partial = unitdays[(unitdays.kapanewon_code == "34.01.00") & (unitdays.date == "2021-12-01")].iloc[0]
    assert partial.published_hours == 23
    assert pd.isna(partial.daytime_share_pct)
    assert daily.complete_kapanewon_days.eq(77).all()
    assert np.allclose(daily.daytime_share_pct, 100 * 10 / 24)
    profiles = hourly[hourly.complete_day].groupby(["date", "kapanewon_code"]).hourly_share_pct.sum()
    assert np.allclose(profiles, 100)
    assert np.allclose(regency.groupby("date").published_presence_share_pct.sum(), 100)


def test_google_filters_province_and_preserves_missing_metrics(monkeypatch):
    monkeypatch.setattr(p, "DATES", pd.date_range("2021-12-01", periods=1, name="date"))
    row = {"country_region_code": "ID", "sub_region_1": "Special Region of Yogyakarta", "sub_region_2": np.nan,
           "metro_area": np.nan, "iso_3166_2_code": "ID-YO", "date": "2021-12-01"}
    row.update({f"{key}_percent_change_from_baseline": "10" for key in p.GOOGLE_METRICS})
    row["parks_percent_change_from_baseline"] = np.nan
    child = dict(row, sub_region_2="Child area")
    other = dict(row, iso_3166_2_code="ID-JT")
    cleaned, audit = p.prepare_google(pd.DataFrame([row, child, other]))
    assert len(cleaned) == 1
    assert cleaned.google_parks_pct.isna().all()
    assert audit["all_indonesia_input_rows"] == 3


def test_invalid_hours_and_below_suppression_threshold_fail():
    raw = synthetic_presence()
    raw.loc[0, "hour"] = "24"
    with pytest.raises(ValueError, match="hour outside"):
        p.prepare_presence(raw)
    raw.loc[0, "hour"] = "0"
    raw.loc[0, "n_maids"] = "4"
    with pytest.raises(ValueError, match="n_maids < 5"):
        p.prepare_presence(raw)


def test_bad_download_cannot_replace_existing_file(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("good-data")
    target = tmp_path / "cached.csv"
    target.write_text("old-data")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        fetch(source.as_uri(), target, checksum="md5:" + "0" * 32, force=True)
    assert target.read_text() == "old-data"
    assert not target.with_suffix(".csv.part").exists()
    fetch(source.as_uri(), target, checksum="sha256:" + digest(source), force=True)
    assert digest(source) == digest(target)


def test_calendar_quality_flags_follow_publisher_dates():
    frame = p.add_calendar(pd.DataFrame({"date": pd.to_datetime(["2021-12-31", "2022-01-01", "2022-02-16", "2022-03-08"])}))
    assert frame.sample_regime.tolist() == ["Dec 2021", "Jan 1-Feb 15", "Feb 16-Apr 30", "Feb 16-Apr 30"]
    assert frame.known_anomaly.tolist() == [False, False, False, True]


def test_od_uses_origin_daytime_denominator_and_preserves_quality_flags():
    rows, origins = [], []
    for month in ["2021-12", "2022-01", "2022-02", "2022-03", "2022-04"]:
        origin = {"month": month, "origin_kab_code": "34.01", "origin_kab_kota": "KULON PROGO",
                  "origin_code": "34.01.01", "origin_kapanewon": "TEMON", "reduced_quality": str(month >= "2022-03")}
        rows.append(dict(origin, dest_kab_code="34.01", dest_kab_kota="KULON PROGO", dest_code="34.01.02", dest_kapanewon="WATES", n_maids="5"))
        origins.append(dict(origin, n_homed_maids="30", n_homed_maids_daytime="20"))
    od, audit = p.prepare_od(pd.DataFrame(rows), pd.DataFrame(origins))
    assert od.visit_share_pct.eq(25).all()
    assert od.reduced_quality.tolist() == [False, False, False, True, True]
    assert od.inter_kapanewon.all()
    origins[0]["n_homed_maids_daytime"] = "4"
    with pytest.raises(ValueError, match="invalid daytime denominator"):
        p.prepare_od(pd.DataFrame(rows), pd.DataFrame(origins))


def test_weekly_correlations_skip_anomaly_endpoints_and_sample_breaks():
    from analysis import correlation_tables
    dates = pd.date_range("2021-12-20", "2022-01-31")
    frame = p.add_calendar(pd.DataFrame({"date": dates, "daytime_share_pct": np.sin(np.arange(len(dates)) / 3) + 50}))
    frame.loc[frame.date.eq("2022-01-20"), "known_anomaly"] = True
    for key in p.GOOGLE_METRICS:
        frame[f"google_{key}_pct"] = np.arange(len(frame)) ** 2
    result = correlation_tables(frame)
    row = result.query("window == 'all_valid' and category == 'Workplaces' and method == '7day_difference'").iloc[0]
    # 43 days - first 7 days - 7 days crossing Jan 1 - two anomaly endpoints.
    assert row.n_pairs == 27
