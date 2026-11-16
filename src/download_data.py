"""Download two independent sources atomically, with checksums and provenance."""
import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ZENODO_API = "https://zenodo.org/api/records/23157460"
REQUIRED = {
    "presence_kapanewon_hourly.csv", "od_home_visits_kapanewon_monthly.csv",
    "od_origin_homes_monthly.csv", "tier1_summary.csv", "README.md",
}


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url, dest, checksum=None, force=False):
    """Never mistake a partial download for a valid cached file."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    algorithm, expected = checksum.split(":", 1) if checksum else (None, None)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        if not checksum or digest(dest, algorithm) == expected:
            print("cached", dest.name, flush=True)
            return False
    partial = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "HumanMobility-StudentProject/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
                while block := response.read(1024 * 1024):
                    out.write(block)
            if partial.stat().st_size == 0:
                raise ValueError(f"Empty response: {url}")
            if checksum and digest(partial, algorithm) != expected:
                raise ValueError(f"Checksum mismatch: {dest.name}")
            partial.replace(dest)
            print("downloaded", dest.name, flush=True)
            return True
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main(force=False):
    RAW.mkdir(parents=True, exist_ok=True)
    catalogue = RAW / "zenodo_record.json"
    fetch(ZENODO_API, catalogue, force=True)
    record = json.loads(catalogue.read_text(encoding="utf-8"))
    available = {f["key"]: f for f in record["files"]}
    if missing := REQUIRED - available.keys():
        raise ValueError(f"Zenodo files missing: {missing}")
    sources = []
    for name in sorted(REQUIRED):
        meta = available[name]
        sources.append(("JogjaPulse", meta["links"]["self"], "jogjapulse_" + name, meta["checksum"]))
    # Official country/year extracts avoid the multi-country global CSV.
    for year in (2021, 2022):
        name = f"{year}_ID_Region_Mobility_Report.csv"
        sources.append(("Google Community Mobility", f"https://www.gstatic.com/covid19/mobility/{name}", "google_" + name, None))
    manifest_path = RAW / "manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    entries = []
    for source, url, name, checksum in sources:
        dest = RAW / name
        previous_file = next((x for x in previous.get("files", []) if x["path"] == f"data/raw/{name}"), {})
        # Validate Google cache against the recorded local hash on later runs.
        validation_checksum = checksum or ("sha256:" + previous_file["sha256"] if previous_file and not force else None)
        changed = fetch(url, dest, validation_checksum, force)
        sha = digest(dest)
        prior = next((x for x in previous.get("files", []) if x["path"] == f"data/raw/{name}" and x["sha256"] == sha), {})
        entries.append({"source": source, "url": url, "path": f"data/raw/{name}",
                        "bytes": dest.stat().st_size, "sha256": sha,
                        "publisher_checksum": checksum,
                        "recorded_at_utc": (prior.get("recorded_at_utc") if not changed else None)
                        or datetime.now(timezone.utc).isoformat()})
    manifest_path.write_text(json.dumps({"files": entries}, indent=2) + "\n", encoding="utf-8")
    print("Source manifest:", manifest_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download cached source files")
    main(parser.parse_args().force)
