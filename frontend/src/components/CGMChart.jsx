import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, ReferenceLine, CartesianGrid,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value
  return (
    <div
      className="card px-3 py-2 text-xs"
      style={{ minWidth: 140, pointerEvents: 'none' }}
    >
      <p style={{ color: 'var(--c-muted)' }}>{label}</p>
      <p className="font-semibold mt-0.5" style={{ color: val < 70 || val > 180 ? '#E24B4A' : '#1D9E75' }}>
        {val?.toFixed(0)} mg/dL
      </p>
    </div>
  )
}

export default function CGMChart({ series = [] }) {
  // Format timestamps for display
  const data = series.map(pt => ({
    t: new Date(pt.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    glucose: pt.glucose_mg_dl != null ? Math.round(pt.glucose_mg_dl) : null,
  }))

  // Show every Nth label to avoid crowding
  const tickInterval = Math.max(1, Math.floor(data.length / 8))

  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="cgmGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#2f7bff" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#2f7bff" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.05)"
            vertical={false}
          />

          {/* Target range band */}
          <ReferenceLine y={180} stroke="#BA7517" strokeDasharray="4 3" strokeWidth={1} strokeOpacity={0.6} />
          <ReferenceLine y={70}  stroke="#E24B4A" strokeDasharray="4 3" strokeWidth={1} strokeOpacity={0.6} />

          <XAxis
            dataKey="t"
            tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={tickInterval}
          />
          <YAxis
            domain={[40, 320]}
            tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickCount={6}
          />
          <Tooltip content={<CustomTooltip />} />

          <Area
            type="monotone"
            dataKey="glucose"
            stroke="#2f7bff"
            strokeWidth={1.5}
            fill="url(#cgmGrad)"
            dot={false}
            activeDot={{ r: 4, fill: '#2f7bff', strokeWidth: 0 }}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 px-1" style={{ fontSize: 11, color: 'var(--c-muted)' }}>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 border-t border-dashed" style={{ borderColor: '#E24B4A' }} />
          Hypo (&lt;70)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 h-3 rounded-sm opacity-40" style={{ background: '#1D9E75' }} />
          Target 70–180
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 border-t border-dashed" style={{ borderColor: '#BA7517' }} />
          Hyper (&gt;180)
        </span>
      </div>
    </div>
  )
}
