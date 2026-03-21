import { useState } from 'react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid } from 'recharts'

const GROUP_COLORS = {
  healthy:         '#1D9E75',
  pre_diabetes:    '#BA7517',
  oral_med:        '#378ADD',
  insulin:         '#D85A30',
}

function pctColor(pct) {
  if (pct >= 80) return '#1D9E75'
  if (pct >= 50) return '#378ADD'
  if (pct >= 25) return '#BA7517'
  if (pct >= 10) return '#D85A30'
  return '#E24B4A'
}

function cellBg(pct) {
  if (pct >= 80) return 'rgba(29,158,117,0.30)'
  if (pct >= 50) return 'rgba(47,123,255,0.25)'
  if (pct >= 25) return 'rgba(186,117,23,0.25)'
  if (pct >= 10) return 'rgba(216,90,48,0.22)'
  return 'rgba(226,75,74,0.18)'
}

// ── Heatmap Grid ──────────────────────────────────────────────────────────────

function HeatmapGrid({ data }) {
  const [hovered, setHovered] = useState(null)

  if (!data?.matrix || !data?.modalities) return null
  const { modalities, matrix, n_total } = data

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs" style={{ color: 'var(--c-muted)' }}>
        Each cell shows the number of participants with <strong style={{ color: 'var(--c-text)' }}>both</strong> modalities present.
        Diagonal = single-modality count. Total cohort: <strong style={{ color: 'var(--c-text)' }}>{n_total?.toLocaleString()}</strong>.
      </p>

      <div className="overflow-x-auto">
        <table style={{ borderCollapse: 'separate', borderSpacing: 2 }}>
          <thead>
            <tr>
              <th style={{ width: 110 }} />
              {modalities.map(m => (
                <th
                  key={m.key}
                  className="text-xs font-medium pb-2"
                  style={{ color: 'var(--c-muted)', minWidth: 72, textAlign: 'center', writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: 90, verticalAlign: 'bottom' }}
                >
                  {m.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, ri) => (
              <tr key={modalities[ri].key}>
                <td
                  className="text-xs pr-3 text-right"
                  style={{ color: 'var(--c-muted)', whiteSpace: 'nowrap', paddingRight: 8 }}
                >
                  {modalities[ri].label}
                </td>
                {row.map((cell, ci) => {
                  const isDiag = ri === ci
                  const isHov  = hovered && (hovered.a === cell.modality_a && hovered.b === cell.modality_b)
                  return (
                    <td
                      key={ci}
                      className="text-center rounded cursor-default transition-all"
                      style={{
                        width: 72, height: 44,
                        background: isDiag ? 'rgba(47,123,255,0.20)' : cellBg(cell.pct),
                        border: isHov ? '1px solid var(--c-accent)' : '1px solid transparent',
                        position: 'relative',
                      }}
                      onMouseEnter={() => setHovered({ a: cell.modality_a, b: cell.modality_b })}
                      onMouseLeave={() => setHovered(null)}
                      title={`${cell.label_a} ∩ ${cell.label_b}: ${cell.count.toLocaleString()} (${cell.pct}%)`}
                    >
                      <div className="flex flex-col items-center justify-center" style={{ height: '100%' }}>
                        <span className="text-xs font-semibold tabular-nums" style={{ color: 'var(--c-text)' }}>
                          {cell.count.toLocaleString()}
                        </span>
                        <span className="text-xs" style={{ color: pctColor(cell.pct), fontSize: 10 }}>
                          {cell.pct}%
                        </span>
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-1" style={{ fontSize: 11, color: 'var(--c-muted)' }}>
        {[
          { label: '≥80%', bg: 'rgba(29,158,117,0.30)' },
          { label: '50–79%', bg: 'rgba(47,123,255,0.25)' },
          { label: '25–49%', bg: 'rgba(186,117,23,0.25)' },
          { label: '10–24%', bg: 'rgba(216,90,48,0.22)' },
          { label: '<10%', bg: 'rgba(226,75,74,0.18)' },
        ].map(l => (
          <span key={l.label} className="flex items-center gap-1">
            <span className="inline-block w-4 h-4 rounded" style={{ background: l.bg }} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Group Breakdown Bar Chart ─────────────────────────────────────────────────

function GroupBreakdown({ data, selectedModality }) {
  if (!data?.group_breakdown) return null

  const chartData = data.group_breakdown.map(g => ({
    name: g.study_group_label,
    group: g.study_group,
    n: g.n,
    value: selectedModality ? (g.modality_counts[selectedModality] || 0) : g.n,
    pct: selectedModality
      ? Math.round((g.modality_counts[selectedModality] || 0) / g.n * 100)
      : 100,
  }))

  const groupColors = {
    'Healthy':   '#1D9E75',
    'Pre-DM':    '#BA7517',
    'Oral Med.': '#378ADD',
    'Insulin':   '#D85A30',
  }

  return (
    <div style={{ height: 180 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="card px-3 py-2 text-xs">
                  <p style={{ color: 'var(--c-muted)' }}>{d.name}</p>
                  <p className="font-semibold">{d.value.toLocaleString()} participants ({d.pct}%)</p>
                </div>
              )
            }}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {chartData.map((d, i) => (
              <Cell key={i} fill={groupColors[d.name] || '#2f7bff'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Triple Overlap Table ──────────────────────────────────────────────────────

function TripleOverlapTable({ data }) {
  if (!data?.triple_overlap?.length) return null
  return (
    <div>
      <p className="text-xs mb-3" style={{ color: 'var(--c-muted)' }}>
        Participants with concurrent <strong style={{ color: 'var(--c-text)' }}>ECG + CGM + Clinical data</strong> — the core ML-ready subset.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {data.triple_overlap.map(g => (
          <div key={g.study_group} className="card2 p-3">
            <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>{g.study_group_label}</p>
            <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>
              {g.n_triple.toLocaleString()}
            </p>
            <p className="text-xs" style={{ color: g.pct >= 70 ? '#5DCAA5' : g.pct >= 40 ? '#EF9F27' : '#E24B4A' }}>
              {g.pct}% of group
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Completeness Histogram ────────────────────────────────────────────────────

function CompletenessHist({ data }) {
  if (!data?.completeness_hist) return null
  const filtered = data.completeness_hist.filter(b => b.count > 0)
  return (
    <div style={{ height: 160 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={filtered} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="n_modalities"
            tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
            tickLine={false} axisLine={false}
            label={{ value: 'Number of modalities', position: 'insideBottom', offset: -2, fill: 'var(--c-muted)', fontSize: 11 }}
          />
          <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="card px-3 py-2 text-xs">
                  <p style={{ color: 'var(--c-muted)' }}>{d.n_modalities} modalities present</p>
                  <p className="font-semibold">{d.count.toLocaleString()} participants</p>
                </div>
              )
            }}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {filtered.map((d, i) => (
              <Cell key={i} fill={d.n_modalities >= 7 ? '#1D9E75' : d.n_modalities >= 4 ? '#378ADD' : '#BA7517'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Main Export ───────────────────────────────────────────────────────────────

export default function ComissingnessMatrix({ data }) {
  const [selectedModality, setSelectedModality] = useState(null)

  if (!data) return null

  return (
    <div className="flex flex-col gap-8">

      {/* Heatmap */}
      <div>
        <h3 className="section-title mb-1">Pairwise modality co-occurrence</h3>
        <HeatmapGrid data={data} />
      </div>

      {/* Triple overlap — key for ML readiness */}
      <div>
        <h3 className="section-title mb-3">ECG + CGM + Clinical triple overlap</h3>
        <TripleOverlapTable data={data} />
      </div>

      {/* Per-group breakdown */}
      <div>
        <div className="flex items-center gap-3 mb-3">
          <h3 className="section-title">Modality presence by study group</h3>
          <select
            className="input-base text-xs"
            style={{ width: 160 }}
            value={selectedModality || ''}
            onChange={e => setSelectedModality(e.target.value || null)}
          >
            <option value="">All participants</option>
            {data.modalities?.map(m => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </div>
        <GroupBreakdown data={data} selectedModality={selectedModality} />
      </div>

      {/* Completeness histogram */}
      <div>
        <h3 className="section-title mb-3">Modality completeness distribution</h3>
        <p className="text-xs mb-3" style={{ color: 'var(--c-muted)' }}>
          How many modalities each participant has (out of 9 total).
        </p>
        <CompletenessHist data={data} />
      </div>

    </div>
  )
}
