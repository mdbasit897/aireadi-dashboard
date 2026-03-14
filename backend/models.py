from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# ── Cohort ────────────────────────────────────────────────────────────────────

class StudyGroupCount(BaseModel):
    group: str
    label: str
    count: int
    color: str

class SiteCount(BaseModel):
    site: str
    label: str
    count: int

class ModalityCoverage(BaseModel):
    modality: str
    label: str
    count: int
    total: int
    pct: float

class SplitCount(BaseModel):
    split: str
    count: int

class EnrollmentMonth(BaseModel):
    month: str
    count: int
    cumulative: int

class CohortSummary(BaseModel):
    total_participants: int
    age_min: int
    age_max: int
    age_mean: float
    dataset_size: str
    num_files: int
    collection_start: str
    collection_end: str
    study_groups: List[StudyGroupCount]
    sites: List[SiteCount]
    modalities: List[ModalityCoverage]
    splits: List[SplitCount]
    ecg_cgm_overlap: int
    all_modalities_count: int

class AgeBucket(BaseModel):
    bucket: int
    label: str
    count: int

class SiteGroupMatrix(BaseModel):
    site: str
    healthy: int
    pre_diabetes: int
    oral_med: int
    insulin: int


# ── Participant ───────────────────────────────────────────────────────────────

class ParticipantRow(BaseModel):
    person_id: str
    clinical_site: str
    study_group: str
    age: int
    study_visit_date: str
    recommended_split: str
    has_ecg: bool
    has_cgm: bool
    has_wearable: bool
    has_retinal: bool
    has_clinical: bool

class ParticipantList(BaseModel):
    total: int
    page: int
    page_size: int
    participants: List[ParticipantRow]

class ParticipantDetail(BaseModel):
    person_id: str
    clinical_site: str
    clinical_site_label: str
    study_group: str
    study_group_label: str
    age: int
    study_visit_date: str
    recommended_split: str
    modalities: Dict[str, bool]


# ── CGM ──────────────────────────────────────────────────────────────────────

class CGMPoint(BaseModel):
    timestamp: str
    glucose_mg_dl: Optional[float]

class CGMSummary(BaseModel):
    person_id: str
    tir_pct: float          # 70–180 mg/dL
    tir_low_pct: float      # <70
    tir_high_pct: float     # >180
    tir_very_high_pct: float  # >250
    mean_glucose: float
    std_glucose: float
    readings_count: int
    days_covered: float
    series: List[CGMPoint]


# ── ECG ──────────────────────────────────────────────────────────────────────

class ECGLead(BaseModel):
    name: str
    signal: List[float]

class ECGData(BaseModel):
    person_id: str
    fs: int                 # sampling frequency
    duration_sec: float
    leads: List[ECGLead]
    units: str


# ── Wearable ─────────────────────────────────────────────────────────────────

class WearableSummary(BaseModel):
    person_id: str
    mean_hr: Optional[float]
    mean_spo2: Optional[float]
    mean_steps_per_day: Optional[float]
    mean_stress: Optional[float]
    sleep_hours: Optional[float]
    days_covered: int


# ── AI Summary ───────────────────────────────────────────────────────────────

class ClinicalSummary(BaseModel):
    person_id: str
    summary: str
    generated: bool         # False if API key not configured
