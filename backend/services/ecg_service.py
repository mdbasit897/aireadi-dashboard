"""
EDA service — three analytical tools for the AI-READI EDA dashboard:

1. Temporal Overlap: per-participant and cohort-level timeline of
   CGM windows anchored to clinical visit dates, with ECG recording
   date extracted from WFDB .hea comment fields.

2. Co-missingness Matrix: how many participants in each study group
   have concurrent data across all modality combinations.

3. Signal Quality: CGM dropout rate, ECG quality flags from
   machine interpretation comments, wearable data density.

Parser coverage note (Q1):
   _parse_ecg_comments() extracts the recording date from the
   `validation_date` comment field (format: YYYYMMDD). If this field
   is absent or malformed, recording_date is returned as None and
   the frontend displays "—" in the Temporal Overlap timeline without
   raising an error. Parser success rate should be reported in the
   manuscript (see get_ecg_parser_coverage_report()).

Timezone note (Q2):
   All temporal alignment is performed at calendar-date granularity.
   CGM timestamps are stored in UTC (ISO 8601 with Z suffix);
   visit_occurrence dates are timezone-naive calendar dates; ECG
   validation_date is a bare YYYYMMDD string with no TZ annotation.
   Sub-day alignment cannot be guaranteed without site-specific UTC
   offset metadata and historical daylight saving time logs.
"""

import glob
import json
import logging
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd

from config import get_settings
from services.cohort_service import load_participants

logger = logging.getLogger(__name__)

# ── ECG comment parser ───────────────────────────────────────────────────────

