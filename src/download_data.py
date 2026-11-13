"""Download raw data into data/raw/. Run: python src/download_data.py"""
import os
import urllib.request

RAW = os.path.join("data", "raw")
os.makedirs(RAW, exist_ok=True)

ZENODO = "https://zenodo.org/records/23157460/files/{}?download=1"
ZENODO_FILES = [
    "presence_cell500m_daily.csv",
    "presence_kapanewon_hourly.csv",
    "od_home_visits_kapanewon_monthly.csv",
    "od_origin_homes_monthly.csv",
    "home_maids_vs_population_kapanewon.csv",
    "validation_night_presence_kapanewon.csv",
    "od_summary.csv",
    "tier1_summary.csv",
    "README.md",
]
GOOGLE = "https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv"

def fetch(url, dest):
    if os.path.exists(dest):
        print("skip", dest)
        return
    print("downloading", dest)
    urllib.request.urlretrieve(url, dest)

for f in ZENODO_FILES:
    fetch(ZENODO.format(f), os.path.join(RAW, "jogjapulse_" + f))
fetch(GOOGLE, os.path.join(RAW, "google_global_mobility.csv"))
print("done")
