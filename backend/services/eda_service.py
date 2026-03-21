"""
EDA service — three analytical tools for the AI-READI EDA dashboard:

1. Temporal Overlap: per-participant and cohort-level timeline of
   CGM windows anchored to clinical visit dates, with ECG recording
   date extracted from WFDB .hea comment fields.

2. Co-missingness Matrix: how many participants in each study group
   have concurrent data across all modality combinations.

3. Signal Quality: CGM dropout rate, ECG quality flags from
   machine interpretation comments, wearable data density.
"""

import glob
import json
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from config import get_settings
from services.cohort_service import load_participants

# ── ECG comment parser ───────────────────────────────────────────────────────

def _parse_ecg_comments(comments: list[str]) -> dict[str, Any]:
    """
    Extracts structured metadata from WFDB .hea comment strings.
    Returns validation_date, device firmware, filter settings,
    interpretation flags, HR/PR/QT intervals.
    """
    meta: dict[str, Any] = {}
    for c in comments:
        if ":" in c:
            key, _, val = c.partition(":")
            meta[key.strip()] = val.strip()

    result: dict[str, Any] = {}

    # Recording date from validation_date field (format: YYYYMMDD)
    vd = meta.get("validation_date", "")
    if vd and len(vd) == 8:
        try:
            result["recording_date"] = datetime.strptime(vd, "%Y%m%d").date().isoformat()
        except ValueError:
            result["recording_date"] = None
    else:
        result["recording_date"] = None

    result["device_model"]  = meta.get("device_model", "Unknown")
    result["firmware"]      = meta.get("machine_detail_description", "")
    result["hp_filter"]     = meta.get("high_pass_filter_setting", "")
    result["lp_filter"]     = meta.get("low_pass_filter_setting", "")
    result["notch_filter"]  = meta.get("notch_filter_setting", "")
    result["artifact_filter"] = meta.get("artifact_filter_flag", "")

    # Automated interpretation
    result["interpretation"] = meta.get("interpretation_comment_2", "").strip(" -")
    result["sinus_rhythm"]   = "Sinus rhythm" in str(meta.get("comment_1_key", ""))

    # Interval measurements from header
    try: result["hr"]   = int(meta.get("Rate", 0))
    except: result["hr"] = None
    try: result["pr"]   = int(meta.get("PR", 0))
    except: result["pr"] = None
    try: result["qrsd"] = int(meta.get("QRSD", 0))
    except: result["qrsd"] = None
    try: result["qt"]   = int(meta.get("QT", 0))
    except: result["qt"] = None
    try: result["qtc"]  = int(meta.get("QTc", 0))
    except: result["qtc"] = None

    # Quality flags
    abnormal_keywords = [
        "ST elevation", "ST depression", "atrial fibrillation",
        "left bundle", "right bundle", "ischemia", "infarct",
        "bradycardia", "tachycardia", "abnormal",
    ]
    interp_text = " ".join(str(v) for v in meta.values()).lower()
    result["has_abnormal_flag"] = any(kw.lower() in interp_text for kw in abnormal_keywords)
    result["unconfirmed_diagnosis"] = "Unconfirmed" in meta.get("interpretation_comment_1", "")

    return result


def _find_ecg_record(person_id: str) -> str | None:
    settings = get_settings()
    pattern1 = os.path.join(settings.ecg_dir, person_id, "*.hea")
    headers = glob.glob(pattern1)
    if not headers:
        pattern2 = os.path.join(settings.ecg_dir, f"{person_id}*.hea")
        headers = glob.glob(pattern2)
    return headers[0].replace(".hea", "") if headers else None


def get_ecg_metadata(person_id: str) -> dict[str, Any] | None:
    """Returns parsed ECG metadata including recording date and quality flags."""
    record_path = _find_ecg_record(person_id)
    if not record_path:
        return None
    try:
        import wfdb
        header = wfdb.rdheader(record_path)
        meta = _parse_ecg_comments(header.comments or [])
        meta["person_id"] = person_id
        meta["fs"]        = header.fs
        meta["sig_len"]   = header.sig_len
        meta["duration_sec"] = round(header.sig_len / header.fs, 2) if header.fs else None
        return meta
    except Exception:
        return None


