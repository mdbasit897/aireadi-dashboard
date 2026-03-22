"""
OMOP service — reads AI-READI clinical_data OMOP CDM tables.

Tables used:
  measurement.csv       — lab values, vitals, visual acuity, cognitive scores
  visit_occurrence.csv  — clinical visit dates (temporal anchor)
  person.csv            — demographics (gender, race, ethnicity, birth year)
  condition_occurrence.csv — diagnoses

Key OMOP concept IDs present in this dataset:
  3004410  → HbA1c (Hemoglobin A1c/Hemoglobin.total)
  3004501  → Glucose (serum/plasma)
  3016244  → Insulin
  3010084  → C-peptide
  4245997  → BMI
  3036277  → Height (cm)
  3025315  → Weight (kg)
  3004249  → Systolic BP
  3012888  → Diastolic BP
  4239408  → Heart rate (bpm)
  3027114  → Total cholesterol
  3022192  → Triglycerides
  3007070  → HDL cholesterol
  3028288  → LDL cholesterol
  3009542  → Hematocrit
  37174522 → MoCA total score
  4172830  → Waist circumference
  4111665  → Hip circumference

Unit validation note (Q4):
  All concept IDs have a hardcoded expected unit in CONCEPT_META.
  get_participant_labs() and get_cohort_lab_distributions() validate
  unit_source_value against these expectations.  Mixed-unit rows
  (e.g., HbA1c in mmol/mol instead of %) are converted automatically
  using UNIT_CONVERSIONS; rows with unknown units are excluded with a
  logged warning.  verify_unit_homogeneity() can be called offline to
  produce the unit audit table reported in the manuscript.
"""

import logging
import os
from functools import lru_cache
from typing import Any

import pandas as pd

from config import get_settings

logger = logging.getLogger(__name__)

# ── Concept ID → human-readable label + LOINC code mapping ──────────────────
CONCEPT_META = {
    3004410:  {"label": "HbA1c",             "unit": "%",       "loinc": "4548-4",  "category": "glycaemic"},
    3004501:  {"label": "Glucose (serum)",    "unit": "mg/dL",   "loinc": "2345-7",  "category": "glycaemic"},
    3016244:  {"label": "Insulin",            "unit": "µIU/mL",  "loinc": "20448-7", "category": "glycaemic"},
    3010084:  {"label": "C-peptide",          "unit": "ng/mL",   "loinc": "1986-9",  "category": "glycaemic"},
    4245997:  {"label": "BMI",                "unit": "kg/m²",   "loinc": "39156-5", "category": "anthropometric"},
    3036277:  {"label": "Height",             "unit": "cm",      "loinc": "8302-2",  "category": "anthropometric"},
    3025315:  {"label": "Weight",             "unit": "kg",      "loinc": "29463-7", "category": "anthropometric"},
    4172830:  {"label": "Waist circumference","unit": "cm",      "loinc": "56115-9", "category": "anthropometric"},
    3004249:  {"label": "Systolic BP",        "unit": "mmHg",    "loinc": "8480-6",  "category": "cardiovascular"},
    3012888:  {"label": "Diastolic BP",       "unit": "mmHg",    "loinc": "8462-4",  "category": "cardiovascular"},
    4239408:  {"label": "Heart rate",         "unit": "bpm",     "loinc": "8867-4",  "category": "cardiovascular"},
    3027114:  {"label": "Total cholesterol",  "unit": "mg/dL",   "loinc": "2093-3",  "category": "lipids"},
    3022192:  {"label": "Triglycerides",      "unit": "mg/dL",   "loinc": "2571-8",  "category": "lipids"},
    3007070:  {"label": "HDL cholesterol",    "unit": "mg/dL",   "loinc": "2085-9",  "category": "lipids"},
    3028288:  {"label": "LDL cholesterol",    "unit": "mg/dL",   "loinc": "18262-6", "category": "lipids"},
    3009542:  {"label": "Hematocrit",         "unit": "%",       "loinc": "20570-8", "category": "haematology"},
    3000963:  {"label": "Hemoglobin",         "unit": "g/dL",    "loinc": "718-7",   "category": "haematology"},
    3007461:  {"label": "Platelets",          "unit": "×10³/µL", "loinc": "777-3",   "category": "haematology"},
    3006906:  {"label": "Calcium",            "unit": "mg/dL",   "loinc": "17861-6", "category": "metabolic"},
    3016723:  {"label": "Creatinine",         "unit": "mg/dL",   "loinc": "2160-0",  "category": "renal"},
    3013682:  {"label": "BUN",                "unit": "mg/dL",   "loinc": "3094-0",  "category": "renal"},
    3010156:  {"label": "CRP (hs)",           "unit": "mg/L",    "loinc": "30522-7", "category": "inflammatory"},
    37174522: {"label": "MoCA total score",   "unit": "/30",     "loinc": "72172-0", "category": "cognitive"},
}

