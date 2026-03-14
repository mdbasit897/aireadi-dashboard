import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Sparkles, Activity, Heart, BarChart3, Loader2 } from 'lucide-react'

import { useApi } from '../hooks/useApi'
import { api } from '../utils/api'
import { SITES } from '../utils/clinical'
import PageHeader from '../components/PageHeader'
import GroupBadge from '../components/GroupBadge'
import ModalityPills from '../components/ModalityPills'
import TIRBar from '../components/TIRBar'
import CGMChart from '../components/CGMChart'
import ECGChart from '../components/ECGChart'
import WearableCard from '../components/WearableCard'
import { SkeletonBlock, SkeletonChartCard } from '../components/Skeleton'
import ErrorState from '../components/ErrorState'
import MetricCard from '../components/MetricCard'

// ── Tab definitions ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'cgm',     label: 'CGM Glucose', icon: BarChart3 },
  { id: 'ecg',     label: 'ECG',         icon: Activity  },
  { id: 'wearable',label: 'Wearable',    icon: Heart     },
]

// ── AI Summary panel ──────────────────────────────────────────────────────────

function AISummaryPanel({ personId }) {
  const [requested, setRequested] = useState(false)
  const { data, loading, error } = useApi(
    () => api.getPatientSummary(personId),
    [personId, requested],
    { skip: !requested }
  )

  return (
    <div
      className="card p-5 border-l-2"
      style={{ borderLeftColor: 'var(--c-accent)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} style={{ color: 'var(--c-accent2)' }} />
        <span className="text-sm font-medium">AI Clinical Summary</span>
        {data && !data.generated && (
          <span className="badge text-xs" style={{ background: 'rgba(186,117,23,0.12)', color: '#EF9F27' }}>
            Rule-based
          </span>
        )}
        {data?.generated && (
          <span className="badge text-xs" style={{ background: 'rgba(47,123,255,0.12)', color: '#57a0ff' }}>
            Claude AI
          </span>
        )}
      </div>

      {!requested && (
        <div>
          <p className="text-sm mb-3" style={{ color: 'var(--c-muted)' }}>
            Generate a concise clinical summary based on this participant's available data.
          </p>
          <button className="btn-primary text-sm" onClick={() => setRequested(true)}>
            <Sparkles size={13} /> Generate summary
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--c-muted)' }}>
          <Loader2 size={14} className="animate-spin" /> Generating…
        </div>
      )}

      {error && (
        <p className="text-sm" style={{ color: '#E24B4A' }}>
          Could not generate summary: {error}
        </p>
      )}

      {data && (
        <p className="text-sm leading-relaxed" style={{ color: 'var(--c-text)' }}>
          {data.summary}
        </p>
      )}
    </div>
  )
}

// ── CGM Tab ───────────────────────────────────────────────────────────────────

function CGMTab({ personId, hasCGM }) {
  const { data, loading, error } = useApi(
    () => api.getPatientCGM(personId),
    [personId],
    { skip: !hasCGM }
  )

  if (!hasCGM) return (
    <p className="text-sm py-8 text-center" style={{ color: 'var(--c-muted)' }}>
      No CGM data available for this participant.
    </p>
  )

  if (loading) return <SkeletonChartCard height="h-64" />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="flex flex-col gap-5">
      {/* TIR metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Time in range"      value={`${data.tir_pct}%`}       sub="70–180 mg/dL" accent="#1D9E75" />
        <MetricCard label="Time below 70"      value={`${data.tir_low_pct}%`}   sub="Hypoglycaemia" accent={data.tir_low_pct > 4 ? '#E24B4A' : undefined} />
        <MetricCard label="Mean glucose"       value={`${data.mean_glucose}`}   sub="mg/dL" />
        <MetricCard label="Monitoring period"  value={`${data.days_covered}`}   sub={`days · ${data.readings_count.toLocaleString()} readings`} />
      </div>

      {/* TIR stacked bar */}
      <div className="card p-5">
        <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
          Time-in-Range breakdown
        </h3>
        <TIRBar cgm={data} />
      </div>

      {/* CGM trace chart */}
      <div className="card p-5">
        <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
          Glucose trace (Dexcom G6)
        </h3>
        <CGMChart series={data.series} />
      </div>
    </div>
  )
}

// ── ECG Tab ───────────────────────────────────────────────────────────────────