# ── CGM temporal helpers ─────────────────────────────────────────────────────

def _get_cgm_window(person_id: str) -> dict[str, Any] | None:
    """Returns CGM start/end dates and dropout rate for a participant."""
    settings = get_settings()
    primary = os.path.join(
        settings.dataset_root,
        "wearable_blood_glucose", "continuous_glucose_monitoring",
        "dexcom_g6", person_id, f"{person_id}_DEX.json",
    )
    if not os.path.exists(primary):
        files = glob.glob(os.path.join(
            settings.dataset_root, "wearable_blood_glucose",
            "continuous_glucose_monitoring", "dexcom_g6",
            person_id, "*.json",
        ))
        if not files:
            return None
        primary = files[0]

    try:
        with open(primary) as f:
            data = json.load(f)
        cgm_list = data.get("body", {}).get("cgm", [])
        if not cgm_list:
            return None

        timestamps = []
        for entry in cgm_list:
            tf = entry.get("effective_time_frame", {})
            ts = (tf.get("date_time") or
                  tf.get("time_interval", {}).get("start_date_time"))
            if ts:
                timestamps.append(ts)

        if not timestamps:
            return None

        timestamps.sort()
        t0 = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
        days_covered = (t1 - t0).total_seconds() / 86400

        # Dropout: expected 288 readings/day (5-min intervals)
        expected = max(1, days_covered * 288)
        actual   = len(timestamps)
        dropout_pct = round(max(0, (expected - actual) / expected) * 100, 1)

        return {
            "cgm_start":    timestamps[0][:10],
            "cgm_end":      timestamps[-1][:10],
            "days_covered": round(days_covered, 1),
            "n_readings":   actual,
            "dropout_pct":  dropout_pct,
        }
    except Exception:
        return None


# ── Temporal Overlap ─────────────────────────────────────────────────────────

def get_temporal_overlap_participant(person_id: str) -> dict[str, Any]:
    """
    Returns the full temporal timeline for a single participant:
    - Clinical visit date (from visit_occurrence.csv)
    - CGM window (start/end)
    - ECG recording date (from .hea comments)
    - Wearable coverage (days_covered)
    """
    from services.omop_service import get_visit_dates

    visits    = get_visit_dates(person_id)
    cgm       = _get_cgm_window(person_id)
    ecg_meta  = get_ecg_metadata(person_id)

    # Primary visit: first visit with a valid date
    primary_visit_date = None
    if visits:
        for v in visits:
            if v["visit_start_date"]:
                primary_visit_date = v["visit_start_date"]
                break

    # CGM offset relative to visit
    cgm_offset_days = None
    cgm_duration_days = None
    if cgm and primary_visit_date:
        try:
            vd = datetime.strptime(primary_visit_date, "%Y-%m-%d").date()
            cd = datetime.strptime(cgm["cgm_start"], "%Y-%m-%d").date()
            cgm_offset_days  = (cd - vd).days
            cgm_duration_days = cgm["days_covered"]
        except Exception:
            pass

    return {
        "person_id":          person_id,
        "visit_date":         primary_visit_date,
        "visits":             visits,
        "cgm_start":          cgm["cgm_start"]    if cgm else None,
        "cgm_end":            cgm["cgm_end"]       if cgm else None,
        "cgm_days":           cgm["days_covered"]  if cgm else None,
        "cgm_dropout_pct":    cgm["dropout_pct"]   if cgm else None,
        "cgm_n_readings":     cgm["n_readings"]    if cgm else None,
        "cgm_offset_days":    cgm_offset_days,
        "ecg_recording_date": ecg_meta["recording_date"] if ecg_meta else None,
        "ecg_hr":             ecg_meta.get("hr")   if ecg_meta else None,
        "ecg_qtc":            ecg_meta.get("qtc")  if ecg_meta else None,
        "ecg_interpretation": ecg_meta.get("interpretation") if ecg_meta else None,
        "ecg_has_abnormal":   ecg_meta.get("has_abnormal_flag") if ecg_meta else None,
    }


