"""
Cohort service — loads participants.tsv and provides aggregate statistics.
All heavy computation is cached at startup so API responses are instant.
"""
import csv
import os
from collections import defaultdict, Counter
from functools import lru_cache
from typing import Any

import pandas as pd

from config import get_settings

STUDY_GROUP_META = {
    "healthy": {
        "label": "Healthy (no diabetes)",
        "color": "#1D9E75",
    },
    "pre_diabetes_lifestyle_controlled": {
        "label": "Pre-DM / Lifestyle controlled",
        "color": "#BA7517",
    },
    "oral_medication_and_or_non_insulin_injectable_medication_controlled": {
        "label": "Oral / Non-insulin medication",
        "color": "#378ADD",
    },
    "insulin_dependent": {
        "label": "Insulin dependent T2D",
        "color": "#D85A30",
    },
}

SITE_META = {
    "UW": "University of Washington",
    "UCSD": "University of California San Diego",
    "UAB": "University of Alabama at Birmingham",
}

MODALITY_META = {
    "cardiac_ecg": ("ECG (12-lead Philips)", "#378ADD"),
    "clinical_data": ("Clinical data (OMOP)", "#1D9E75"),
    "environment": ("Environmental sensor", "#888780"),
    "retinal_flio": ("Retinal FLIO", "#534AB7"),
    "retinal_oct": ("Retinal OCT", "#7F77DD"),
    "retinal_octa": ("Retinal OCTA", "#AFA9EC"),
    "retinal_photography": ("Retinal Photography", "#5DCAA5"),
    "wearable_activity_monitor": ("Wearable (Garmin)", "#EF9F27"),
    "wearable_blood_glucose": ("CGM (Dexcom G6)", "#D85A30"),
}


@lru_cache(maxsize=1)
def load_participants() -> pd.DataFrame:
    settings = get_settings()
    path = settings.participants_tsv
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"participants.tsv not found at {path}. "
            "Check DATASET_ROOT in your .env file."
        )
    df = pd.read_csv(path, sep="\t", dtype={"person_id": str})
    bool_cols = [
        "cardiac_ecg", "clinical_data", "environment",
        "retinal_flio", "retinal_oct", "retinal_octa",
        "retinal_photography", "wearable_activity_monitor",
        "wearable_blood_glucose",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper() == "TRUE"
    return df


def get_cohort_summary() -> dict[str, Any]:
    df = load_participants()
    n = len(df)

    study_groups = []
    for key, meta in STUDY_GROUP_META.items():
        count = int((df["study_group"] == key).sum())
        study_groups.append({
            "group": key,
            "label": meta["label"],
            "count": count,
            "color": meta["color"],
        })

    sites = [
        {"site": s, "label": SITE_META.get(s, s), "count": int((df["clinical_site"] == s).sum())}
        for s in ["UW", "UCSD", "UAB"]
    ]

    modalities = []
    for col, (label, color) in MODALITY_META.items():
        if col in df.columns:
            cnt = int(df[col].sum())
            modalities.append({
                "modality": col,
                "label": label,
                "count": cnt,
                "total": n,
                "pct": round(cnt / n * 100, 1),
                "color": color,
            })

    splits = [
        {"split": s, "count": int((df["recommended_split"] == s).sum())}
        for s in ["train", "val", "test"]
    ]

    ecg_cgm = int(
        (df["cardiac_ecg"] & df["wearable_blood_glucose"]).sum()
    )
    all_mod_cols = list(MODALITY_META.keys())
    all_present = int(df[[c for c in all_mod_cols if c in df.columns]].all(axis=1).sum())

    return {
        "total_participants": n,
        "age_min": int(df["age"].min()),
        "age_max": int(df["age"].max()),
        "age_mean": round(float(df["age"].mean()), 1),
        "dataset_size": "3.82 TB",
        "num_files": 356343,
        "collection_start": "2023-07-18",
        "collection_end": "2025-05-01",
        "study_groups": study_groups,
        "sites": sites,
        "modalities": modalities,
        "splits": splits,
        "ecg_cgm_overlap": ecg_cgm,
        "all_modalities_count": all_present,
    }


def get_age_distribution() -> list[dict]:
    df = load_participants()
    buckets = []
    for start in range(40, 95, 5):
        end = start + 4
        cnt = int(((df["age"] >= start) & (df["age"] <= end)).sum())
        buckets.append({"bucket": start, "label": f"{start}–{end}", "count": cnt})
    return buckets


def get_enrollment_timeline() -> list[dict]:
    df = load_participants()
    df["month"] = df["study_visit_date"].str[:7]
    monthly = df.groupby("month").size().reset_index(name="count")
    monthly = monthly.sort_values("month")
    monthly["cumulative"] = monthly["count"].cumsum()
    return monthly.to_dict(orient="records")


def get_site_group_matrix() -> list[dict]:
    df = load_participants()
    result = []
    for site in ["UW", "UCSD", "UAB"]:
        sub = df[df["clinical_site"] == site]
        result.append({
            "site": site,
            "healthy": int((sub["study_group"] == "healthy").sum()),
            "pre_diabetes": int((sub["study_group"] == "pre_diabetes_lifestyle_controlled").sum()),
            "oral_med": int((sub["study_group"] == "oral_medication_and_or_non_insulin_injectable_medication_controlled").sum()),
            "insulin": int((sub["study_group"] == "insulin_dependent").sum()),
        })
    return result


def get_participant_list(
    page: int = 1,
    page_size: int = 20,
    study_group: str | None = None,
    site: str | None = None,
    split: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    df = load_participants()

    if study_group:
        df = df[df["study_group"] == study_group]
    if site:
        df = df[df["clinical_site"] == site]
    if split:
        df = df[df["recommended_split"] == split]
    if search:
        df = df[df["person_id"].str.contains(search, case=False, na=False)]

    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start : start + page_size]

    participants = []
    for _, row in page_df.iterrows():
        participants.append({
            "person_id": str(row["person_id"]),
            "clinical_site": row["clinical_site"],
            "study_group": row["study_group"],
            "age": int(row["age"]),
            "study_visit_date": row["study_visit_date"],
            "recommended_split": row["recommended_split"],
            "has_ecg": bool(row.get("cardiac_ecg", False)),
            "has_cgm": bool(row.get("wearable_blood_glucose", False)),
            "has_wearable": bool(row.get("wearable_activity_monitor", False)),
            "has_retinal": bool(
                row.get("retinal_photography", False)
                or row.get("retinal_oct", False)
            ),
            "has_clinical": bool(row.get("clinical_data", False)),
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "participants": participants,
    }


def get_participant_detail(person_id: str) -> dict[str, Any] | None:
    df = load_participants()
    row = df[df["person_id"] == person_id]
    if row.empty:
        return None
    r = row.iloc[0]
    modality_cols = list(MODALITY_META.keys())
    modalities = {col: bool(r.get(col, False)) for col in modality_cols if col in df.columns}
    return {
        "person_id": str(r["person_id"]),
        "clinical_site": r["clinical_site"],
        "clinical_site_label": SITE_META.get(r["clinical_site"], r["clinical_site"]),
        "study_group": r["study_group"],
        "study_group_label": STUDY_GROUP_META.get(r["study_group"], {}).get("label", r["study_group"]),
        "age": int(r["age"]),
        "study_visit_date": r["study_visit_date"],
        "recommended_split": r["recommended_split"],
        "modalities": modalities,
    }
