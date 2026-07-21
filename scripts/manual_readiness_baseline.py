#!/usr/bin/env python3
"""
Manual (notebook-equivalent) baseline for the AI-READI readiness workflow.

Purpose
-------
This script reproduces, *from raw files and with no dashboard helpers*, the
core readiness check that OpenT2D Explorer performs in a few clicks:

    For one study group, count participants with concurrent ECG+CGM+clinical
    files, then for each of them recover the ECG recording date (from the
    non-standard WFDB .hea comment fields), the CGM monitoring window (first/
    last Open mHealth timestamp), and the OMOP visit date, and test
    calendar-date co-registration.

It is deliberately self-contained (stdlib + pandas only) so that the line
count and wall-clock it reports are a fair "what a researcher would have to
write" baseline for the paper's Table I / Table III comparison.

How to use for the paper
------------------------
1. Set DATASET_ROOT below (or export it as an env var).
2. Run:  python scripts/manual_readiness_baseline.py
3. Read the two numbers printed at the end:
       ANALYSIS LINES OF CODE .... <N>
       WALL-CLOCK (s) ........... <M>
   Drop <N> and <M> into the manuscript sentence, e.g.:
   "reproducing this in a notebook requires ~<N> lines of custom parsing
    code and <M> s, versus two clicks in OpenT2D Explorer; ATLAS cannot
    express the query at all, as it has no access to the waveform files."

Only the code between the BEGIN/END MANUAL BASELINE markers is counted as
the analysis code; the timing/counting harness below is excluded, which is
the honest thing to report.
"""

import glob
import json
import os
import re
import time
from datetime import datetime

import pandas as pd

DATASET_ROOT = os.environ.get(
    "DATASET_ROOT",
    "/home/azureuser/Datasets/f9e65119-3f27-4525-a140-b4413222991d/dataset",
)

# Which study group to scope (mirrors the paper's insulin-dependent walkthrough).
# Adjust the label to match the participants.tsv `study_group` encoding.
TARGET_STUDY_GROUP = "insulin"  # substring match, case-insensitive


# === BEGIN MANUAL BASELINE =====================================================
def parse_ecg_date(hea_path):
    """Recover recording date from WFDB .hea free-text comment fields.
    AI-READI leaves base_date/base_time empty; the date lives in a comment
    line like `# validation_date: 20241014`."""
    try:
        with open(hea_path, "r", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.lstrip("#").strip().partition(":")
        if key.strip().lower() == "validation_date":
            val = val.strip()
            if len(val) == 8:
                try:
                    return datetime.strptime(val, "%Y%m%d").date()
                except ValueError:
                    return None
    return None


def cgm_window(json_path):
    """First/last CGM timestamp, reading count and dropout% from a Dexcom G6
    Open mHealth JSON file."""
    try:
        with open(json_path, "r", errors="ignore") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    readings = doc.get("body", {}).get("cgm", [])
    stamps = []
    for r in readings:
        s = (r.get("effective_time_frame", {})
              .get("time_interval", {})
              .get("start_date_time"))
        if s:
            stamps.append(datetime.fromisoformat(s.replace("Z", "+00:00")))
    if not stamps:
        return None
    stamps.sort()
    first, last = stamps[0], stamps[-1]
    days = max((last - first).total_seconds() / 86400.0, 1e-9)
    expected = days * 288  # Dexcom G6 = one reading / 5 min
    dropout = max(0.0, (expected - len(stamps)) / expected * 100.0)
    return {"first": first, "last": last, "n": len(stamps),
            "days": days, "dropout_pct": dropout}


def visit_dates_by_person(clinical_dir):
    """Earliest OMOP visit_start_date per person_id from visit_occurrence.csv."""
    path = os.path.join(clinical_dir, "visit_occurrence.csv")
    df = pd.read_csv(path, usecols=["person_id", "visit_start_date"])
    df["visit_start_date"] = pd.to_datetime(df["visit_start_date"],
                                            errors="coerce")
    earliest = (df.dropna(subset=["visit_start_date"])
                  .sort_values("visit_start_date")
                  .groupby("person_id", as_index=False)
                  .first())
    return dict(zip(earliest["person_id"].astype(str),
                    earliest["visit_start_date"].dt.date))


def find_hea(person_id):
    base = os.path.join(DATASET_ROOT, "cardiac_ecg", "ecg_12lead",
                        "philips_tc30", str(person_id))
    hits = glob.glob(os.path.join(base, "**", "*.hea"), recursive=True)
    return hits[0] if hits else None


def find_cgm(person_id):
    p = os.path.join(DATASET_ROOT, "wearable_blood_glucose",
                     "continuous_glucose_monitoring", "dexcom_g6",
                     str(person_id), f"{person_id}_DEX.json")
    return p if os.path.exists(p) else None


def run():
    clinical_dir = os.path.join(DATASET_ROOT, "clinical_data")
    parts = pd.read_csv(os.path.join(DATASET_ROOT, "participants.tsv"), sep="\t")
    pid_col = "participant_id" if "participant_id" in parts.columns else parts.columns[0]

    group = parts[parts["study_group"].astype(str)
                  .str.contains(TARGET_STUDY_GROUP, case=False, na=False)]

    # File co-presence (triple overlap) from the modality boolean columns.
    for col in ("cardiac_ecg", "wearable_blood_glucose", "clinical_data"):
        if col not in group.columns:
            raise SystemExit(f"Expected modality column '{col}' not in participants.tsv")
    triple = group[group[["cardiac_ecg", "wearable_blood_glucose",
                          "clinical_data"]].astype(bool).all(axis=1)]

    visits = visit_dates_by_person(clinical_dir)

    same_day = 0
    checked = 0
    for pid in triple[pid_col].astype(str):
        hea = find_hea(pid)
        cgm_json = find_cgm(pid)
        ecg_date = parse_ecg_date(hea) if hea else None
        window = cgm_window(cgm_json) if cgm_json else None
        visit = visits.get(pid)
        if not (window and visit):
            continue
        checked += 1
        cgm_start_date = window["first"].date()
        if cgm_start_date == visit:  # calendar-date co-registration
            same_day += 1

    print(f"study group ..................... {TARGET_STUDY_GROUP}")
    print(f"triple-overlap participants ..... {len(triple)} / {len(group)}")
    print(f"participants with CGM+visit ..... {checked}")
    print(f"CGM co-registered same day ...... {same_day}")
    return len(triple), checked, same_day
# === END MANUAL BASELINE =======================================================


def _count_analysis_loc():
    """Non-blank, non-comment lines between the BEGIN/END markers."""
    with open(__file__, "r") as fh:
        src = fh.readlines()
    inside, n = False, 0
    for line in src:
        s = line.strip()
        if s.startswith("# === BEGIN MANUAL BASELINE"):
            inside = True
            continue
        if s.startswith("# === END MANUAL BASELINE"):
            break
        if inside and s and not s.startswith("#"):
            n += 1
    return n


if __name__ == "__main__":
    t0 = time.perf_counter()
    try:
        run()
        ok = True
    except Exception as exc:  # noqa: BLE001 -- report, don't crash the benchmark
        print(f"[run failed: {exc}] -- fix DATASET_ROOT / paths, then re-run")
        ok = False
    elapsed = time.perf_counter() - t0

    print("-" * 60)
    print(f"ANALYSIS LINES OF CODE .... {_count_analysis_loc()}")
    if ok:
        print(f"WALL-CLOCK (s) ........... {elapsed:.1f}")
    print("-" * 60)
    print("Compare against OpenT2D Explorer: 2 clicks; ATLAS: not expressible.")