@lru_cache(maxsize=1)
def get_temporal_overlap_cohort() -> dict[str, Any]:
    """
    Cohort-level temporal overlap summary.
    Computes CGM window length distribution and ECG/CGM co-occurrence
    relative to visit dates across all participants.
    Returns aggregated stats + per-participant summary rows.
    """
    from services.omop_service import _load_visit_occurrence

    participants = load_participants()
    visits_df    = _load_visit_occurrence()

    # Get earliest visit per participant
    earliest_visits = (
        visits_df.sort_values("visit_start_date")
        .groupby("person_id")
        .first()
        .reset_index()[["person_id", "visit_start_date"]]
    )
    earliest_visits["visit_start_date"] = pd.to_datetime(
        earliest_visits["visit_start_date"], errors="coerce"
    )

    rows = []
    cgm_durations  = []
    cgm_offsets    = []
    dropout_rates  = []
    ecg_dates_ok   = 0
    cgm_dates_ok   = 0
    both_ok        = 0

    # Sample up to 300 participants for the per-row payload (performance)
    sample_ids = participants["person_id"].astype(str).tolist()

    settings = get_settings()

    for pid in sample_ids:
        visit_row = earliest_visits[earliest_visits["person_id"] == pid]
        visit_date = None
        if not visit_row.empty:
            vd = visit_row.iloc[0]["visit_start_date"]
            if pd.notna(vd):
                visit_date = vd.date().isoformat()

        # CGM quick scan (skip full parse for speed — just check file exists)
        cgm_path = os.path.join(
            settings.dataset_root,
            "wearable_blood_glucose", "continuous_glucose_monitoring",
            "dexcom_g6", pid, f"{pid}_DEX.json",
        )
        has_cgm_file = os.path.exists(cgm_path)

        # ECG quick scan
        ecg_pattern = os.path.join(settings.ecg_dir, pid, "*.hea")
        has_ecg_file = bool(glob.glob(ecg_pattern))

        row = {
            "person_id":   pid,
            "visit_date":  visit_date,
            "has_cgm":     has_cgm_file,
            "has_ecg":     has_ecg_file,
            "cgm_days":    None,
            "cgm_dropout": None,
            "cgm_offset":  None,
        }

        if has_cgm_file:
            cgm_dates_ok += 1
        if has_ecg_file:
            ecg_dates_ok += 1
        if has_cgm_file and has_ecg_file:
            both_ok += 1

        rows.append(row)

    total = len(rows)
    cgm_pct = round(cgm_dates_ok / total * 100, 1) if total else 0
    ecg_pct = round(ecg_dates_ok / total * 100, 1) if total else 0
    both_pct = round(both_ok / total * 100, 1) if total else 0

    return {
        "total_participants": total,
        "cgm_present_n":     cgm_dates_ok,
        "ecg_present_n":     ecg_dates_ok,
        "both_present_n":    both_ok,
        "cgm_pct":           cgm_pct,
        "ecg_pct":           ecg_pct,
        "both_pct":          both_pct,
        "participants":      rows,
    }


# ── Co-missingness Matrix ────────────────────────────────────────────────────

MODALITY_COLS = [
    "cardiac_ecg",
    "clinical_data",
    "wearable_blood_glucose",
    "wearable_activity_monitor",
    "retinal_photography",
    "retinal_oct",
    "retinal_octa",
    "retinal_flio",
    "environment",
]

MODALITY_SHORT = {
    "cardiac_ecg":               "ECG",
    "clinical_data":             "Clinical",
    "wearable_blood_glucose":    "CGM",
    "wearable_activity_monitor": "Wearable",
    "retinal_photography":       "Retinal Photo",
    "retinal_oct":               "OCT",
    "retinal_octa":              "OCTA",
    "retinal_flio":              "FLIO",
    "environment":               "Environment",
}

