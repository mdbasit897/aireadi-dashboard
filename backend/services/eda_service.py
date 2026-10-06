"""
EDA service — three analytical tools for the AI-READI EDA dashboard:

1. Temporal Overlap: per-participant and cohort-level timeline of
   CGM windows anchored to clinical visit dates, with the ECG date
   extracted from WFDB .hea comment fields.

2. Co-missingness Matrix: how many participants in each study group
   have concurrent data across all modality combinations.

3. Signal Quality: CGM dropout rate and the Philips PageWriter TC30
   four-way machine verdict (normal / otherwise normal / borderline /
   abnormal) read from interpretation_comment_2.

ECG date parsing:
   AI-READI WFDB headers leave base_date/base_time empty. The only date in
   the header is the `validation_date` comment (YYYYMMDD). Parsing rules:
     1. split each comment line at the first ':' into key and value;
     2. take the value of key `validation_date`;
     3. accept it only if it is exactly 8 digits and a valid calendar date.
   Failures are classified as missing / malformed / no_hea_file /
   header_read_error and the date is returned as None (shown as "—").
   Whether validation_date is the acquisition date is checked by
   scripts/ecg_date_audit.py, not assumed here.

Timezone note:
   All temporal alignment is performed at calendar-date granularity.
   CGM timestamps are stored in UTC (ISO 8601 with Z suffix);
   visit_occurrence dates are timezone-naive calendar dates; ECG
   validation_date is a bare YYYYMMDD string with no TZ annotation.

Full-cohort results:
   The offline pipeline in scripts/ writes JSON files to settings.results_dir.
   When results/quality_full.json exists, /api/eda/signal-quality serves the
   full-cohort statistics; otherwise it computes a seeded, study-group-
   stratified random sample live and labels it as such.
"""

import glob
import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Any

import pandas as pd

from config import get_settings
from services.cohort_service import load_participants
from services.readiness_service import (
    DEFAULT_TAU_DAYS,
    classify_philips_verdict,
    cgm_readings_from_omh,
    comments_to_dict,
    make_histogram,
    parse_yyyymmdd,
    stratified_sample,
    summarise_cgm,
    summarise_quality,
    to_int_or_none,
)

logger = logging.getLogger(__name__)

LIVE_SAMPLE_CGM = 200
LIVE_SAMPLE_ECG = 150
LIVE_SAMPLE_SEED = 42

# ── ECG comment parser ───────────────────────────────────────────────────────

def _parse_ecg_comments(comments: list[str]) -> dict[str, Any]:
    """
    Extracts structured metadata from WFDB .hea comment strings.
    Returns the validation_date, device firmware, filter settings,
    the Philips machine verdict and HR/PR/QRS/QT/QTc intervals.

    If `validation_date` is absent or cannot be parsed, recording_date
    is set to None and recording_date_failure names the reason.
    """
    meta = comments_to_dict(comments)
    result: dict[str, Any] = {}

    d, failure = parse_yyyymmdd(meta.get("validation_date"))
    result["recording_date"]         = d.isoformat() if d else None
    result["recording_date_failure"] = failure

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
    result["hr"]   = to_int_or_none(meta.get("Rate"))
    result["pr"]   = to_int_or_none(meta.get("PR"))
    result["qrsd"] = to_int_or_none(meta.get("QRSD"))
    result["qt"]   = to_int_or_none(meta.get("QT"))
    result["qtc"]  = to_int_or_none(meta.get("QTc"))

    # Quality flags — interpretation_comment_2 is the authoritative Philips
    # machine verdict: "- NORMAL ECG -", "- OTHERWISE NORMAL ECG -",
    # "- BORDERLINE ECG -" or "- ABNORMAL ECG -". Keyword matching over the
    # other comment fields is intentionally NOT used: secondary annotations
    # (e.g. "Minimal ST elevation") appear on OTHERWISE NORMAL records and
    # would produce false positives.
    verdict = classify_philips_verdict(meta.get("interpretation_comment_2"))
    result["ecg_verdict"]           = verdict
    result["philips_verdict"]       = meta.get("interpretation_comment_2", "").strip()
    result["has_abnormal_flag"]     = verdict == "abnormal"
    result["is_otherwise_normal"]   = verdict == "otherwise_normal"
    result["is_borderline"]         = verdict == "borderline"
    result["unconfirmed_diagnosis"] = "Unconfirmed" in meta.get("interpretation_comment_1", "")

    return result


