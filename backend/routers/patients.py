from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services import (
    get_participant_list,
    get_participant_detail,
    get_cgm_data,
    get_ecg_data,
    get_wearable_summary,
    get_clinical_summary,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("")
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    study_group: Optional[str] = None,
    site: Optional[str] = None,
    split: Optional[str] = None,
    search: Optional[str] = None,
):
    """Paginated, filterable patient list."""
    return get_participant_list(
        page=page,
        page_size=page_size,
        study_group=study_group,
        site=site,
        split=split,
        search=search,
    )


@router.get("/{person_id}")
def patient_detail(person_id: str):
    detail = get_participant_detail(person_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Participant {person_id} not found")
    return detail


@router.get("/{person_id}/cgm")
def patient_cgm(person_id: str):
    detail = get_participant_detail(person_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Participant {person_id} not found")
    if not detail["modalities"].get("wearable_blood_glucose"):
        raise HTTPException(status_code=404, detail="No CGM data for this participant")
    data = get_cgm_data(person_id)
    if not data:
        raise HTTPException(status_code=404, detail="CGM files not found on disk")
    return data


@router.get("/{person_id}/ecg")
def patient_ecg(person_id: str):
    detail = get_participant_detail(person_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Participant {person_id} not found")
    if not detail["modalities"].get("cardiac_ecg"):
        raise HTTPException(status_code=404, detail="No ECG data for this participant")
    data = get_ecg_data(person_id)
    if not data:
        raise HTTPException(status_code=404, detail="ECG files not found on disk")
    return data


@router.get("/{person_id}/wearable")
def patient_wearable(person_id: str):
    detail = get_participant_detail(person_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Participant {person_id} not found")
    if not detail["modalities"].get("wearable_activity_monitor"):
        raise HTTPException(status_code=404, detail="No wearable data for this participant")
    data = get_wearable_summary(person_id)
    if not data:
        raise HTTPException(status_code=404, detail="Wearable files not found on disk")
    return data


@router.get("/{person_id}/summary")
def patient_summary(person_id: str):
    """AI-generated (or rule-based) clinical summary."""
    detail = get_participant_detail(person_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Participant {person_id} not found")
    cgm = get_cgm_data(person_id)
    wearable = get_wearable_summary(person_id)
    return get_clinical_summary(detail, cgm, wearable)
