import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid, ReferenceLine } from 'recharts'

const CATEGORY_COLORS = {
  glycaemic:      '#D85A30',
  cardiovascular: '#E24B4A',
  lipids:         '#BA7517',
  anthropometric: '#378ADD',
  haematology:    '#534AB7',
  renal:          '#1D9E75',
  metabolic:      '#5DCAA5',
  inflammatory:   '#EF9F27',
  cognitive:      '#AFA9EC',
  other:          '#8b92a8',
}

const CATEGORY_ORDER = [
  'glycaemic', 'cardiovascular', 'anthropometric',
  'lipids', 'renal', 'haematology', 'metabolic', 'inflammatory', 'cognitive',
]

// Clinical reference ranges for key markers
const REFERENCE_RANGES = {
  3004410: { low: null, high: 5.7,  unit: '%',     label: 'Normal <5.7%' },
  3004501: { low: 70,   high: 100,  unit: 'mg/dL', label: 'Fasting 70–100' },
  4245997: { low: 18.5, high: 24.9, unit: 'kg/m²', label: 'Normal 18.5–24.9' },
  3004249: { low: null, high: 120,  unit: 'mmHg',  label: 'Normal <120' },
  3012888: { low: null, high: 80,   unit: 'mmHg',  label: 'Normal <80' },
}

function LabRow({ lab }) {
  const ref = REFERENCE_RANGES[lab.concept_id]
  const isHigh = ref?.high && lab.value > ref.high
  const isLow  = ref?.low  && lab.value < ref.low
  const flagged = isHigh || isLow

  return (
    <div
      className="flex items-center justify-between py-2.5 border-b last:border-0"
      style={{ borderColor: 'var(--c-border)' }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm">{lab.label}</p>
        {lab.loinc && (
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>LOINC {lab.loinc}</p>
        )}
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        {ref && (
          <span className="text-xs" style={{ color: 'var(--c-muted)' }}>{ref.label}</span>
        )}
        <span
          className="text-sm font-semibold tabular-nums"
          style={{ color: flagged ? '#E24B4A' : 'var(--c-text)' }}
        >
          {lab.value}
          <span className="text-xs font-normal ml-1" style={{ color: 'var(--c-muted)' }}>
            {lab.unit}
          </span>
        </span>
        {flagged && (
          <span
            className="badge text-xs"
            style={{ background: 'rgba(226,75,74,0.12)', color: '#E24B4A' }}
          >
            {isHigh ? '↑' : '↓'}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Cohort distribution box plot approximation ────────────────────────────────

function GroupBoxPlot({ distribution }) {
  if (!distribution?.groups?.length) return null

  const { label, unit, groups } = distribution
  const groupColors = {
    healthy:     '#1D9E75',
    pre_diabetes_lifestyle_controlled: '#BA7517',
    oral_medication_and_or_non_insulin_injectable_medication_controlled: '#378ADD',
    insulin_dependent: '#D85A30',
  }
  const groupLabels = {
    healthy:     'Healthy',
    pre_diabetes_lifestyle_controlled: 'Pre-DM',
    oral_medication_and_or_non_insulin_injectable_medication_controlled: 'Oral Med.',
    insulin_dependent: 'Insulin',
  }

  return (
    <div>
      <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>
        {label} ({unit}) — median by study group
      </p>
      <div style={{ height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={groups.map(g => ({ ...g, name: groupLabels[g.study_group] || g.study_group }))}
            margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0].payload
                return (
                  <div className="card px-3 py-2 text-xs">
                    <p style={{ color: 'var(--c-muted)' }}>{d.name} (n={d.n})</p>
                    <p>Median: <strong>{d.p50} {unit}</strong></p>
                    <p style={{ color: 'var(--c-muted)' }}>IQR: {d.p25}–{d.p75}</p>
                    <p style={{ color: 'var(--c-muted)' }}>Range: {d.min}–{d.max}</p>
                  </div>
                )
              }}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Bar dataKey="p50" name="Median" radius={[3, 3, 0, 0]}>
              {groups.map((g, i) => (
                <Cell key={i} fill={groupColors[g.study_group] || '#2f7bff'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── Main Export ───────────────────────────────────────────────────────────────

export function ParticipantLabsPanel({ data }) {
  if (!data?.labs?.length) return (
    <p className="text-sm text-center py-6" style={{ color: 'var(--c-muted)' }}>
      No lab data available for this participant.
    </p>
  )

  const { categories } = data

  return (
    <div className="flex flex-col gap-5">
      {CATEGORY_ORDER.map(cat => {
        const labs = categories[cat]
        if (!labs?.length) return null
        const color = CATEGORY_COLORS[cat] || '#8b92a8'
        return (
          <div key={cat}>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              <p className="text-xs font-semibold uppercase tracking-wider" style={{ color }}>
                {cat}
              </p>
            </div>
            <div className="card p-3">
              {labs.map((lab, i) => <LabRow key={i} lab={lab} />)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function CohortLabsPanel({ data }) {
  if (!data) return null
  return (
    <div className="flex flex-col gap-6">
      {Object.entries(data).map(([key, dist]) => (
        <div key={key} className="card p-5">
          <GroupBoxPlot distribution={dist} />
        </div>
      ))}
    </div>
  )
}