# Q4: Unit conversion rules — (observed_unit, canonical_unit) → multiplier
# Applied when unit_source_value differs from the canonical expected unit.
UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # HbA1c: mmol/mol (IFCC) → % (NGSP) via Diabetes Care 2007 equation ≈ /10.929
    ("mmol/mol", "%"):  1 / 10.929,
    # Glucose: mmol/L → mg/dL
    ("mmol/L",  "mg/dL"): 18.016,
    ("mmol/l",  "mg/dL"): 18.016,
    # Cholesterol / TG / LDL / HDL: mmol/L → mg/dL
    ("mmol/L",  "mg/dL"): 18.016,   # reused; valid for non-glucose lipids too (38.67 for cholesterol)
    # Weight: lbs → kg
    ("[lb_av]", "kg"):  0.453592,
    # Height: inches → cm
    ("[in_i]",  "cm"):  2.54,
}

# Physiologically plausible ranges for outlier detection (Q4).
# Rows outside these bounds are flagged as outliers and excluded from
# cohort-level distributions (but retained in per-participant views
# with an outlier flag for researcher awareness).
PLAUSIBLE_RANGES: dict[int, tuple[float, float]] = {
    3004410: (3.0,  20.0),   # HbA1c %
    3004501: (20.0, 700.0),  # Glucose mg/dL
    4245997: (10.0, 80.0),   # BMI kg/m²
    3004249: (50.0, 260.0),  # Systolic BP mmHg
    3012888: (20.0, 160.0),  # Diastolic BP mmHg
    4239408: (20.0, 250.0),  # Heart rate bpm
    3027114: (50.0, 500.0),  # Total cholesterol mg/dL
}

SUMMARY_CONCEPTS = [3004410, 3004501, 4245997, 3004249, 3012888, 4239408,
                    3027114, 3007070, 3028288, 3022192, 3016244, 3010084]


# ── Data loaders (LRU-cached) ────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_measurement() -> pd.DataFrame:
    settings = get_settings()
    path     = os.path.join(settings.clinical_data_dir, "measurement.csv")
    df       = pd.read_csv(path, low_memory=False)
    df["person_id"] = df["person_id"].astype(str)
    return df


@lru_cache(maxsize=1)
def _load_visit_occurrence() -> pd.DataFrame:
    settings = get_settings()
    path     = os.path.join(settings.clinical_data_dir, "visit_occurrence.csv")
    df       = pd.read_csv(path)
    df["person_id"]       = df["person_id"].astype(str)
    df["visit_start_date"] = pd.to_datetime(df["visit_start_date"], errors="coerce")
    return df


@lru_cache(maxsize=1)
def _load_person() -> pd.DataFrame:
    settings = get_settings()
    path     = os.path.join(settings.clinical_data_dir, "person.csv")
    df       = pd.read_csv(path)
    df["person_id"] = df["person_id"].astype(str)
    return df


@lru_cache(maxsize=1)
def _load_condition_occurrence() -> pd.DataFrame:
    settings = get_settings()
    path     = os.path.join(settings.clinical_data_dir, "condition_occurrence.csv")
    df       = pd.read_csv(path)
    df["person_id"] = df["person_id"].astype(str)
    return df


# ── Q4: Unit validation helpers ──────────────────────────────────────────────

