#!/usr/bin/env python3
"""
make_synthetic_dataset.py — writes a small, fully synthetic dataset with the
AI-READI v3.0.0 directory layout and file formats.

It exists so the dashboard, the tests and the evidence pipeline can run
without access to the DUA-protected data (CI, reviewers, new contributors).
No value in it is derived from AI-READI; every number is random. The root
contains dataset_description.json with "synthetic": true, and every script
in scripts/ labels its output as synthetic when it sees that flag.

The generator deliberately includes the edge cases the pipeline must handle:
missing and malformed validation_date values, ECG dates that cluster on a
batch date, CGM windows that start after the visit, CGM gaps, and
participants flagged as having a modality whose file is missing.

Usage:
    python scripts/make_synthetic_dataset.py --out /tmp/aireadi_synth --n 120
    DATASET_ROOT=/tmp/aireadi_synth python scripts/build_readiness_table.py
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

GROUPS = [
    ("healthy", 0.34),
    ("pre_diabetes_lifestyle_controlled", 0.25),
    ("oral_medication_and_or_non_insulin_injectable_medication_controlled", 0.30),
    ("insulin_dependent", 0.11),
]
GROUP_GLUCOSE = {  # mean CGM glucose (mg/dL) by group
    "healthy": 105, "pre_diabetes_lifestyle_controlled": 118,
    "oral_medication_and_or_non_insulin_injectable_medication_controlled": 150,
    "insulin_dependent": 178,
}
GROUP_ABNORMAL_P = {
    "healthy": 0.20, "pre_diabetes_lifestyle_controlled": 0.28,
    "oral_medication_and_or_non_insulin_injectable_medication_controlled": 0.38,
    "insulin_dependent": 0.48,
}
SITES = ["UW", "UCSD", "UAB"]
BATCH_DATE = "20241014"  # a shared "processing" date for a minority of ECGs

OMOP = {  # concept_id: (unit, generator(group_mean_glucose, rng))
    3004410: "%",       # HbA1c
    3004501: "mg/dL",   # glucose
    4245997: "kg/m²",   # BMI
    3004249: "mmHg",    # SBP
    3012888: "mmHg",    # DBP
    3027114: "mg/dL",   # total cholesterol
    3007070: "mg/dL",   # HDL
    3028288: "mg/dL",   # LDL
    3022192: "mg/dL",   # triglycerides
}

MODALITY_COLS = [
    "cardiac_ecg", "clinical_data", "environment", "retinal_flio", "retinal_oct",
    "retinal_octa", "retinal_photography", "wearable_activity_monitor", "wearable_blood_glucose",
]


def _pick(rng: random.Random, weighted):
    r, acc = rng.random(), 0.0
    for item, w in weighted:
        acc += w
        if r <= acc:
            return item
    return weighted[-1][0]


def _ecg_comments(rng: random.Random, visit: date, group: str) -> list[str]:
    scenario = rng.random()
    if scenario < 0.70:
        vd = visit.strftime("%Y%m%d")
    elif scenario < 0.85:
        vd = (visit + timedelta(days=rng.randint(1, 20))).strftime("%Y%m%d")
    elif scenario < 0.95:
        vd = BATCH_DATE
    elif scenario < 0.98:
        vd = None                      # missing
    else:
        vd = rng.choice(["2024-10-14", "20241399"])  # malformed

    p_abn = GROUP_ABNORMAL_P[group]
    verdict = _pick(rng, [
        ("- NORMAL ECG -", 0.62 - p_abn),
        ("- OTHERWISE NORMAL ECG -", 0.28),
        ("- BORDERLINE ECG -", 0.10),
        ("- ABNORMAL ECG -", p_abn),
    ])
    hr = rng.randint(52, 98)
    qt = rng.randint(360, 440)
    qtc = int(qt / math.sqrt(60 / hr))
    lines = [
        "device_model: PageWriter TC30",
        "machine_detail_description: A.07.07.07",
        "high_pass_filter_setting: 0.15",
        "low_pass_filter_setting: 100",
        "notch_filter_setting: 60",
        "artifact_filter_flag: On",
        f"Rate: {hr}",
        f"PR: {rng.randint(130, 210)}",
        f"QRSD: {rng.randint(78, 118)}",
        f"QT: {qt}",
        f"QTc: {qtc}",
        "interpretation_comment_1: Unconfirmed Diagnosis",
        f"interpretation_comment_2: {verdict}",
        "comment_1_key: Sinus rhythm",
    ]
    if vd is not None:
        lines.insert(0, f"validation_date: {vd}")
    return lines


def _write_ecg(rng: random.Random, np_rng, out: Path, pid: str, visit: date, group: str) -> None:
    import wfdb

    d = out / "cardiac_ecg" / "ecg_12lead" / "philips_tc30" / pid
    d.mkdir(parents=True, exist_ok=True)
    fs, n = 500, 5000
    t = np.arange(n) / fs
    base = 0.8 * np.sin(2 * np.pi * 1.1 * t) ** 31        # crude QRS-like spikes
    sig = np.stack([base * (0.5 + 0.1 * k) + np_rng.normal(0, 0.03, n) for k in range(12)], axis=1)
    wfdb.wrsamp(
        f"{pid}_ecg_synthetic", fs=fs, units=["mV"] * 12,
        sig_name=["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"],
        p_signal=sig, fmt=["16"] * 12, comments=_ecg_comments(rng, visit, group), write_dir=str(d),
    )


def _write_cgm(rng: random.Random, out: Path, pid: str, visit: date, group: str) -> float:
    d = out / "wearable_blood_glucose" / "continuous_glucose_monitoring" / "dexcom_g6" / pid
    d.mkdir(parents=True, exist_ok=True)
    start_offset = 0 if rng.random() < 0.85 else rng.randint(1, 20)
    t0 = datetime.combine(visit + timedelta(days=start_offset), datetime.min.time(), tzinfo=timezone.utc)
    t0 += timedelta(hours=rng.randint(9, 20), minutes=rng.randint(0, 59))
    days = rng.uniform(8.5, 10.0)
    n_slots = int(days * 288)
    gap_p = rng.choice([0.002, 0.01, 0.03, 0.15])
    mu = GROUP_GLUCOSE[group] + rng.gauss(0, 12)
    entries, values = [], []
    for i in range(n_slots):
        if rng.random() < gap_p:
            continue
        ts = t0 + timedelta(minutes=5 * i)
        v = mu + 25 * math.sin(2 * math.pi * i / 288) + rng.gauss(0, 15)
        v = max(40, min(400, v))
        values.append(v)
        iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        entries.append({
            "effective_time_frame": {"time_interval": {"start_date_time": iso, "end_date_time": iso}},
            "event_type": "EGV",
            "blood_glucose": {"unit": "mg/dL", "value": int(round(v))},
        })
    doc = {"header": {"uuid": f"synthetic-{pid}", "synthetic": True}, "body": {"cgm": entries}}
    (d / f"{pid}_DEX.json").write_text(json.dumps(doc))
    return float(np.mean(values)) if values else mu


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output dataset root")
    ap.add_argument("--n", type=int, default=120, help="number of participants")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    (out / "clinical_data").mkdir(parents=True, exist_ok=True)

    participants, persons, visits, measurements = [], [], [], []
    meas_id = 1
    for i in range(args.n):
        pid = str(1001 + i)
        group = _pick(rng, GROUPS)
        site = rng.choice(SITES)
        visit = date(2023, 7, 18) + timedelta(days=rng.randint(0, 620))
        age = rng.randint(40, 85)
        split = _pick(rng, [("train", 0.7), ("val", 0.15), ("test", 0.15)])

        flags = {c: rng.random() < 0.9 for c in MODALITY_COLS}
        flags["clinical_data"] = True
        flags["cardiac_ecg"] = rng.random() < 0.97
        flags["wearable_blood_glucose"] = rng.random() < 0.97

        participants.append({
            "person_id": pid, "clinical_site": site, "study_group": group, "age": age,
            "study_visit_date": visit.isoformat(), "recommended_split": split,
            **{c: "TRUE" if v else "FALSE" for c, v in flags.items()},
        })
        persons.append({"person_id": pid, "gender_concept_id": rng.choice([8507, 8532]),
                        "year_of_birth": visit.year - age})
        visits.append({"visit_occurrence_id": 50000 + i, "person_id": pid,
                       "visit_start_date": visit.isoformat(),
                       "visit_start_datetime": f"{visit.isoformat()} 08:{rng.randint(10, 59)}:00"})

        # A flagged modality occasionally has no file on disk
        mean_glucose = GROUP_GLUCOSE[group]
        if flags["cardiac_ecg"] and rng.random() > 0.01:
            _write_ecg(rng, np_rng, out, pid, visit, group)
        if flags["wearable_blood_glucose"] and rng.random() > 0.01:
            mean_glucose = _write_cgm(rng, out, pid, visit, group)

        bmi = rng.gauss(27 + (3 if group != "healthy" else 0), 4)
        values = {
            3004410: (mean_glucose + 46.7) / 28.7 + rng.gauss(0, 0.35),   # ADAG relation + noise
            3004501: mean_glucose * 0.9 + rng.gauss(0, 12),
            4245997: bmi,
            3004249: rng.gauss(128, 15),
            3012888: rng.gauss(78, 9),
            3027114: rng.gauss(185, 35),
            3007070: rng.gauss(52, 12),
            3028288: rng.gauss(105, 30),
            3022192: rng.gauss(140, 50),
        }
        for cid, v in values.items():
            measurements.append({
                "measurement_id": meas_id, "person_id": pid, "measurement_concept_id": cid,
                "measurement_date": visit.isoformat(), "value_as_number": round(v, 2),
                "unit_source_value": OMOP[cid],
            })
            meas_id += 1

    pd.DataFrame(participants).to_csv(out / "participants.tsv", sep="\t", index=False)
    pd.DataFrame(persons).to_csv(out / "clinical_data" / "person.csv", index=False)
    pd.DataFrame(visits).to_csv(out / "clinical_data" / "visit_occurrence.csv", index=False)
    pd.DataFrame(measurements).to_csv(out / "clinical_data" / "measurement.csv", index=False)
    pd.DataFrame(columns=["person_id", "condition_concept_id"]).to_csv(
        out / "clinical_data" / "condition_occurrence.csv", index=False)
    (out / "dataset_description.json").write_text(json.dumps({
        "name": "Synthetic AI-READI-shaped test fixture",
        "synthetic": True,
        "note": "Random values only. Not derived from AI-READI. For tests and demos.",
        "n_participants": args.n, "seed": args.seed,
    }, indent=2))
    print(f"Wrote synthetic dataset with {args.n} participants to {out}")


if __name__ == "__main__":
    main()