function ECGTab({ personId, hasECG }) {
  const { data, loading, error } = useApi(
    () => api.getPatientECG(personId),
    [personId],
    { skip: !hasECG }
  )

  if (!hasECG) return (
    <p className="text-sm py-8 text-center" style={{ color: 'var(--c-muted)' }}>
      No ECG data available for this participant.
    </p>
  )

  if (loading) return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {[...Array(12)].map((_, i) => <SkeletonChartCard key={i} height="h-20" />)}
    </div>
  )
  if (error) return <ErrorState message={error} />

  return (
    <div className="card p-5">
      <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
        12-Lead ECG — Philips PageWriter TC30
      </h3>
      <ECGChart ecg={data} />
    </div>
  )
}

// ── Wearable Tab ──────────────────────────────────────────────────────────────

function WearableTab({ personId, hasWearable }) {
  const { data, loading, error } = useApi(
    () => api.getPatientWearable(personId),
    [personId],
    { skip: !hasWearable }
  )

  if (!hasWearable) return (
    <p className="text-sm py-8 text-center" style={{ color: 'var(--c-muted)' }}>
      No wearable data available for this participant.
    </p>
  )

  if (loading) return <SkeletonChartCard height="h-40" />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="card p-5 max-w-md">
      <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
        Garmin Vivosmart 5 — Summary
      </h3>
      <WearableCard wearable={data} />
    </div>
  )
}

// ── Main Patient Page ─────────────────────────────────────────────────────────

export default function PatientPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('cgm')

  const { data: patient, loading, error } = useApi(() => api.getPatient(id), [id])

  if (loading) return (
    <div className="p-8 flex flex-col gap-4">
      <SkeletonBlock h="h-6" w="w-48" />
      <SkeletonBlock h="h-16" />
      <SkeletonChartCard height="h-48" />
    </div>
  )

  if (error) return (
    <div className="p-8">
      <ErrorState message={`Participant not found: ${error}`} />
    </div>
  )

  if (!patient) return null

  const mods = patient.modalities || {}

  return (
    <div>
      <PageHeader
        title={`Participant ${patient.person_id}`}
        subtitle={`${SITES[patient.clinical_site]?.label || patient.clinical_site} · Visit ${patient.study_visit_date}`}
      >
        <button className="btn-ghost" onClick={() => navigate('/explorer')}>
          <ArrowLeft size={14} /> Back to list
        </button>
      </PageHeader>

      <div className="px-8 py-6 flex flex-col gap-6">

        {/* ── Participant info card ───────────────────────────────────── */}
        <div className="card p-5 fade-up">
          <div className="flex flex-wrap items-start gap-6">
            {/* Avatar */}
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0 text-lg font-bold"
              style={{ background: 'var(--c-surface2)', color: 'var(--c-accent2)', fontFamily: 'Syne, sans-serif' }}
            >
              {patient.person_id}
            </div>

            {/* Details */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-3 mb-2">
                <GroupBadge group={patient.study_group} />
                <span
                  className="badge"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--c-muted)' }}
                >
                  {patient.clinical_site} — {SITES[patient.clinical_site]?.label}
                </span>
                <span
                  className="badge capitalize"
                  style={{
                    background: { train: 'rgba(29,158,117,0.12)', val: 'rgba(55,138,221,0.12)', test: 'rgba(186,117,23,0.12)' }[patient.recommended_split],
                    color:      { train: '#5DCAA5', val: '#57a0ff', test: '#EF9F27' }[patient.recommended_split],
                  }}
                >
                  {patient.recommended_split} set
                </span>
              </div>
              <p className="text-sm mb-3" style={{ color: 'var(--c-muted)' }}>
                Age <strong style={{ color: 'var(--c-text)' }}>{patient.age}</strong> yrs &nbsp;·&nbsp;
                Visit date <strong style={{ color: 'var(--c-text)' }}>{patient.study_visit_date}</strong>
              </p>
              <ModalityPills modalities={mods} />
            </div>
          </div>
        </div>

        {/* ── AI summary ─────────────────────────────────────────────── */}
        <div className="fade-up-d1">
          <AISummaryPanel personId={patient.person_id} />
        </div>

        {/* ── Tabs ───────────────────────────────────────────────────── */}
        <div className="fade-up-d2">
          <div className="flex gap-2 mb-5 border-b pb-3" style={{ borderColor: 'var(--c-border)' }}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`btn-ghost flex items-center gap-1.5 ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <tab.icon size={13} />
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'cgm'      && <CGMTab      personId={id} hasCGM={mods.wearable_blood_glucose}      />}
          {activeTab === 'ecg'      && <ECGTab      personId={id} hasECG={mods.cardiac_ecg}                 />}
          {activeTab === 'wearable' && <WearableTab personId={id} hasWearable={mods.wearable_activity_monitor} />}
        </div>

      </div>
    </div>
  )
}
