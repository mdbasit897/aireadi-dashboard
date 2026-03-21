import { useState, useCallback } from 'react'
import { Search, FlaskConical, GitBranch, Activity, Layers, Loader2, Info } from 'lucide-react'

import { useApi } from '../hooks/useApi'
import { api } from '../utils/api'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import { SkeletonChartCard, SkeletonBlock } from '../components/Skeleton'
import TemporalOverlapChart from '../components/TemporalOverlapChart'
import ComissingnessMatrix from '../components/ComissingnessMatrix'
import SignalQualityPanel from '../components/SignalQualityPanel'
import { CohortLabsPanel } from '../components/LabsPanel'

// ── Tab definitions ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'temporal',    label: 'Temporal Overlap',       icon: GitBranch,   desc: 'CGM windows vs visit dates vs ECG recording timestamps' },
  { id: 'missingness', label: 'Co-missingness Matrix',  icon: Layers,      desc: 'Pairwise modality coverage across study groups' },
  { id: 'quality',     label: 'Signal Quality',         icon: Activity,    desc: 'CGM dropout rates, ECG interpretation flags, sensor provenance' },
  { id: 'labs',        label: 'Lab Distributions',      icon: FlaskConical,desc: 'OMOP HbA1c, glucose, BMI distributions by study group' },
]

const STUDY_GROUP_OPTIONS = [
  { value: '',              label: 'All groups' },
  { value: 'healthy',       label: 'Healthy' },
  { value: 'pre_diabetes_lifestyle_controlled', label: 'Pre-DM' },
  { value: 'oral_medication_and_or_non_insulin_injectable_medication_controlled', label: 'Oral Med.' },
  { value: 'insulin_dependent', label: 'Insulin Dependent' },
]

// ── Temporal tab ──────────────────────────────────────────────────────────────

