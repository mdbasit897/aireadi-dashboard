import { tirQuality } from '../utils/clinical'

const ZONES = [
  { key: 'tir_low_pct',      label: 'Low (<70)',    color: '#E24B4A' },
  { key: 'tir_pct',          label: 'In range',     color: '#1D9E75' },
  { key: 'tir_high_pct',     label: 'High (>180)',  color: '#BA7517' },
  { key: 'tir_very_high_pct',label: 'Very high (>250)', color: '#D85A30' },
]

export default function TIRBar({ cgm, showLabels = true }) {
  if (!cgm) return null
  const quality = tirQuality(cgm.tir_pct)

  return (
    <div className="flex flex-col gap-2">
      {/* Stacked bar */}
      <div className="flex h-6 rounded-lg overflow-hidden w-full">
        {ZONES.map(z => {
          const pct = cgm[z.key] || 0
          if (pct < 0.5) return null
          return (
            <div
              key={z.key}
              title={`${z.label}: ${pct}%`}
              style={{ width: `${pct}%`, background: z.color, transition: 'width 0.5s ease' }}
            />
          )
        })}
      </div>

      {showLabels && (
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-3">
            {ZONES.map(z => (
              <span key={z.key} className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--c-muted)' }}>
                <span className="inline-block w-2 h-2 rounded-sm" style={{ background: z.color }} />
                {z.label}: <span style={{ color: 'var(--c-text)' }}>{cgm[z.key] || 0}%</span>
              </span>
            ))}
          </div>
          <span className="text-xs font-medium" style={{ color: quality.color }}>
            {quality.label}
          </span>
        </div>
      )}
    </div>
  )
}