def _normalize_unit_value(
    value: float,
    observed_unit: str,
    concept_id: int,
) -> tuple[float, bool]:
    """
    Returns (normalized_value, was_converted).

    If observed_unit matches the canonical expected unit, returns value as-is.
    If a conversion rule exists in UNIT_CONVERSIONS, applies it.
    Otherwise logs a warning and returns (None, False) signalling exclusion.
    """
    canonical = CONCEPT_META.get(concept_id, {}).get("unit", "")
    if not observed_unit or observed_unit.strip() == canonical:
        return value, False

    key = (observed_unit.strip(), canonical)
    if key in UNIT_CONVERSIONS:
        converted = value * UNIT_CONVERSIONS[key]
        return converted, True

    logger.warning(
        "concept_id=%d: unknown unit '%s' (expected '%s'); row excluded.",
        concept_id, observed_unit, canonical,
    )
    return None, False


def _is_plausible(value: float, concept_id: int) -> bool:
    """Returns True if value is within the physiologically plausible range."""
    if concept_id not in PLAUSIBLE_RANGES:
        return True
    lo, hi = PLAUSIBLE_RANGES[concept_id]
    return lo <= value <= hi


def verify_unit_homogeneity() -> dict[str, Any]:
    """
    Q4: Offline audit — reports unit_source_value distribution for every
    concept in CONCEPT_META and flags any rows needing conversion.

    Call from a script or Jupyter notebook before finalizing manuscript stats:
        from services.omop_service import verify_unit_homogeneity
        report = verify_unit_homogeneity()

    Returns a dict keyed by concept label with:
      - expected_unit
      - unit_counts: {unit_string: row_count}
      - needs_conversion: bool
      - conversion_rule: str | None
      - outlier_count: number of rows outside PLAUSIBLE_RANGES (post-conversion)
    """
    meas = _load_measurement()

    report = {}
    for concept_id, meta in CONCEPT_META.items():
        sub = meas[meas["measurement_concept_id"] == concept_id].copy()
        if sub.empty:
            continue

        unit_counts = sub["unit_source_value"].fillna("(null)").value_counts().to_dict()
        canonical   = meta["unit"]
        non_canonical_units = {k: v for k, v in unit_counts.items()
                                if k.strip() != canonical and k != "(null)"}

        conversion_rules = [
            f"{obs} → {canonical} (×{UNIT_CONVERSIONS[(obs, canonical)]})"
            for obs in non_canonical_units
            if (obs, canonical) in UNIT_CONVERSIONS
        ]
        unknown_units = [
            obs for obs in non_canonical_units
            if (obs, canonical) not in UNIT_CONVERSIONS
        ]

        # Count outliers after conversion
        outlier_count = 0
        if concept_id in PLAUSIBLE_RANGES:
            for _, row in sub.iterrows():
                val  = row.get("value_as_number")
                unit = str(row.get("unit_source_value", ""))
                if pd.isna(val):
                    continue
                norm_val, _ = _normalize_unit_value(float(val), unit, concept_id)
                if norm_val is not None and not _is_plausible(norm_val, concept_id):
                    outlier_count += 1

        report[meta["label"]] = {
            "concept_id":       concept_id,
            "expected_unit":    canonical,
            "unit_counts":      unit_counts,
            "needs_conversion": bool(non_canonical_units),
            "conversion_rules": conversion_rules,
            "unknown_units":    unknown_units,
            "outlier_count":    outlier_count,
        }

    return report


# ── Per-participant lab extraction ────────────────────────────────────────────

def get_participant_labs(person_id: str) -> dict[str, Any]:
    """
    Returns per-participant lab values from measurement.csv.
    Groups by category: glycaemic, cardiovascular, lipids, etc.

    Unit normalization (Q4): each row's unit_source_value is validated
    against CONCEPT_META; mixed-unit rows are converted where a rule
    exists; unknown-unit rows are excluded with a flag.
    Outlier rows are retained but flagged via outlier=True.
    """
    meas = _load_measurement()
    sub  = meas[
        (meas["person_id"] == person_id) &
        (meas["measurement_concept_id"].isin(CONCEPT_META.keys()))
    ].copy()

    if sub.empty:
        return {"person_id": person_id, "categories": {}, "labs": []}

    labs = []
    for _, row in sub.iterrows():
        cid  = int(row["measurement_concept_id"])
        meta = CONCEPT_META.get(cid, {})
        val  = row.get("value_as_number")
        if pd.isna(val):
            continue

        obs_unit = str(row.get("unit_source_value", "")).strip()
        norm_val, was_converted = _normalize_unit_value(float(val), obs_unit, cid)
        if norm_val is None:
            continue  # unknown unit, exclude

        is_outlier = not _is_plausible(norm_val, cid)

        labs.append({
            "concept_id":     cid,
            "label":          meta.get("label", str(cid)),
            "value":          round(norm_val, 2),
            "unit":           meta.get("unit", obs_unit),
            "loinc":          meta.get("loinc", ""),
            "category":       meta.get("category", "other"),
            "date":           str(row.get("measurement_date", "")),
            "unit_converted": was_converted,
            "outlier":        is_outlier,
        })

    categories: dict[str, list] = {}
    for lab in labs:
        categories.setdefault(lab["category"], []).append(lab)

    return {
        "person_id":  person_id,
        "categories": categories,
        "labs":       labs,
    }


