export default function MetricCard({ label, value, sub, accent, className = '' }) {
  return (
    <div
      className={`card p-5 flex flex-col gap-1 ${className}`}
      style={accent ? { borderColor: accent + '33' } : {}}
    >
      <p className="label-muted">{label}</p>
      <p className="metric-val" style={accent ? { color: accent } : {}}>
        {value}
      </p>
      {sub && (
        <p className="text-xs" style={{ color: 'var(--c-muted)' }}>{sub}</p>
      )}
    </div>
  )
}