function TemporalTab() {
  const [participantId, setParticipantId] = useState('')
  const [searchId, setSearchId]           = useState('')

  const { data: cohortData, loading: loadingCohort, error: errCohort } =
    useApi(api.getTemporalOverlapCohort, [])

  const { data: participantData, loading: loadingPt, error: errPt } =
    useApi(
      () => api.getTemporalOverlapParticipant(searchId),
      [searchId],
      { skip: !searchId }
    )

  return (
    <div className="flex flex-col gap-6">

      {/* Info banner */}
      <div
        className="flex gap-3 p-4 rounded-xl text-sm"
        style={{ background: 'rgba(47,123,255,0.08)', borderLeft: '3px solid var(--c-accent)' }}
      >
        <Info size={16} style={{ color: 'var(--c-accent2)', flexShrink: 0, marginTop: 2 }} />
        <div style={{ color: 'var(--c-muted)' }}>
          <strong style={{ color: 'var(--c-text)' }}>Key finding: </strong>
          CGM monitoring is initiated at the clinical visit date and runs for approximately 10 days.
          ECG is a single 10-second recording taken at the same visit. All three streams share a
          common temporal anchor: the <code style={{ color: 'var(--c-accent2)' }}>visit_start_date</code> in{' '}
          <code style={{ color: 'var(--c-accent2)' }}>visit_occurrence.csv</code>.
        </div>
      </div>

      {/* Cohort summary */}
      <div className="card p-5">
        <h3 className="section-title mb-4">Cohort-level modality presence</h3>
        {loadingCohort && <SkeletonChartCard height="h-36" />}
        {errCohort    && <ErrorState message={errCohort} />}
        {cohortData   && <TemporalOverlapChart cohortData={cohortData} mode="cohort" />}
      </div>

      {/* Per-participant timeline */}
      <div className="card p-5">
        <h3 className="section-title mb-1">Per-participant timeline</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--c-muted)' }}>
          Enter a participant ID to visualize their temporal data alignment.
        </p>

        <div className="flex gap-3 mb-5">
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--c-muted)' }} />
            <input
              className="input-base pl-8"
              placeholder="Participant ID e.g. 1023"
              value={participantId}
              onChange={e => setParticipantId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && setSearchId(participantId)}
            />
          </div>
          <button
            className="btn-primary"
            onClick={() => setSearchId(participantId)}
            disabled={!participantId}
          >
            {loadingPt ? <Loader2 size={13} className="animate-spin" /> : 'Load timeline'}
          </button>
        </div>

        {errPt && <ErrorState message={errPt} />}

        {participantData && (
          <TemporalOverlapChart participantData={participantData} mode="participant" />
        )}

        {!searchId && (
          <div className="text-center py-8" style={{ color: 'var(--c-muted)' }}>
            <GitBranch size={28} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">Enter a participant ID above to see their data timeline</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Co-missingness tab ────────────────────────────────────────────────────────

function MissingnessTab() {
  const [studyGroup, setStudyGroup] = useState('')

  const fetchFn = useCallback(
    () => api.getComissingness(studyGroup || undefined),
    [studyGroup]
  )
  const { data, loading, error } = useApi(fetchFn, [studyGroup])

  return (
    <div className="flex flex-col gap-5">
      <div
        className="flex gap-3 p-4 rounded-xl text-sm"
        style={{ background: 'rgba(47,123,255,0.08)', borderLeft: '3px solid var(--c-accent)' }}
      >
        <Info size={16} style={{ color: 'var(--c-accent2)', flexShrink: 0, marginTop: 2 }} />
        <div style={{ color: 'var(--c-muted)' }}>
          <strong style={{ color: 'var(--c-text)' }}>How to read this: </strong>
          Each cell shows participants with <em>both</em> modalities present. The diagonal shows
          single-modality counts. Filter by study group to understand ML-ready subsets for
          specific research questions (e.g., ECG+CGM for glucose prediction from cardiac signals).
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-xs" style={{ color: 'var(--c-muted)' }}>Filter by study group:</label>
        <select
          className="input-base text-sm"
          style={{ width: 200 }}
          value={studyGroup}
          onChange={e => setStudyGroup(e.target.value)}
        >
          {STUDY_GROUP_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        {loading && <Loader2 size={14} className="animate-spin" style={{ color: 'var(--c-muted)' }} />}
      </div>

      {error   && <ErrorState message={error} />}
      {loading && <SkeletonChartCard height="h-96" />}
      {data    && <ComissingnessMatrix data={data} />}
    </div>
  )
}

// ── Signal quality tab ────────────────────────────────────────────────────────

function QualityTab() {
  const { data, loading, error } = useApi(api.getSignalQuality, [])

  return (
    <div className="flex flex-col gap-5">
      <div
        className="flex gap-3 p-4 rounded-xl text-sm"
        style={{ background: 'rgba(186,117,23,0.08)', borderLeft: '3px solid #BA7517' }}
      >
        <Info size={16} style={{ color: '#EF9F27', flexShrink: 0, marginTop: 2 }} />
        <div style={{ color: 'var(--c-muted)' }}>
          <strong style={{ color: 'var(--c-text)' }}>Note: </strong>
          Signal quality is sampled across up to 200 participants per modality. CGM dropout is
          computed as (expected − actual readings) / expected, where expected = days × 288.
          ECG quality flags are sourced from the Philips PageWriter automated interpretation
          embedded in each recording's <code style={{ color: '#EF9F27' }}>.hea</code> comment fields.
        </div>
      </div>

      {loading && <SkeletonChartCard height="h-64" />}
      {error   && <ErrorState message={error} />}
      {data    && <SignalQualityPanel data={data} />}
    </div>
  )
}

// ── Labs distribution tab ─────────────────────────────────────────────────────

function LabsTab() {
  const { data, loading, error } = useApi(api.getCohortLabDistributions, [])

  return (
    <div className="flex flex-col gap-5">
      <div
        className="flex gap-3 p-4 rounded-xl text-sm"
        style={{ background: 'rgba(29,158,117,0.08)', borderLeft: '3px solid #1D9E75' }}
      >
        <Info size={16} style={{ color: '#5DCAA5', flexShrink: 0, marginTop: 2 }} />
        <div style={{ color: 'var(--c-muted)' }}>
          <strong style={{ color: 'var(--c-text)' }}>OMOP CDM: </strong>
          Lab values are sourced from <code style={{ color: '#5DCAA5' }}>measurement.csv</code> using
          standard OMOP concept IDs, which map directly to LOINC codes. Charts show median values
          per study group — a strong gradient from Healthy → Insulin Dependent in HbA1c is expected
          and confirms dataset validity.
        </div>
      </div>

      {loading && <SkeletonChartCard height="h-64" />}
      {error   && <ErrorState message={error} />}
      {data    && <CohortLabsPanel data={data} />}
    </div>
  )
}

// ── Main EDA Page ─────────────────────────────────────────────────────────────

export default function EDAPage() {
  const [activeTab, setActiveTab] = useState('temporal')

  const activeTabMeta = TABS.find(t => t.id === activeTab)

  return (
    <div>
      <PageHeader
        title="Exploratory Data Analysis"
        subtitle="AI-READI v3.0.0 — Temporal alignment, modality coverage, and signal quality tools"
      >
        <span
          className="text-xs px-2 py-1 rounded"
          style={{ background: 'rgba(47,123,255,0.12)', color: '#57a0ff' }}
        >
          EDA Tools
        </span>
      </PageHeader>

      <div className="px-8 py-6 flex flex-col gap-6">

        {/* Tab nav */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`btn-ghost flex items-center gap-2 ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <tab.icon size={13} />
                {tab.label}
              </button>
            ))}
          </div>
          {activeTabMeta && (
            <p className="text-xs" style={{ color: 'var(--c-muted)' }}>
              {activeTabMeta.desc}
            </p>
          )}
        </div>

        {/* Tab content */}
        <div className="fade-up">
          {activeTab === 'temporal'    && <TemporalTab />}
          {activeTab === 'missingness' && <MissingnessTab />}
          {activeTab === 'quality'     && <QualityTab />}
          {activeTab === 'labs'        && <LabsTab />}
        </div>

      </div>
    </div>
  )
}