def _parse_ecg_comments(comments: list[str]) -> dict[str, Any]:
    """
    Extracts structured metadata from WFDB .hea comment strings.
    Returns validation_date, device firmware, filter settings,
    interpretation flags, HR/PR/QT intervals.

    If `validation_date` is absent or cannot be parsed, recording_date
    is set to None. The caller and frontend treat None as a missing value
    (displayed as "—") rather than raising an error, so partial parse
    failures degrade gracefully.
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

    result["device_model"]    = meta.get("device_model", "Unknown")
    result["firmware"]        = meta.get("machine_detail_description", "")
    result["hp_filter"]       = meta.get("high_pass_filter_setting", "")
    result["lp_filter"]       = meta.get("low_pass_filter_setting", "")
    result["notch_filter"]    = meta.get("notch_filter_setting", "")
    result["artifact_filter"] = meta.get("artifact_filter_flag", "")

    # Automated interpretation
    result["interpretation"] = meta.get("interpretation_comment_2", "").strip(" -")
    result["sinus_rhythm"]   = "Sinus rhythm" in str(meta.get("comment_1_key", ""))

    # Interval measurements from header
    try:    result["hr"]   = int(meta.get("Rate", 0))
    except: result["hr"]   = None
    try:    result["pr"]   = int(meta.get("PR", 0))
    except: result["pr"]   = None
    try:    result["qrsd"] = int(meta.get("QRSD", 0))
    except: result["qrsd"] = None
    try:    result["qt"]   = int(meta.get("QT", 0))
    except: result["qt"]   = None
    try:    result["qtc"]  = int(meta.get("QTc", 0))
    except: result["qtc"]  = None

    # Quality flags — use interpretation_comment_2 as the authoritative
    # Philips machine verdict. This field contains one of four values:
    #   "- NORMAL ECG -"
    #   "- OTHERWISE NORMAL ECG -"   (minor finding, overall normal)
    #   "- BORDERLINE ECG -"
    #   "- ABNORMAL ECG -"
    #
    # has_abnormal_flag is True ONLY for strict "- ABNORMAL ECG -" verdict.
    # "OTHERWISE NORMAL" and "BORDERLINE" are surfaced separately so the
    # dashboard can present the full four-way distribution to the researcher.
    # Keyword matching against comment fields is intentionally NOT used here
    # because secondary comment_N_key annotations (e.g. "Minimal ST elevation")
    # appear on OTHERWISE NORMAL records and would produce false positives.
    interp_2 = meta.get("interpretation_comment_2", "").strip().upper()
    result["has_abnormal_flag"]       = "ABNORMAL ECG" in interp_2 and "OTHERWISE" not in interp_2
    result["is_otherwise_normal"]     = "OTHERWISE NORMAL" in interp_2
    result["is_borderline"]           = "BORDERLINE" in interp_2
    result["philips_verdict"]         = meta.get("interpretation_comment_2", "").strip()
    result["unconfirmed_diagnosis"]   = "Unconfirmed" in meta.get("interpretation_comment_1", "")

    return result


def _find_ecg_record(person_id: str) -> str | None:
    settings = get_settings()
    pattern1 = os.path.join(settings.ecg_dir, person_id, "*.hea")
    headers  = glob.glob(pattern1)
    if not headers:
        pattern2 = os.path.join(settings.ecg_dir, f"{person_id}*.hea")
        headers  = glob.glob(pattern2)
    return headers[0].replace(".hea", "") if headers else None


def get_ecg_metadata(person_id: str) -> dict[str, Any] | None:
    """Returns parsed ECG metadata including recording date and quality flags.

    recording_date is None when validation_date is absent from the .hea
    comment block; the frontend renders "—" in that case.
    """
    record_path = _find_ecg_record(person_id)
    if not record_path:
        return None
    try:
        import wfdb
        header = wfdb.rdheader(record_path)
        meta   = _parse_ecg_comments(header.comments or [])
        meta["person_id"]    = person_id
        meta["fs"]           = header.fs
        meta["sig_len"]      = header.sig_len
        meta["duration_sec"] = round(header.sig_len / header.fs, 2) if header.fs else None
        return meta
    except Exception as e:
        logger.debug("ECG metadata read failed for %s: %s", person_id, e)
        return None


# ── Q1: Parser coverage report ───────────────────────────────────────────────

def get_ecg_parser_coverage_report() -> dict[str, Any]:
    """
    Runs _parse_ecg_comments across ALL ECG participants and returns:
      - total_ecg_files   : number of participants with an ECG .hea file
      - date_parsed_n     : successfully extracted a recording_date
      - date_parsed_pct   : percentage of above
      - failure_modes     : dict of failure reason → count
          "missing_validation_date" : field absent from comments
          "malformed_date"          : field present but strptime failed
          "no_hea_file"             : .hea not found for participant with ECG flag

    Intended for offline reporting / manuscript verification; not exposed
    as a live API endpoint because it scans the full directory.
    """
    participants = load_participants()
    ecg_pids     = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()

    total_files     = 0
    date_parsed_n   = 0
    failure_modes   = {
        "missing_validation_date": 0,
        "malformed_date":          0,
        "no_hea_file":             0,
        "header_read_error":       0,
    }

    for pid in ecg_pids:
        record_path = _find_ecg_record(pid)
        if not record_path:
            failure_modes["no_hea_file"] += 1
            continue

        total_files += 1
        try:
            import wfdb
            header   = wfdb.rdheader(record_path)
            comments = header.comments or []

            # Replicate validation_date extraction logic exactly
            meta_raw: dict[str, str] = {}
            for c in comments:
                if ":" in c:
                    key, _, val = c.partition(":")
                    meta_raw[key.strip()] = val.strip()

            vd = meta_raw.get("validation_date", "")
            if not vd or len(vd) != 8:
                failure_modes["missing_validation_date"] += 1
            else:
                try:
                    datetime.strptime(vd, "%Y%m%d")
                    date_parsed_n += 1
                except ValueError:
                    failure_modes["malformed_date"] += 1

        except Exception:
            failure_modes["header_read_error"] += 1

    date_parsed_pct = round(date_parsed_n / total_files * 100, 1) if total_files else 0.0

    return {
        "total_ecg_participants_flagged": len(ecg_pids),
        "total_hea_files_found":          total_files,
        "date_parsed_n":                  date_parsed_n,
        "date_parsed_pct":                date_parsed_pct,
        "failure_modes":                  failure_modes,
    }


# ── CGM temporal helpers ─────────────────────────────────────────────────────

def _get_cgm_window(person_id: str) -> dict[str, Any] | None:
    """Returns CGM start/end dates and dropout rate for a participant.

    Timestamps are compared at calendar-date granularity; CGM data is
    stored in UTC (ISO 8601 with Z suffix) while visit_occurrence dates
    are timezone-naive. Sub-day alignment is not guaranteed.
    """
    settings = get_settings()
    primary  = os.path.join(
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
        expected   = max(1, days_covered * 288)
        actual     = len(timestamps)
        dropout_pct = round(max(0, (expected - actual) / expected) * 100, 1)

        return {
            "cgm_start":    timestamps[0][:10],   # calendar date, UTC
            "cgm_end":      timestamps[-1][:10],  # calendar date, UTC
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
    - CGM window (start/end, UTC-derived calendar dates)
    - ECG recording date (from .hea validation_date comment, or None)
    - Wearable coverage (days_covered)

    All date comparisons are at calendar-date granularity.
    """
    from services.omop_service import get_visit_dates

    visits   = get_visit_dates(person_id)
    cgm      = _get_cgm_window(person_id)
    ecg_meta = get_ecg_metadata(person_id)

    primary_visit_date = None
    if visits:
        for v in visits:
            if v["visit_start_date"]:
                primary_visit_date = v["visit_start_date"]
                break

    cgm_offset_days   = None
    cgm_duration_days = None
    if cgm and primary_visit_date:
        try:
            vd = datetime.strptime(primary_visit_date, "%Y-%m-%d").date()
            cd = datetime.strptime(cgm["cgm_start"], "%Y-%m-%d").date()
            cgm_offset_days   = (cd - vd).days
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
        # Timezone transparency (Q2): dates are calendar-date granularity only.
        # CGM timestamps derived from UTC; ECG date is a bare YYYYMMDD string;
        # visit date is a timezone-naive OMOP calendar date.
        "_tz_note": "calendar-date granularity; sub-day alignment not guaranteed",
    }