def _find_ecg_records(person_id: str) -> list[str]:
    """All WFDB record paths (without .hea) for a participant, sorted."""
    settings = get_settings()
    headers = glob.glob(os.path.join(settings.ecg_dir, person_id, "*.hea"))
    if not headers:
        headers = glob.glob(os.path.join(settings.ecg_dir, f"{person_id}*.hea"))
    return [h[: -len(".hea")] for h in sorted(headers)]


def _find_ecg_record(person_id: str) -> str | None:
    records = _find_ecg_records(person_id)
    return records[0] if records else None


def read_ecg_header(person_id: str) -> dict[str, Any]:
    """
    Reads the first WFDB header for a participant without loading the signal.
    Returns {"ok": False, "failure": "no_hea_file" | "header_read_error"} on
    failure, otherwise the raw comments plus header fields.
    """
    records = _find_ecg_records(person_id)
    if not records:
        return {"ok": False, "failure": "no_hea_file", "n_records": 0}
    try:
        import wfdb
        header = wfdb.rdheader(records[0])
    except Exception as e:  # noqa: BLE001 — any header problem is a read error
        logger.debug("ECG header read failed for %s: %s", person_id, e)
        return {"ok": False, "failure": "header_read_error", "n_records": len(records)}
    return {
        "ok":          True,
        "failure":     None,
        "record_path": records[0],
        "n_records":   len(records),
        "comments":    header.comments or [],
        "base_date":   header.base_date,
        "base_time":   header.base_time,
        "fs":          header.fs,
        "sig_len":     header.sig_len,
        "n_sig":       header.n_sig,
    }


def get_ecg_metadata(person_id: str) -> dict[str, Any] | None:
    """Returns parsed ECG metadata including recording date and quality flags.

    recording_date is None when validation_date is absent from the .hea
    comment block; the frontend renders "—" in that case.
    """
    h = read_ecg_header(person_id)
    if not h["ok"]:
        return None
    meta = _parse_ecg_comments(h["comments"])
    meta["person_id"]    = person_id
    meta["fs"]           = h["fs"]
    meta["sig_len"]      = h["sig_len"]
    meta["duration_sec"] = round(h["sig_len"] / h["fs"], 2) if h["fs"] else None
    meta["n_records"]    = h["n_records"]
    return meta


def get_ecg_parser_coverage_report() -> dict[str, Any]:
    """
    Runs the validation_date parser across ALL participants flagged with ECG.
    Returns extraction coverage and a breakdown of failure modes. This
    measures whether a date can be extracted, not whether it is the
    acquisition date — see scripts/ecg_date_audit.py for that check.
    """
    participants = load_participants()
    ecg_pids = participants[participants["cardiac_ecg"] == True]["person_id"].astype(str).tolist()

    failure_modes = {"missing": 0, "malformed": 0, "no_hea_file": 0, "header_read_error": 0}
    total_files = date_parsed_n = 0
    for pid in ecg_pids:
        h = read_ecg_header(pid)
        if not h["ok"]:
            failure_modes[h["failure"]] += 1
            continue
        total_files += 1
        d, failure = parse_yyyymmdd(comments_to_dict(h["comments"]).get("validation_date"))
        if d:
            date_parsed_n += 1
        else:
            failure_modes[failure] += 1

    return {
        "total_ecg_participants_flagged": len(ecg_pids),
        "total_hea_files_found":          total_files,
        "date_parsed_n":                  date_parsed_n,
        "date_parsed_pct":                round(date_parsed_n / total_files * 100, 1) if total_files else 0.0,
        "failure_modes":                  failure_modes,
    }


# ── CGM helpers ──────────────────────────────────────────────────────────────

def _cgm_path(person_id: str) -> str | None:
    settings = get_settings()
    primary = os.path.join(settings.cgm_dir, person_id, f"{person_id}_DEX.json")
    if os.path.exists(primary):
        return primary
    files = sorted(glob.glob(os.path.join(settings.cgm_dir, person_id, "*.json")))
    return files[0] if files else None


def _get_cgm_window(person_id: str) -> dict[str, Any] | None:
    """Returns CGM start/end dates, dropout and glucose summary for a participant.

    Timestamps are compared at calendar-date granularity; CGM data is
    stored in UTC (ISO 8601 with Z suffix) while visit_occurrence dates
    are timezone-naive. Sub-day alignment is not guaranteed.
    """
    path = _cgm_path(person_id)
    if not path:
        return None
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    stamps, values = cgm_readings_from_omh(doc)
    return summarise_cgm(stamps, values)


# ── Visit dates ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def earliest_visit_dates() -> dict[str, str]:
    """person_id → earliest OMOP visit_start_date (ISO calendar date)."""
    from services.omop_service import _load_visit_occurrence

    visits = _load_visit_occurrence()
    earliest = (
        visits.dropna(subset=["visit_start_date"])
        .sort_values("visit_start_date")
        .groupby("person_id")
        .first()["visit_start_date"]
    )
    return {str(pid): d.date().isoformat() for pid, d in earliest.items()}