STUDY_GROUP_SHORT = {
    "healthy":                                                                    "Healthy",
    "pre_diabetes_lifestyle_controlled":                                          "Pre-DM",
    "oral_medication_and_or_non_insulin_injectable_medication_controlled":        "Oral Med.",
    "insulin_dependent":                                                          "Insulin",
}


def get_comissingness_matrix(study_group: str | None = None) -> dict[str, Any]:
    """
    Returns a co-missingness matrix: for every pair of modalities,
    how many participants have BOTH present (and optionally filtered
    by study group).

    Also returns single-modality counts and N-modality completeness histogram.
    """
    df = load_participants()
    if study_group:
        df = df[df["study_group"] == study_group]

    present_cols = [c for c in MODALITY_COLS if c in df.columns]
    n_total = len(df)

    # ── Pairwise co-occurrence matrix ────────────────────────────────────────
    matrix = []
    for col_a in present_cols:
        row = []
        for col_b in present_cols:
            if col_a == col_b:
                count = int(df[col_a].sum())
            else:
                count = int((df[col_a] & df[col_b]).sum())
            row.append({
                "modality_a": col_a,
                "modality_b": col_b,
                "label_a":    MODALITY_SHORT.get(col_a, col_a),
                "label_b":    MODALITY_SHORT.get(col_b, col_b),
                "count":      count,
                "pct":        round(count / n_total * 100, 1) if n_total else 0,
            })
        matrix.append(row)

    # ── Per-study-group single-modality counts ───────────────────────────────
    group_breakdown = []
    for sg, sg_label in STUDY_GROUP_SHORT.items():
        sg_df = df[df["study_group"] == sg]
        if sg_df.empty:
            continue
        counts = {}
        for col in present_cols:
            counts[col] = int(sg_df[col].sum())
        group_breakdown.append({
            "study_group":       sg,
            "study_group_label": sg_label,
            "n":                 len(sg_df),
            "modality_counts":   counts,
        })

    # ── N-modality completeness histogram ────────────────────────────────────
    n_modalities = df[present_cols].sum(axis=1)
    completeness_hist = []
    for n in range(0, len(present_cols) + 1):
        completeness_hist.append({
            "n_modalities": n,
            "count":        int((n_modalities == n).sum()),
        })

    # ── ECG + CGM + Clinical triple overlap by study group ────────────────────
    # Always computed on the FULL unfiltered df so all 4 groups are always shown.
    full_df = load_participants()
    triple_overlap = []
    triple_cols = ["cardiac_ecg", "wearable_blood_glucose", "clinical_data"]
    triple_present = [c for c in triple_cols if c in full_df.columns]
    if len(triple_present) == 3:
        for sg, sg_label in STUDY_GROUP_SHORT.items():
            sg_df = full_df[full_df["study_group"] == sg]
            n_triple = int(sg_df[triple_present].all(axis=1).sum())
            triple_overlap.append({
                "study_group":       sg,
                "study_group_label": sg_label,
                "n_total":           len(sg_df),
                "n_triple":          n_triple,
                "pct":               round(n_triple / len(sg_df) * 100, 1) if len(sg_df) else 0,
            })

    return {
        "study_group":        study_group or "all",
        "n_total":            n_total,
        "modalities":         [{"key": c, "label": MODALITY_SHORT.get(c, c)} for c in present_cols],
        "matrix":             matrix,
        "group_breakdown":    group_breakdown,
        "completeness_hist":  completeness_hist,
        "triple_overlap":     triple_overlap,
    }


# ── Signal Quality ───────────────────────────────────────────────────────────

