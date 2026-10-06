const BASE = import.meta.env.VITE_API_BASE_URL || ''

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // ── Cohort ──────────────────────────────────────────────────────────────
  getCohortSummary:     () => apiFetch('/api/cohort/summary'),
  getAgeDistribution:   () => apiFetch('/api/cohort/age-distribution'),
  getEnrollment:        () => apiFetch('/api/cohort/enrollment'),
  getSiteGroupMatrix:   () => apiFetch('/api/cohort/site-group-matrix'),

  // ── Patients ─────────────────────────────────────────────────────────────
  getPatients: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return apiFetch(`/api/patients${qs ? '?' + qs : ''}`)
  },
  getPatient:         (id) => apiFetch(`/api/patients/${id}`),
  getPatientCGM:      (id) => apiFetch(`/api/patients/${id}/cgm`),
  getPatientECG:      (id) => apiFetch(`/api/patients/${id}/ecg`),
  getPatientWearable: (id) => apiFetch(`/api/patients/${id}/wearable`),
  getPatientSummary:  (id) => apiFetch(`/api/patients/${id}/summary`),

  // ── EDA tools ─────────────────────────────────────────────────────────────
  getTemporalOverlapCohort:      ()    => apiFetch('/api/eda/temporal-overlap/cohort'),
  getTemporalOverlapParticipant: (id)  => apiFetch(`/api/eda/temporal-overlap/${id}`),

  getComissingness: (studyGroup) => {
    const qs = studyGroup ? `?study_group=${encodeURIComponent(studyGroup)}` : ''
    return apiFetch(`/api/eda/comissingness${qs}`)
  },

  getSignalQuality:          (source = 'auto') => apiFetch(`/api/eda/signal-quality?source=${source}`),
  getTemporalOffsets:        () => apiFetch('/api/eda/temporal-offsets'),
  getReadinessFunnel:        () => apiFetch('/api/eda/readiness-funnel'),
  getCohortLabDistributions: () => apiFetch('/api/eda/labs/cohort'),
  getParticipantLabs:        (id) => apiFetch(`/api/eda/labs/${id}`),
  getECGMetadata:            (id) => apiFetch(`/api/eda/ecg-metadata/${id}`),
  getSensorProvenance:       () => apiFetch('/api/eda/sensor-provenance'),
}