def _days_between(a: str | None, b: str | None) -> int | None:
    """(a − b) in whole days, for ISO calendar dates."""
    if not a or not b:
        return None
    try:
        return (datetime.fromisoformat(a).date() - datetime.fromisoformat(b).date()).days
    except ValueError:
        return None


def extract_participant_readiness(person_id: str, row: pd.Series | dict | None = None) -> dict[str, Any]:
    """
    One flat record per participant covering all three readiness axes.
    This is the row format of results/participant_readiness.csv.
    """
    row = row if row is not None else {}
    get = row.get if hasattr(row, "get") else (lambda k, d=None: d)

    visit = earliest_visit_dates().get(person_id)
    rec: dict[str, Any] = {
        "person_id":         person_id,
        "clinical_site":     get("clinical_site"),
        "study_group":       get("study_group"),
        "recommended_split": get("recommended_split"),
        "age":               get("age"),
        "flag_ecg":          bool(get("cardiac_ecg", False)),
        "flag_cgm":          bool(get("wearable_blood_glucose", False)),
        "has_clinical":      bool(get("clinical_data", False)),
        "visit_date":        visit,
        "visit_date_tsv":    get("study_visit_date"),
    }

    # ECG
    h = read_ecg_header(person_id)
    rec["has_ecg_file"]     = h["failure"] != "no_hea_file"
    rec["ecg_n_records"]    = h.get("n_records", 0)
    rec["ecg_header_ok"]    = h["ok"]
    rec["ecg_base_date_set"] = bool(h.get("base_date")) if h["ok"] else None
    if h["ok"]:
        meta = _parse_ecg_comments(h["comments"])
        rec.update({
            "ecg_date":         meta["recording_date"],
            "ecg_date_failure": meta["recording_date_failure"],
            "ecg_verdict":      meta["ecg_verdict"],
            "ecg_hr":           meta["hr"],
            "ecg_pr":           meta["pr"],
            "ecg_qrsd":         meta["qrsd"],
            "ecg_qt":           meta["qt"],
            "ecg_qtc":          meta["qtc"],
            "ecg_firmware":     meta["firmware"],
        })
    else:
        rec.update({"ecg_date": None, "ecg_date_failure": h["failure"], "ecg_verdict": None})

    # CGM
    cgm = _get_cgm_window(person_id)
    rec["has_cgm_file"] = _cgm_path(person_id) is not None
    if cgm:
        rec.update({
            "cgm_start":           cgm["cgm_start"],
            "cgm_end":             cgm["cgm_end"],
            "cgm_days":            cgm["days_covered"],
            "cgm_n_readings":      cgm["n_readings"],
            "cgm_dropout_pct":     cgm["dropout_pct"],
            "cgm_dropout_nominal_pct": cgm["dropout_nominal_pct"],
            "cgm_mean":            cgm.get("glucose_mean"),
            "cgm_sd":              cgm.get("glucose_sd"),
            "cgm_cv":              cgm.get("glucose_cv"),
            "cgm_tir":             cgm.get("tir_pct"),
            "cgm_tbr":             cgm.get("tbr_pct"),
            "cgm_tar":             cgm.get("tar_pct"),
            "cgm_gmi":             cgm.get("gmi_pct"),
        })

    # Temporal offsets (days, signed: modality − anchor)
    rec["cgm_offset_days"]     = _days_between(rec.get("cgm_start"), visit)
    rec["ecg_offset_days"]     = _days_between(rec.get("ecg_date"), visit)
    rec["ecg_cgm_offset_days"] = _days_between(rec.get("ecg_date"), rec.get("cgm_start"))
    rec["visit_tsv_offset_days"] = _days_between(
        str(rec["visit_date_tsv"])[:10] if rec["visit_date_tsv"] else None, visit
    )
    return rec


# ── Temporal Overlap ─────────────────────────────────────────────────────────

