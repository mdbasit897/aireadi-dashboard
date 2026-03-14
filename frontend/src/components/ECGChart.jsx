import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, ReferenceLine, CartesianGrid,
} from 'recharts'

// Standard 12-lead display order
const LEAD_ORDER = ['I','II','III','aVR','aVL','aVF','V1','V2','V3','V4','V5','V6']

function LeadStrip({ name, signal, fs }) {
  // Build time-indexed data array (only first 5 seconds = 5*fs samples)
  const maxSamples = Math.min(signal.length, fs * 5)
  const data = Array.from({ length: maxSamples }, (_, i) => ({
    t: +(i / fs).toFixed(3),
    v: signal[i],
  }))

  return (
    <div className="card2 px-3 pt-2 pb-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium" style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--c-accent2)' }}>
          {name}
        </span>
      </div>
      <div style={{ height: 72 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" />
            <XAxis dataKey="t" hide />
            <YAxis domain={['auto', 'auto']} tick={{ fill: 'var(--c-muted)', fontSize: 9 }} tickLine={false} axisLine={false} tickCount={3} />
            <Line
              type="linear"
              dataKey="v"
              stroke="#2f7bff"
              strokeWidth={1.2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function ECGChart({ ecg }) {
  const [selectedLead, setSelectedLead] = useState(null)

  if (!ecg?.leads?.length) return (
    <p className="text-sm text-center py-8" style={{ color: 'var(--c-muted)' }}>
      No ECG data available
    </p>
  )

  // Sort leads by standard order
  const sorted = [...ecg.leads].sort((a, b) => {
    const ia = LEAD_ORDER.indexOf(a.name)
    const ib = LEAD_ORDER.indexOf(b.name)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  const displayLeads = selectedLead
    ? sorted.filter(l => l.name === selectedLead)
    : sorted

  return (
    <div className="flex flex-col gap-3">
      {/* Lead selector */}
      <div className="flex flex-wrap gap-1.5">
        <button
          className={`btn-ghost text-xs py-1 ${!selectedLead ? 'active' : ''}`}
          onClick={() => setSelectedLead(null)}
        >
          All leads
        </button>
        {sorted.map(l => (
          <button
            key={l.name}
            className={`btn-ghost text-xs py-1 ${selectedLead === l.name ? 'active' : ''}`}
            onClick={() => setSelectedLead(l.name === selectedLead ? null : l.name)}
            style={{ fontFamily: 'JetBrains Mono, monospace' }}
          >
            {l.name}
          </button>
        ))}
      </div>

      {/* ECG strips */}
      <div className={`grid gap-2 ${selectedLead ? 'grid-cols-1' : 'grid-cols-2 md:grid-cols-3'}`}>
        {displayLeads.map(lead => (
          <LeadStrip
            key={lead.name}
            name={lead.name}
            signal={lead.signal}
            fs={ecg.fs}
          />
        ))}
      </div>

      <p className="text-xs" style={{ color: 'var(--c-muted)' }}>
        Showing first 5 s · {ecg.fs} Hz · {ecg.units} · Duration: {ecg.duration_sec}s
      </p>
    </div>
  )
}
