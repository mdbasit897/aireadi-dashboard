"""
EDA router — endpoints for the Exploratory Data Analysis dashboard.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.eda_service import (
    get_temporal_overlap_participant,
    get_temporal_overlap_cohort,
    get_temporal_offsets,
    get_readiness_funnel,
    get_comissingness_matrix,
    get_signal_quality_summary,
    get_ecg_metadata,
)
from services.omop_service import (
    get_participant_labs,
    get_cohort_lab_distributions,
)

router = APIRouter(prefix="/api/eda", tags=["eda"])


@router.get("/temporal-overlap/cohort")
def temporal_overlap_cohort():
    """
    Cohort-level temporal overlap summary.
    Returns presence counts for ECG/CGM/visit data + per-participant rows.
    """
    try:
        return get_temporal_overlap_cohort()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal-offsets")
def temporal_offsets():
    """
    Cohort-wide distributions of ECG−visit, CGM−visit and ECG−CGM offsets,
    overall and by site, with the extraction audit. Precomputed by
    scripts/ecg_date_audit.py.
    """
    data = get_temporal_offsets()
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Temporal offset audit not found. Run: python scripts/ecg_date_audit.py",
        )
    return data


@router.get("/readiness-funnel")
def readiness_funnel():
    """
    Participants retained at each readiness gate (coverage → integrity →
    temporal), overall and per study group. Precomputed by
    scripts/full_cohort_quality.py.
    """
    data = get_readiness_funnel()
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Readiness funnel not found. Run: python scripts/full_cohort_quality.py",
        )
    return data


@router.get("/temporal-overlap/{person_id}")
def temporal_overlap_participant(
    person_id: str,
    tau_days: int = Query(7, ge=0, le=365, description="Co-registration tolerance in days"),
):
    """
    Full temporal timeline for a single participant:
    visit date, CGM window, ECG date, offsets and co-registration flags.
    """
    try:
        return get_temporal_overlap_participant(person_id, tau_days=tau_days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comissingness")
def comissingness_matrix(
    study_group: Optional[str] = Query(None, description="Filter by study group key")
):
    """
    Co-missingness matrix: pairwise modality co-occurrence counts.
    Optionally filtered to a single study group.
    """
    try:
        return get_comissingness_matrix(study_group=study_group)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal-quality")
def signal_quality(
    source: str = Query("auto", pattern="^(auto|precomputed|sample)$",
                        description="auto | precomputed (full cohort) | sample (live stratified sample)"),
):
    """
    Aggregate signal quality metrics: CGM dropout, the Philips four-way ECG
    verdict with 95% Wilson CIs, and HR/QTc distributions. Serves the
    full-cohort results from scripts/full_cohort_quality.py when available,
    otherwise a seeded study-group-stratified live sample.
    """
    try:
        return get_signal_quality_summary(source=source)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labs/cohort")
def cohort_lab_distributions():
    """
    Population-level distributions of HbA1c, glucose, BMI
    broken down by study group.
    """
    try:
        return get_cohort_lab_distributions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labs/{person_id}")
def participant_labs(person_id: str):
    """
    Per-participant OMOP lab values grouped by category
    (glycaemic, cardiovascular, lipids, etc.)
    """
    try:
        return get_participant_labs(person_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ecg-metadata/{person_id}")
def ecg_metadata(person_id: str):
    """
    Parsed ECG metadata for a participant:
    recording date, HR/PR/QT/QTc intervals, firmware,
    filter settings, automated interpretation.
    """
    meta = get_ecg_metadata(person_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"No ECG found for {person_id}")
    return meta


@router.get("/sensor-provenance")
def sensor_provenance():
    """
    Static sensor provenance and calibration metadata
    for all three clinical sites.
    """
    return {
        "ecg": {
            "device":       "Philips PageWriter TC30",
            "firmware":     "A.07.07.07",
            "sampling_hz":  500,
            "leads":        12,
            "hp_filter_hz": 0.15,
            "lp_filter_hz": 100,
            "notch_hz":     60,
            "format":       "WFDB (.hea + .dat)",
            "sites":        ["UW", "UCSD", "UAB"],
            "notes":        "Single 10-second resting ECG per visit. Artifact filter active.",
        },
        "cgm": {
            "device":       "Dexcom G6",
            "interval_min": 5,
            "unit":         "mg/dL",
            "format":       "Open mHealth JSON",
            "sites":        ["UW", "UCSD", "UAB"],
            "notes":        "Factory-calibrated. No fingerstick calibration required. Sensor wear up to 10 days.",
        },
        "wearable": {
            "device":       "Garmin Vivosmart 5",
            "metrics":      ["HR", "SpO2", "Steps", "Stress", "Sleep", "Respiratory rate"],
            "format":       "Open mHealth JSON",
            "sites":        ["UW", "UCSD", "UAB"],
            "notes":        "Optical HR sensor. SpO2 spot measurements. Activity tracked continuously.",
        },
    }