def get_temporal_overlap_participant(person_id: str, tau_days: int = DEFAULT_TAU_DAYS) -> dict[str, Any]:
    """
    Returns the full temporal timeline for a single participant:
    - Clinical visit date (from visit_occurrence.csv)
    - CGM window (start/end, UTC-derived calendar dates)
    - ECG date (from the .hea validation_date comment, or None)
    - Signed offsets from the visit and co-registration flags at tolerance tau

    All date comparisons are at calendar-date granularity.
    """
    from services.omop_service import get_visit_dates

    visits   = get_visit_dates(person_id)
    cgm      = _get_cgm_window(person_id)
    ecg_meta = get_ecg_metadata(person_id)

    primary_visit_date = next((v["visit_start_date"] for v in visits if v["visit_start_date"]), None)

    cgm_offset = _days_between(cgm["cgm_start"], primary_visit_date) if cgm else None
    ecg_date   = ecg_meta["recording_date"] if ecg_meta else None
    ecg_offset = _days_between(ecg_date, primary_visit_date)

    return {
        "person_id":          person_id,
        "visit_date":         primary_visit_date,
        "visits":             visits,
        "cgm_start":          cgm["cgm_start"]    if cgm else None,
        "cgm_end":            cgm["cgm_end"]       if cgm else None,
        "cgm_days":           cgm["days_covered"]  if cgm else None,
        "cgm_dropout_pct":    cgm["dropout_pct"]   if cgm else None,
        "cgm_dropout_nominal_pct": cgm["dropout_nominal_pct"] if cgm else None,
        "cgm_n_readings":     cgm["n_readings"]    if cgm else None,
        "cgm_offset_days":    cgm_offset,
        "ecg_recording_date": ecg_date,
        "ecg_offset_days":    ecg_offset,
        "ecg_hr":             ecg_meta.get("hr")   if ecg_meta else None,
        "ecg_qtc":            ecg_meta.get("qtc")  if ecg_meta else None,
        "ecg_interpretation": ecg_meta.get("interpretation") if ecg_meta else None,
        "ecg_verdict":        ecg_meta.get("ecg_verdict") if ecg_meta else None,
        "ecg_has_abnormal":   ecg_meta.get("has_abnormal_flag") if ecg_meta else None,
        "tau_days":           tau_days,
        "cgm_co_registered":  cgm_offset is not None and abs(cgm_offset) <= tau_days,
        "ecg_co_registered":  ecg_offset is not None and abs(ecg_offset) <= tau_days,
        "_tz_note": "calendar-date granularity; sub-day alignment not guaranteed",
    }