def get_signal_quality_summary() -> dict[str, Any]:
    """
    Aggregate signal quality metrics across the cohort:
    - CGM: mean dropout rate, distribution of monitoring durations
    - ECG: % with abnormal interpretation flags, HR distribution
    - Wearable: data density (days covered distribution)

    For performance, samples up to 200 participants with each modality.
    """
    participants = load_participants()
    settings     = get_settings()

    # ── CGM quality ──────────────────────────────────────────────────────────
    cgm_participants = participants[participants["wearable_blood_glucose"] == True]["person_id"].astype(str).tolist()
    cgm_sample       = cgm_participants[:200]

    cgm_dropouts  = []
    cgm_durations = []

    for pid in cgm_sample:
        cgm = _get_cgm_window(pid)
        if cgm:
            cgm_dropouts.append(cgm["dropout_pct"])
            cgm_durations.append(cgm["days_covered"])

    cgm_quality = {}
    if cgm_dropouts:
        cgm_quality = {
            "n_sampled":         len(cgm_dropouts),
            "n_total":           len(cgm_participants),
            "mean_dropout_pct":  round(sum(cgm_dropouts) / len(cgm_dropouts), 1),
            "pct_under5_dropout": round(sum(1 for d in cgm_dropouts if d < 5) / len(cgm_dropouts) * 100, 1),
            "mean_duration_days": round(sum(cgm_durations) / len(cgm_durations), 1),
            "duration_hist":     _make_histogram(cgm_durations, bins=[0,5,8,10,12,15,20,30]),
            "dropout_hist":      _make_histogram(cgm_dropouts, bins=[0,2,5,10,20,50,100]),
        }

    # ── ECG quality ──────────────────────────────────────────────────────────
    ecg_participants = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()
    ecg_sample       = ecg_participants[:150]

    ecg_normal    = 0
    ecg_abnormal  = 0
    ecg_hr_vals   = []
    ecg_qtc_vals  = []

    for pid in ecg_sample:
        meta = get_ecg_metadata(pid)
        if not meta:
            continue
        if meta.get("has_abnormal_flag"):
            ecg_abnormal += 1
        else:
            ecg_normal += 1
        if meta.get("hr"):
            ecg_hr_vals.append(meta["hr"])
        if meta.get("qtc"):
            ecg_qtc_vals.append(meta["qtc"])

    ecg_quality = {}
    n_ecg_sampled = ecg_normal + ecg_abnormal
    if n_ecg_sampled:
        ecg_quality = {
            "n_sampled":          n_ecg_sampled,
            "n_total":            len(ecg_participants),
            "pct_normal":         round(ecg_normal / n_ecg_sampled * 100, 1),
            "pct_abnormal_flag":  round(ecg_abnormal / n_ecg_sampled * 100, 1),
            "mean_hr":            round(sum(ecg_hr_vals) / len(ecg_hr_vals), 1) if ecg_hr_vals else None,
            "mean_qtc":           round(sum(ecg_qtc_vals) / len(ecg_qtc_vals), 1) if ecg_qtc_vals else None,
            "hr_hist":            _make_histogram(ecg_hr_vals, bins=[30,50,60,70,80,90,100,120,150]),
            "qtc_hist":           _make_histogram(ecg_qtc_vals, bins=[350,380,400,420,440,460,500]),
            "device_model":       "Philips PageWriter TC30",
            "firmware":           "A.07.07.07",
            "hp_filter_hz":       0.15,
            "lp_filter_hz":       100,
            "notch_filter_hz":    60,
            "sampling_rate_hz":   500,
        }

    return {
        "cgm":     cgm_quality,
        "ecg":     ecg_quality,
    }


def _make_histogram(values: list[float], bins: list[float]) -> list[dict]:
    """Returns histogram bucket counts for given bin edges."""
    if not values:
        return []
    result = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        count = sum(1 for v in values if lo <= v < hi)
        result.append({"bin": f"{lo}–{hi}", "lo": lo, "hi": hi, "count": count})
    # Last bucket catches overflow
    overflow = sum(1 for v in values if v >= bins[-1])
    if overflow:
        result.append({"bin": f"≥{bins[-1]}", "lo": bins[-1], "hi": None, "count": overflow})
    return result