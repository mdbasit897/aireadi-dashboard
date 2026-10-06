import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
  LineChart, Line,
} from 'recharts'

const GROUP_LABELS = {
  healthy: 'Healthy',
  pre_diabetes_lifestyle_controlled: 'Pre-DM',
  oral_medication_and_or_non_insulin_injectable_medication_controlled: 'Oral Med.',
  insulin_dependent: 'Insulin',
}
const GROUP_COLORS = {
  healthy: '#1D9E75',
  pre_diabetes_lifestyle_controlled: '#BA7517',
  oral_medication_and_or_non_insulin_injectable_medication_controlled: '#378ADD',
  insulin_dependent: '#D85A30',
}

function PipelineHint({ command }) {
  return (
    <div className="card2 p-4 text-xs" style={{ color: 'var(--c-muted)', lineHeight: 1.7 }}>
      Not computed yet. Run the offline pipeline once on the dataset host:
      <br />
      <code style={{ color: 'var(--c-accent2)' }}>{command}</code>
    </div>
  )
}

function Provenance({ meta }) {
  if (!meta) return null
  return (
    <p className="text-xs mt-2" style={{ color: 'var(--c-muted)', fontSize: 10 }}>
      Computed {meta.generated_at?.slice(0, 10)} by {meta.script}
      {meta.git_commit ? ` @ ${meta.git_commit}` : ''}
      {meta.synthetic ? ' · SYNTHETIC test data' : ''}
    </p>
  )
}

// ── Cohort-wide temporal offsets (scripts/ecg_date_audit.py) ─────────────────

export function CohortOffsetsPanel({ data, error }) {
  if (error) return <PipelineHint command="python scripts/build_readiness_table.py && python scripts/ecg_date_audit.py" />
  if (!data?.offsets) return null

  const { offsets, interpretation, extraction } = data
  const series = [
    { key: 'ecg_minus_visit', label: 'ECG − visit', color: '#1D9E75' },
    { key: 'cgm_minus_visit', label: 'CGM start − visit', color: '#D85A30' },
    { key: 'ecg_minus_cgm',   label: 'ECG − CGM start', color: '#2f7bff' },
  ]
  const bins = offsets.ecg_minus_visit.overall.bins.map((b, i) => {
    const row = { bin: b.bin }
    series.forEach(s => { row[s.key] = offsets[s.key].overall.bins[i]?.pct ?? 0 })
    return row
  })
  const both = offsets.ecg_and_cgm_within_tau_of_visit

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>ECG date extracted</p>
          <p className="text-lg font-bold">{extraction?.date_extracted?.pct}%</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>of {extraction?.n_header_readable} headers</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>ECG + CGM within ±{offsets.tau_days} d of visit</p>
          <p className="text-lg font-bold" style={{ color: '#2f7bff' }}>{both?.pct}%</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>95% CI {both?.ci95?.[0]}–{both?.ci95?.[1]}</p>
        </div>
        <div className="card2 p-3 md:col-span-2">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>What validation_date behaves like (heuristic)</p>
          <p className="text-sm font-semibold">{interpretation?.verdict?.replaceAll('_', ' ')}</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>{interpretation?.note}</p>
        </div>
      </div>

      <div className="card2 p-4">
        <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>
          Distribution of |offset| (% of participants with both dates), anchor = earliest OMOP visit
        </p>
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bins} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border2)" vertical={false} />
              <XAxis dataKey="bin" tick={{ fill: 'var(--c-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis unit="%" tick={{ fill: 'var(--c-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v, name) => [`${v}%`, series.find(s => s.key === name)?.label ?? name]} />
              <Legend formatter={key => series.find(s => s.key === key)?.label ?? key} wrapperStyle={{ fontSize: 11 }} />
              {series.map(s => <Bar key={s.key} dataKey={s.key} fill={s.color} radius={[2, 2, 0, 0]} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <Provenance meta={data._meta} />
      </div>
    </div>
  )
}

// ── Readiness funnel (scripts/full_cohort_quality.py) ────────────────────────

export function ReadinessFunnelPanel({ data, error }) {
  if (error) return <PipelineHint command="python scripts/build_readiness_table.py && python scripts/full_cohort_quality.py" />
  if (!data?.funnel) return null

  const { funnel, params } = data
  const groups = Object.keys(funnel[0]?.by_group ?? {})
  const lines = funnel.map(row => {
    const point = { gate: row.gate }
    groups.forEach(g => { point[g] = row.by_group[g]?.pct_of_G0 })
    return point
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {funnel.map(row => (
          <div key={row.gate} className="card2 p-3">
            <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>{row.gate} · {row.label}</p>
            <p className="text-lg font-bold">{row.n.toLocaleString()}</p>
            <p className="text-xs" style={{ color: 'var(--c-muted)' }}>{row.pct_of_G0}% of G0</p>
          </div>
        ))}
      </div>
      <div className="card2 p-4">
        <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>
          Retained by study group (% of G0) · τ = {params?.tau_days} d · CGM dropout &lt; {params?.max_cgm_dropout_pct}%
          · ECG date in temporal gate: {params?.ecg_temporal ? 'yes' : 'no'}
        </p>
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lines} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border2)" vertical={false} />
              <XAxis dataKey="gate" tick={{ fill: 'var(--c-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis unit="%" domain={[0, 100]} tick={{ fill: 'var(--c-muted)', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v, g) => [`${v}%`, GROUP_LABELS[g] ?? g]} />
              <Legend formatter={g => GROUP_LABELS[g] ?? g} wrapperStyle={{ fontSize: 11 }} />
              {groups.map(g => (
                <Line key={g} type="monotone" dataKey={g} stroke={GROUP_COLORS[g] ?? '#888'} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <Provenance meta={data._meta} />
      </div>
    </div>
  )
}