@lru_cache(maxsize=1)
def get_temporal_overlap_cohort() -> dict[str, Any]:
    """
    Cohort-level file-presence summary for ECG and CGM, overall and
    stratified by clinical_site × study_group. Scans all participants
    (O(N) filesystem stat, no CGM parse). Cohort-wide temporal offsets
    come from the offline audit (see get_temporal_offsets()).
    """
    participants = load_participants()
    visits       = earliest_visit_dates()
    settings     = get_settings()

    rows = []
    for _, part_row in participants.iterrows():
        pid = str(part_row["person_id"])
        has_cgm = os.path.exists(os.path.join(settings.cgm_dir, pid, f"{pid}_DEX.json"))
        has_ecg = bool(glob.glob(os.path.join(settings.ecg_dir, pid, "*.hea")))
        rows.append({
            "person_id":     pid,
            "clinical_site": str(part_row.get("clinical_site", "")),
            "study_group":   str(part_row.get("study_group", "")),
            "visit_date":    visits.get(pid),
            "has_cgm":       has_cgm,
            "has_ecg":       has_ecg,
        })

    rows_df = pd.DataFrame(rows)
    total   = len(rows_df)
    n_cgm   = int(rows_df["has_cgm"].sum()) if total else 0
    n_ecg   = int(rows_df["has_ecg"].sum()) if total else 0
    n_both  = int((rows_df["has_cgm"] & rows_df["has_ecg"]).sum()) if total else 0
    pct     = lambda k: round(k / total * 100, 1) if total else 0  # noqa: E731

    site_group_breakdown = []
    for site in ["UW", "UCSD", "UAB"]:
        site_df = rows_df[rows_df["clinical_site"] == site] if total else rows_df
        if site_df.empty:
            continue
        groups = []
        for grp_key, grp_label in STUDY_GROUP_SHORT.items():
            g_df = site_df[site_df["study_group"] == grp_key]
            if g_df.empty:
                continue
            n = len(g_df)
            k_cgm, k_ecg = int(g_df["has_cgm"].sum()), int(g_df["has_ecg"].sum())
            k_both = int((g_df["has_cgm"] & g_df["has_ecg"]).sum())
            groups.append({
                "study_group":       grp_key,
                "study_group_label": grp_label,
                "n":                 n,
                "n_cgm":             k_cgm,
                "n_ecg":             k_ecg,
                "n_both":            k_both,
                "cgm_pct":           round(k_cgm  / n * 100, 1),
                "ecg_pct":           round(k_ecg  / n * 100, 1),
                "both_pct":          round(k_both / n * 100, 1),
            })
        site_group_breakdown.append({"site": site, "n": len(site_df), "groups": groups})

    return {
        "total_participants":   total,
        "cgm_present_n":        n_cgm,
        "ecg_present_n":        n_ecg,
        "both_present_n":       n_both,
        "cgm_pct":              pct(n_cgm),
        "ecg_pct":              pct(n_ecg),
        "both_pct":             pct(n_both),
        "participants":         rows,
        "site_group_breakdown": site_group_breakdown,
        "_sampling_note": (
            "File-presence scan covers all participants. Cohort-wide temporal "
            "offsets are computed by scripts/ecg_date_audit.py and served by "
            "/api/eda/temporal-offsets."
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

    full_df        = load_participants()
    triple_overlap = []
    triple_cols    = ["cardiac_ecg", "wearable_blood_glucose", "clinical_data"]
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


# ── Precomputed results (offline pipeline) ───────────────────────────────────

def load_result(name: str) -> dict[str, Any] | None:
    """Loads results/<name> written by the scripts/ pipeline, or None."""
    path = os.path.join(get_settings().results_dir, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def get_temporal_offsets() -> dict[str, Any] | None:
    """Cohort-wide ECG/CGM/visit offset distributions from scripts/ecg_date_audit.py."""
    audit = load_result("ecg_date_audit.json")
    if audit is None:
        return None
    return {
        "offsets":        audit.get("offsets"),
        "interpretation": audit.get("validation_date_interpretation"),
        "extraction":     audit.get("extraction"),
        "_meta":          audit.get("_meta"),
    }


def get_readiness_funnel() -> dict[str, Any] | None:
    """Participants retained at each readiness gate, from scripts/full_cohort_quality.py."""
    quality = load_result("quality_full.json")
    if quality is None or "funnel" not in quality:
        return None
    return {"funnel": quality["funnel"], "params": quality.get("gate_params"), "_meta": quality.get("_meta")}


# ── Signal Quality ───────────────────────────────────────────────────────────

def get_signal_quality_summary(source: str = "auto") -> dict[str, Any]:
    """
    Aggregate signal-quality metrics.

    source="auto"        full-cohort results if results/quality_full.json
                         exists, otherwise a live stratified sample
    source="precomputed" full-cohort results only (FileNotFoundError if absent)
    source="sample"      live sample: a seeded random draw stratified by
                         study group (200 CGM, 150 ECG participants)
    """
    if source in ("auto", "precomputed"):
        full = load_result("quality_full.json")
        if full is not None:
            out = dict(full["summary"])
            out["source"] = "precomputed_full_cohort"
            out["_meta"] = full.get("_meta")
            return out
        if source == "precomputed":
            raise FileNotFoundError(
                "results/quality_full.json not found — run scripts/full_cohort_quality.py"
            )

    participants = load_participants()

    cgm_pool = participants[participants["wearable_blood_glucose"] == True]
    cgm_sample = stratified_sample(cgm_pool, LIVE_SAMPLE_CGM, "study_group", LIVE_SAMPLE_SEED)
    cgm_records = [w for w in (_get_cgm_window(str(p)) for p in cgm_sample["person_id"]) if w]

    ecg_pool = participants[participants["cardiac_ecg"] == True]
    ecg_sample = stratified_sample(ecg_pool, LIVE_SAMPLE_ECG, "study_group", LIVE_SAMPLE_SEED)
    ecg_records = []
    for pid in ecg_sample["person_id"]:
        meta = get_ecg_metadata(str(pid))
        if meta:
            ecg_records.append({"verdict": meta["ecg_verdict"], "hr": meta["hr"], "qtc": meta["qtc"]})

    method = (f"stratified random sample by study group (seed {LIVE_SAMPLE_SEED}); "
              "run scripts/full_cohort_quality.py for full-cohort statistics")
    out = summarise_quality(
        cgm_records, ecg_records,
        sampling_method=method,
        n_total_cgm=len(cgm_pool),
        n_total_ecg=len(ecg_pool),
    )
    if out["ecg"]:
        out["ecg"].update(ECG_PROVENANCE)
    out["source"] = "live_sample"
    return out


# Sensor provenance reported alongside ECG quality (identical across sites
# in AI-READI v3.0.0; verified per record by scripts/full_cohort_quality.py)
ECG_PROVENANCE = {
    "device_model":     "Philips PageWriter TC30",
    "firmware":         "A.07.07.07",
    "hp_filter_hz":     0.15,
    "lp_filter_hz":     100,
    "notch_filter_hz":  60,
    "sampling_rate_hz": 500,
}


def _make_histogram(values: list[float], bins: list[float]) -> list[dict]:
    return make_histogram(values, bins)