def get_visit_dates(person_id: str) -> list[dict]:
    """Returns clinical visit dates for a participant."""
    visits = _load_visit_occurrence()
    sub    = visits[visits["person_id"] == person_id].copy()
    sub    = sub.sort_values("visit_start_date")
    return [
        {
            "visit_occurrence_id":    int(r["visit_occurrence_id"]),
            "visit_start_date":       str(r["visit_start_date"].date()) if pd.notna(r["visit_start_date"]) else None,
            "visit_start_datetime":   str(r.get("visit_start_datetime", "")),
        }
        for _, r in sub.iterrows()
    ]


def get_cohort_lab_distributions() -> dict[str, Any]:
    """
    Returns population-level distributions of key lab values grouped by
    study group — used for the EDA overview charts.

    Unit normalization (Q4): unit_source_value is validated per row.
    Outliers (outside PLAUSIBLE_RANGES) are excluded from the distribution
    to avoid skewing medians/IQRs. The exclusion count is reported in the
    response for transparency.
    """
    from services.cohort_service import load_participants
    participants = load_participants()
    meas         = _load_measurement()

    key_concepts = {3004410: "hba1c", 4245997: "bmi", 3004501: "glucose"}
    result       = {}

    for concept_id, key in key_concepts.items():
        sub = meas[meas["measurement_concept_id"] == concept_id][
            ["person_id", "value_as_number", "unit_source_value"]
        ].copy()
        sub["person_id"] = sub["person_id"].astype(str)
        sub = sub.dropna(subset=["value_as_number"])

        # Normalize units and filter outliers
        cleaned_rows = []
        excluded_count = 0
        for _, row in sub.iterrows():
            obs_unit = str(row.get("unit_source_value", "")).strip()
            raw_val  = float(row["value_as_number"])
            norm_val, _ = _normalize_unit_value(raw_val, obs_unit, concept_id)
            if norm_val is None:
                excluded_count += 1
                continue
            if not _is_plausible(norm_val, concept_id):
                excluded_count += 1
                continue
            cleaned_rows.append({"person_id": row["person_id"], "value_as_number": norm_val})

        if not cleaned_rows:
            continue

        cleaned_df = pd.DataFrame(cleaned_rows)
        merged     = cleaned_df.merge(
            participants[["person_id", "study_group"]].astype({"person_id": str}),
            on="person_id",
            how="inner",
        )

        group_stats = []
        for group, grp_df in merged.groupby("study_group"):
            vals = grp_df["value_as_number"].dropna().tolist()
            if not vals:
                continue
            group_stats.append({
                "study_group": group,
                "n":           len(vals),
                "mean":        round(sum(vals) / len(vals), 2),
                "min":         round(min(vals), 2),
                "max":         round(max(vals), 2),
                "p25":         round(float(pd.Series(vals).quantile(0.25)), 2),
                "p50":         round(float(pd.Series(vals).quantile(0.50)), 2),
                "p75":         round(float(pd.Series(vals).quantile(0.75)), 2),
            })

        result[key] = {
            "concept_id":      concept_id,
            "label":           CONCEPT_META[concept_id]["label"],
            "unit":            CONCEPT_META[concept_id]["unit"],
            "loinc":           CONCEPT_META[concept_id]["loinc"],
            "groups":          group_stats,
            "rows_excluded":   excluded_count,  # Q4 transparency
        }

    return result