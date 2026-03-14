export const STUDY_GROUPS = {
  healthy: {
    label: 'Healthy',
    shortLabel: 'Healthy',
    color: '#1D9E75',
    bg: 'rgba(29,158,117,0.12)',
    text: '#5DCAA5',
  },
  pre_diabetes_lifestyle_controlled: {
    label: 'Pre-DM / Lifestyle',
    shortLabel: 'Pre-DM',
    color: '#BA7517',
    bg: 'rgba(186,117,23,0.12)',
    text: '#EF9F27',
  },
  oral_medication_and_or_non_insulin_injectable_medication_controlled: {
    label: 'Oral / Non-insulin',
    shortLabel: 'Oral Med.',
    color: '#378ADD',
    bg: 'rgba(55,138,221,0.12)',
    text: '#57a0ff',
  },
  insulin_dependent: {
    label: 'Insulin Dependent',
    shortLabel: 'Insulin',
    color: '#D85A30',
    bg: 'rgba(216,90,48,0.12)',
    text: '#F09575',
  },
}

export const SITES = {
  UW:   { label: 'Univ. of Washington',      short: 'UW'   },
  UCSD: { label: 'UC San Diego',              short: 'UCSD' },
  UAB:  { label: 'Univ. of Alabama, Birmingham', short: 'UAB'  },
}

export const SPLITS = {
  train: { label: 'Train', color: '#1D9E75' },
  val:   { label: 'Val',   color: '#378ADD' },
  test:  { label: 'Test',  color: '#BA7517' },
}

export const MODALITY_META = {
  cardiac_ecg:                  { label: 'ECG',           icon: '⚡' },
  clinical_data:                { label: 'Clinical',      icon: '🩺' },
  environment:                  { label: 'Environment',   icon: '🌡' },
  retinal_flio:                 { label: 'FLIO',          icon: '👁' },
  retinal_oct:                  { label: 'OCT',           icon: '👁' },
  retinal_octa:                 { label: 'OCTA',          icon: '👁' },
  retinal_photography:          { label: 'Retinal Photo', icon: '📷' },
  wearable_activity_monitor:    { label: 'Wearable',      icon: '⌚' },
  wearable_blood_glucose:       { label: 'CGM',           icon: '📈' },
}

// Glucose zone helpers
export function glucoseZone(mgdl) {
  if (mgdl === null || mgdl === undefined) return 'unknown'
  if (mgdl < 54)  return 'very-low'
  if (mgdl < 70)  return 'low'
  if (mgdl <= 180) return 'normal'
  if (mgdl <= 250) return 'high'
  return 'very-high'
}

export const GLUCOSE_ZONE_COLORS = {
  'very-low': '#E24B4A',
  'low':      '#E24B4A',
  'normal':   '#1D9E75',
  'high':     '#BA7517',
  'very-high':'#D85A30',
}

export function tirQuality(tirPct) {
  if (tirPct >= 70) return { label: 'Good control',   color: '#1D9E75' }
  if (tirPct >= 50) return { label: 'Moderate control', color: '#BA7517' }
  return              { label: 'Poor control',    color: '#D85A30' }
}
