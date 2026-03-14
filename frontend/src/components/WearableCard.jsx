import { Heart, Wind, Footprints, Moon, Zap } from 'lucide-react'

function StatRow({ icon: Icon, label, value, unit, color }) {
  if (value == null) return null
  return (
    <div className="flex items-center gap-3 py-2.5 border-b last:border-0" style={{ borderColor: 'var(--c-border)' }}>
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: color + '18' }}
      >
        <Icon size={15} style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs" style={{ color: 'var(--c-muted)' }}>{label}</p>
      </div>
      <p className="text-sm font-semibold tabular-nums">
        {typeof value === 'number' ? value.toFixed(value % 1 === 0 ? 0 : 1) : value}
        <span className="text-xs font-normal ml-1" style={{ color: 'var(--c-muted)' }}>{unit}</span>
      </p>
    </div>
  )
}

export default function WearableCard({ wearable }) {
  if (!wearable) return (
    <p className="text-sm py-4 text-center" style={{ color: 'var(--c-muted)' }}>
      No wearable data available
    </p>
  )

  return (
    <div>
      <StatRow icon={Heart}      label="Mean heart rate"     value={wearable.mean_hr}           unit="bpm"   color="#E24B4A" />
      <StatRow icon={Wind}       label="Mean SpO₂"           value={wearable.mean_spo2}         unit="%"     color="#378ADD" />
      <StatRow icon={Footprints} label="Mean daily steps"    value={wearable.mean_steps_per_day} unit="steps" color="#1D9E75" />
      <StatRow icon={Moon}       label="Mean sleep"          value={wearable.sleep_hours}        unit="hrs"   color="#534AB7" />
      <StatRow icon={Zap}        label="Mean stress score"   value={wearable.mean_stress}        unit="/100"  color="#BA7517" />

      <p className="text-xs mt-3" style={{ color: 'var(--c-muted)' }}>
        {wearable.days_covered} day{wearable.days_covered !== 1 ? 's' : ''} of Garmin Vivosmart 5 data
      </p>
    </div>
  )
}
