import { useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'

// ── Participant Timeline Strip ────────────────────────────────────────────────

function TimelineStrip({ data }) {
  if (!data) return null

  const { visit_date, cgm_start, cgm_end, cgm_days, cgm_dropout_pct,
          ecg_recording_date, ecg_hr, ecg_qtc, ecg_interpretation,
          ecg_has_abnormal, cgm_offset_days, ecg_offset_days,
          cgm_co_registered, ecg_co_registered, tau_days } = data

  const offsetText = d => d == null ? null : d === 0 ? 'same day as visit' : `${d > 0 ? '+' : ''}${d} d from visit`

  const hasVisit = !!visit_date
  const hasCGM   = !!cgm_start
  const hasECG   = !!ecg_recording_date

  // Compute a shared date domain for rendering
  const allDates = [visit_date, cgm_start, cgm_end, ecg_recording_date]
    .filter(Boolean)
    .map(d => new Date(d))

  if (allDates.length === 0) return (
    <p className="text-sm text-center py-8" style={{ color: 'var(--c-muted)' }}>
      No temporal data available for this participant.
    </p>
  )

  const domainStart = new Date(Math.min(...allDates.map(d => d.getTime())))
  const domainEnd   = new Date(Math.max(...allDates.map(d => d.getTime())))
  domainStart.setDate(domainStart.getDate() - 3)
  domainEnd.setDate(domainEnd.getDate() + 3)

  const totalDays = Math.max(1, (domainEnd - domainStart) / 86400000)

  function pct(dateStr) {
    if (!dateStr) return null
    const d = new Date(dateStr)
    return ((d - domainStart) / 86400000 / totalDays) * 100
  }

  function pctSpan(startStr, endStr) {
    if (!startStr || !endStr) return { left: 0, width: 0 }
    const s = new Date(startStr), e = new Date(endStr)
    const left  = ((s - domainStart) / 86400000 / totalDays) * 100
    const width = Math.max(0.5, ((e - s) / 86400000 / totalDays) * 100)
    return { left: `${left}%`, width: `${width}%` }
  }

  const cgmSpan = pctSpan(cgm_start, cgm_end)
  const visitPct = pct(visit_date)
  const ecgPct   = pct(ecg_recording_date)

  const formatDate = d => d ? new Date(d).toLocaleDateString('en-US', { month:'short', day:'numeric' }) : '—'

  return (
    <div className="flex flex-col gap-4">
      {/* Timeline ruler */}
      <div className="relative" style={{ height: 120 }}>

        {/* Date axis */}
        <div className="flex justify-between text-xs mb-2" style={{ color: 'var(--c-muted)' }}>
          <span>{formatDate(domainStart.toISOString())}</span>
          <span>{formatDate(domainEnd.toISOString())}</span>
        </div>

        {/* Track background */}
        <div className="relative" style={{ height: 80 }}>

          {/* ── CGM bar ── */}
          {hasCGM && (
            <div
              className="absolute top-0 flex items-center"
              style={{ ...cgmSpan, height: 28, zIndex: 1 }}
            >
              <div
                className="w-full h-full rounded flex items-center px-2"
                style={{ background: 'rgba(216,90,48,0.25)', border: '1px solid rgba(216,90,48,0.5)' }}
              >
                <span className="text-xs font-medium truncate" style={{ color: '#F09575' }}>
                  CGM {cgm_days}d
                </span>
              </div>
            </div>
          )}

          {/* ── Visit marker ── */}
          {hasVisit && visitPct !== null && (
            <div
              className="absolute flex flex-col items-center"
              style={{ left: `${visitPct}%`, top: 32, transform: 'translateX(-50%)', zIndex: 3 }}
            >
              <div
                className="w-3 h-3 rounded-full border-2"
                style={{ background: '#2f7bff', borderColor: '#fff' }}
                title={`Visit: ${visit_date}`}
              />
              <div
                className="w-px"
                style={{ height: 16, background: 'rgba(47,123,255,0.5)' }}
              />
              <span className="text-xs whitespace-nowrap" style={{ color: 'var(--c-accent2)' }}>
                Visit
              </span>
            </div>
          )}

          {/* ── ECG marker ── */}
          {hasECG && ecgPct !== null && (
            <div
              className="absolute flex flex-col items-center"
              style={{ left: `${ecgPct}%`, top: 32, transform: 'translateX(-50%)', zIndex: 3 }}
            >
              <div
                className="w-3 h-3 rounded"
                style={{
                  background: ecg_has_abnormal ? '#E24B4A' : '#1D9E75',
                  border: '2px solid #fff',
                }}
                title={`ECG: ${ecg_recording_date}`}
              />
              <div
                className="w-px"
                style={{ height: 16, background: 'rgba(29,158,117,0.5)' }}
              />
              <span className="text-xs whitespace-nowrap" style={{ color: '#5DCAA5' }}>
                ECG
              </span>
            </div>
          )}

          {/* Baseline */}
          <div
            className="absolute w-full"
            style={{
              top: 38, height: 2,
              background: 'var(--c-border2)',
              borderRadius: 1,
            }}
          />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Clinical visit</p>
          <p className="text-sm font-semibold">{formatDate(visit_date)}</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>CGM window</p>
          <p className="text-sm font-semibold">
            {hasCGM ? `${formatDate(cgm_start)} → ${formatDate(cgm_end)}` : '—'}
          </p>
          {hasCGM && (
            <p className="text-xs mt-0.5" style={{ color: cgm_dropout_pct > 10 ? '#E24B4A' : 'var(--c-muted)' }}>
              {cgm_days}d · {cgm_dropout_pct}% dropout
            </p>
          )}
          {cgm_offset_days != null && (
            <p className="text-xs mt-0.5" style={{ color: cgm_co_registered ? '#1D9E75' : '#E24B4A' }}>
              {offsetText(cgm_offset_days)} · {cgm_co_registered ? `within ±${tau_days} d` : `outside ±${tau_days} d`}
            </p>
          )}
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>ECG header date (validation_date)</p>
          <p className="text-sm font-semibold">{formatDate(ecg_recording_date)}</p>
          {hasECG && (
            <p className="text-xs mt-0.5" style={{ color: ecg_has_abnormal ? '#E24B4A' : '#5DCAA5' }}>
              {ecg_interpretation || (ecg_has_abnormal ? 'Abnormal flag' : 'Normal')}
            </p>
          )}
          {ecg_offset_days != null && (
            <p className="text-xs mt-0.5" style={{ color: ecg_co_registered ? '#1D9E75' : '#E24B4A' }}>
              {offsetText(ecg_offset_days)} · {ecg_co_registered ? `within ±${tau_days} d` : `outside ±${tau_days} d`}
            </p>
          )}
        </div>
      </div>

      {/* ECG intervals */}
      {hasECG && (ecg_hr || ecg_qtc) && (
        <div className="flex gap-4 flex-wrap">
          {ecg_hr  && <span className="text-xs badge" style={{ background: 'rgba(47,123,255,0.1)', color: '#57a0ff' }}>HR {ecg_hr} bpm</span>}
          {ecg_qtc && (
            <span
              className="text-xs badge"
              style={{
                background: ecg_qtc > 450 ? 'rgba(226,75,74,0.1)' : 'rgba(29,158,117,0.1)',
                color:      ecg_qtc > 450 ? '#E24B4A' : '#5DCAA5',
              }}
            >
              QTc {ecg_qtc} ms{ecg_qtc > 450 ? ' ⚠ prolonged' : ''}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Cohort Overlap Summary ────────────────────────────────────────────────────

function CohortOverlapSummary({ cohortData }) {
  if (!cohortData) return null
  const { total_participants, cgm_present_n, ecg_present_n, both_present_n,
          cgm_pct, ecg_pct, both_pct } = cohortData

  const bars = [
    { label: 'CGM only',     value: cgm_present_n,  pct: cgm_pct,  color: '#D85A30' },
    { label: 'ECG only',     value: ecg_present_n,  pct: ecg_pct,  color: '#1D9E75' },
    { label: 'ECG + CGM',    value: both_present_n, pct: both_pct, color: '#2f7bff' },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        {bars.map(b => (
          <div key={b.label} className="card2 p-4">
            <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>{b.label}</p>
            <p className="text-xl font-bold" style={{ fontFamily: 'Syne, sans-serif', color: b.color }}>
              {b.value.toLocaleString()}
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--c-muted)' }}>{b.pct}% of cohort</p>
          </div>
        ))}
      </div>

      <div className="card p-4">
        <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>
          Modality presence across {total_participants.toLocaleString()} participants
        </p>
        {bars.map(b => (
          <div key={b.label} className="flex items-center gap-3 mb-2 last:mb-0">
            <span className="text-xs w-20 flex-shrink-0" style={{ color: 'var(--c-muted)' }}>{b.label}</span>
            <div className="flex-1 h-4 rounded overflow-hidden" style={{ background: 'var(--c-surface2)' }}>
              <div
                className="h-full rounded transition-all"
                style={{ width: `${b.pct}%`, background: b.color, opacity: 0.8 }}
              />
            </div>
            <span className="text-xs font-semibold tabular-nums w-10 text-right">{b.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function TemporalOverlapChart({ participantData, cohortData, mode = 'participant' }) {
  return (
    <div>
      {mode === 'participant' && participantData && (
        <TimelineStrip data={participantData} />
      )}
      {mode === 'cohort' && cohortData && (
        <CohortOverlapSummary cohortData={cohortData} />
      )}
    </div>
  )
}