# ── Q7: Site- and group-stratified temporal overlap ──────────────────────────

@lru_cache(maxsize=1)
def get_temporal_overlap_cohort() -> dict[str, Any]:
    """
    Cohort-level temporal overlap summary.

    Returns:
      - Aggregate ECG/CGM presence counts (total and %)
      - Per-participant summary rows (has_cgm, has_ecg, visit_date)
      - NEW (Q7): site_group_breakdown — presence counts stratified by
        clinical_site × study_group, enabling site-level discrepancy checks.

    Sampling note (Q3): scans all participants for file presence (fast,
    O(N) filesystem stat) but does NOT perform full CGM parse for the
    cohort view; that is reserved for the Signal Quality module's 200-sample
    draw which uses a head-slice for guaranteed sub-second response.
    """
    from services.omop_service import _load_visit_occurrence

    participants = load_participants()
    visits_df    = _load_visit_occurrence()

    earliest_visits = (
        visits_df.sort_values("visit_start_date")
        .groupby("person_id")
        .first()
        .reset_index()[["person_id", "visit_start_date"]]
    )
    earliest_visits["visit_start_date"] = pd.to_datetime(
        earliest_visits["visit_start_date"], errors="coerce"
    )

    rows          = []
    ecg_dates_ok  = 0
    cgm_dates_ok  = 0
    both_ok       = 0

    settings = get_settings()

    # ── Per-participant file-presence scan ───────────────────────────────
    for _, part_row in participants.iterrows():
        pid = str(part_row["person_id"])

        visit_row  = earliest_visits[earliest_visits["person_id"] == pid]
        visit_date = None
        if not visit_row.empty:
            vd = visit_row.iloc[0]["visit_start_date"]
            if pd.notna(vd):
                visit_date = vd.date().isoformat()

        cgm_path = os.path.join(
            settings.dataset_root,
            "wearable_blood_glucose", "continuous_glucose_monitoring",
            "dexcom_g6", pid, f"{pid}_DEX.json",
        )
        has_cgm_file = os.path.exists(cgm_path)

        ecg_pattern  = os.path.join(settings.ecg_dir, pid, "*.hea")
        has_ecg_file = bool(glob.glob(ecg_pattern))

        row = {
            "person_id":    pid,
            "clinical_site": str(part_row.get("clinical_site", "")),
            "study_group":  str(part_row.get("study_group", "")),
            "visit_date":   visit_date,
            "has_cgm":      has_cgm_file,
            "has_ecg":      has_ecg_file,
            "cgm_days":     None,
            "cgm_dropout":  None,
            "cgm_offset":   None,
        }

        if has_cgm_file:
            cgm_dates_ok += 1
        if has_ecg_file:
            ecg_dates_ok += 1
        if has_cgm_file and has_ecg_file:
            both_ok += 1

        rows.append(row)

    total    = len(rows)
    cgm_pct  = round(cgm_dates_ok / total * 100, 1) if total else 0
    ecg_pct  = round(ecg_dates_ok / total * 100, 1) if total else 0
    both_pct = round(both_ok      / total * 100, 1) if total else 0

    # ── Q7: Site × study-group stratified breakdown ──────────────────────
    rows_df = pd.DataFrame(rows)

    SITE_ORDER  = ["UW", "UCSD", "UAB"]
    GROUP_SHORT = {
        "healthy":                                                                    "Healthy",
        "pre_diabetes_lifestyle_controlled":                                          "Pre-DM",
        "oral_medication_and_or_non_insulin_injectable_medication_controlled":        "Oral Med.",
        "insulin_dependent":                                                          "Insulin",
    }

    site_group_breakdown = []
    for site in SITE_ORDER:
        site_df = rows_df[rows_df["clinical_site"] == site]
        if site_df.empty:
            continue
        groups = []
        for grp_key, grp_label in GROUP_SHORT.items():
            g_df = site_df[site_df["study_group"] == grp_key]
            if g_df.empty:
                continue
            n         = len(g_df)
            n_cgm     = int(g_df["has_cgm"].sum())
            n_ecg     = int(g_df["has_ecg"].sum())
            n_both    = int((g_df["has_cgm"] & g_df["has_ecg"]).sum())
            groups.append({
                "study_group":       grp_key,
                "study_group_label": grp_label,
                "n":                 n,
                "n_cgm":             n_cgm,
                "n_ecg":             n_ecg,
                "n_both":            n_both,
                "cgm_pct":           round(n_cgm  / n * 100, 1),
                "ecg_pct":           round(n_ecg  / n * 100, 1),
                "both_pct":          round(n_both / n * 100, 1),
            })
        site_group_breakdown.append({
            "site":   site,
            "n":      len(site_df),
            "groups": groups,
        })

    return {
        "total_participants": total,
        "cgm_present_n":      cgm_dates_ok,
        "ecg_present_n":      ecg_dates_ok,
        "both_present_n":     both_ok,
        "cgm_pct":            cgm_pct,
        "ecg_pct":            ecg_pct,
        "both_pct":           both_pct,
        "participants":       rows,
        # Q7 addition
        "site_group_breakdown": site_group_breakdown,
        # Q3 transparency note
        "_sampling_note": (
            "File-presence scan covers all participants (O(N) stat, no CGM parse). "
            "Signal Quality module uses a head-slice of 200 participants for interactive "
            "performance; full-cohort quality statistics require an offline batch pipeline."
        ),
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
    df = load_participants()
    if study_group:
        df = df[df["study_group"] == study_group]

    present_cols = [c for c in MODALITY_COLS if c in df.columns]
    n_total      = len(df)

    matrix = []
    for col_a in present_cols:
        row = []
        for col_b in present_cols:
            count = int(df[col_a].sum()) if col_a == col_b else int((df[col_a] & df[col_b]).sum())
            row.append({
                "modality_a": col_a,
                "modality_b": col_b,
                "label_a":    MODALITY_SHORT.get(col_a, col_a),
                "label_b":    MODALITY_SHORT.get(col_b, col_b),
                "count":      count,
                "pct":        round(count / n_total * 100, 1) if n_total else 0,
            })
        matrix.append(row)

    group_breakdown = []
    for sg, sg_label in STUDY_GROUP_SHORT.items():
        sg_df = df[df["study_group"] == sg]
        if sg_df.empty:
            continue
        counts = {col: int(sg_df[col].sum()) for col in present_cols}
        group_breakdown.append({
            "study_group":       sg,
            "study_group_label": sg_label,
            "n":                 len(sg_df),
            "modality_counts":   counts,
        })

    n_modalities      = df[present_cols].sum(axis=1)
    completeness_hist = [
        {"n_modalities": n, "count": int((n_modalities == n).sum())}
        for n in range(0, len(present_cols) + 1)
    ]

    full_df       = load_participants()
    triple_overlap = []
    triple_cols   = ["cardiac_ecg", "wearable_blood_glucose", "clinical_data"]
    triple_present = [c for c in triple_cols if c in full_df.columns]
    if len(triple_present) == 3:
        for sg, sg_label in STUDY_GROUP_SHORT.items():
            sg_df    = full_df[full_df["study_group"] == sg]
            n_triple = int(sg_df[triple_present].all(axis=1).sum())
            triple_overlap.append({
                "study_group":       sg,
                "study_group_label": sg_label,
                "n_total":           len(sg_df),
                "n_triple":          n_triple,
                "pct":               round(n_triple / len(sg_df) * 100, 1) if len(sg_df) else 0,
            })

    return {
        "study_group":       study_group or "all",
        "n_total":           n_total,
        "modalities":        [{"key": c, "label": MODALITY_SHORT.get(c, c)} for c in present_cols],
        "matrix":            matrix,
        "group_breakdown":   group_breakdown,
        "completeness_hist": completeness_hist,
        "triple_overlap":    triple_overlap,
    }


# ── Signal Quality ───────────────────────────────────────────────────────────

def get_signal_quality_summary() -> dict[str, Any]:
    """
    Aggregate signal quality metrics across the cohort.

    Sampling strategy (Q3): uses a head-slice (first N in participants.tsv
    ordering) rather than a random or stratified draw. This guarantees
    sub-second API response for the interactive dashboard. The ordering
    in participants.tsv is determined by the AI-READI dataset creators
    and may correlate with enrollment date or site; a fully stratified
    offline pipeline is listed in the development roadmap.

    Reported hardware context (Q5): benchmarked on Azure Standard_D4s_v3
    (4 vCPU, 16 GiB RAM). Cold-start latency for this endpoint is
    reported in the manuscript; warm-cache latency for /api/cohort/summary
    is <50ms.
    """
    participants = load_participants()
    settings     = get_settings()

    # ── CGM quality (head-slice, N=200) ──────────────────────────────────
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
            "n_sampled":             len(cgm_dropouts),
            "n_total":               len(cgm_participants),
            "sampling_method":       "head-slice (first 200 in participants.tsv)",
            "mean_dropout_pct":      round(sum(cgm_dropouts) / len(cgm_dropouts), 1),
            "pct_under5_dropout":    round(sum(1 for d in cgm_dropouts if d < 5)  / len(cgm_dropouts) * 100, 1),
            "mean_duration_days":    round(sum(cgm_durations) / len(cgm_durations), 1),
            "duration_hist":         _make_histogram(cgm_durations, bins=[0, 5, 8, 10, 12, 15, 20, 30]),
            "dropout_hist":          _make_histogram(cgm_dropouts,  bins=[0, 2, 5, 10, 20, 50, 100]),
        }

    # ── ECG quality (head-slice, N=150) ──────────────────────────────────
    ecg_participants = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()
    ecg_sample       = ecg_participants[:150]

    # Four-way verdict counters (matches Philips interpretation_comment_2 values)
    ecg_strict_normal     = 0   # "- NORMAL ECG -"
    ecg_otherwise_normal  = 0   # "- OTHERWISE NORMAL ECG -"
    ecg_borderline        = 0   # "- BORDERLINE ECG -"
    ecg_strict_abnormal   = 0   # "- ABNORMAL ECG -"
    ecg_hr_vals  = []
    ecg_qtc_vals = []

    for pid in ecg_sample:
        meta = get_ecg_metadata(pid)
        if not meta:
            continue
        verdict = meta.get("philips_verdict", "").upper()
        if "ABNORMAL ECG" in verdict and "OTHERWISE" not in verdict:
            ecg_strict_abnormal += 1
        elif "OTHERWISE NORMAL" in verdict:
            ecg_otherwise_normal += 1
        elif "BORDERLINE" in verdict:
            ecg_borderline += 1
        else:
            ecg_strict_normal += 1
        if meta.get("hr"):
            ecg_hr_vals.append(meta["hr"])
        if meta.get("qtc"):
            ecg_qtc_vals.append(meta["qtc"])

    ecg_quality   = {}
    n_ecg_sampled = ecg_strict_normal + ecg_otherwise_normal + ecg_borderline + ecg_strict_abnormal
    if n_ecg_sampled:
        def pct(n): return round(n / n_ecg_sampled * 100, 1)
        ecg_quality = {
            "n_sampled":                  n_ecg_sampled,
            "n_total":                    len(ecg_participants),
            "sampling_method":            "head-slice (first 150 in participants.tsv)",
            # Four-way Philips verdict distribution
            "n_normal":                   ecg_strict_normal,
            "n_otherwise_normal":         ecg_otherwise_normal,
            "n_borderline":               ecg_borderline,
            "n_abnormal":                 ecg_strict_abnormal,
            "pct_normal":                 pct(ecg_strict_normal),
            "pct_otherwise_normal":       pct(ecg_otherwise_normal),
            "pct_borderline":             pct(ecg_borderline),
            "pct_abnormal_flag":          pct(ecg_strict_abnormal),  # kept for API compatibility
            # Interval measurements
            "mean_hr":               round(sum(ecg_hr_vals)  / len(ecg_hr_vals),  1) if ecg_hr_vals  else None,
            "mean_qtc":              round(sum(ecg_qtc_vals) / len(ecg_qtc_vals), 1) if ecg_qtc_vals else None,
            "hr_hist":               _make_histogram(ecg_hr_vals,  bins=[30, 50, 60, 70, 80, 90, 100, 120, 150]),
            "qtc_hist":              _make_histogram(ecg_qtc_vals, bins=[350, 380, 400, 420, 440, 460, 500]),
            "device_model":          "Philips PageWriter TC30",
            "firmware":              "A.07.07.07",
            "hp_filter_hz":          0.15,
            "lp_filter_hz":          100,
            "notch_filter_hz":       60,
            "sampling_rate_hz":      500,
        }

    return {
        "cgm": cgm_quality,
        "ecg": ecg_quality,
    }


def _make_histogram(values: list[float], bins: list[float]) -> list[dict]:
    if not values:
        return []
    result = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        count  = sum(1 for v in values if lo <= v < hi)
        result.append({"bin": f"{lo}–{hi}", "lo": lo, "hi": hi, "count": count})
    overflow = sum(1 for v in values if v >= bins[-1])
    if overflow:
        result.append({"bin": f"≥{bins[-1]}", "lo": bins[-1], "hi": None, "count": overflow})
    return result
