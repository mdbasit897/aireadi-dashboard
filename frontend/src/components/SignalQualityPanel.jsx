import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, Cell, CartesianGrid,
} from 'recharts'

function MiniBar({ label, pct, color, sublabel }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--c-muted)' }}>{label}</span>
        <span className="text-xs font-semibold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-2 rounded-full" style={{ background: 'var(--c-surface2)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {sublabel && <span className="text-xs" style={{ color: 'var(--c-muted)', fontSize: 10 }}>{sublabel}</span>}
    </div>
  )
}

function HistogramBar({ data, color }) {
  if (!data?.length) return <p className="text-xs text-center py-4" style={{ color: 'var(--c-muted)' }}>No data</p>
  return (
    <div style={{ height: 120 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis dataKey="bin" tick={{ fill: 'var(--c-muted)', fontSize: 9 }} tickLine={false} axisLine={false} interval={0} angle={-30} textAnchor="end" height={30} />
          <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 9 }} tickLine={false} axisLine={false} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              return (
                <div className="card px-2 py-1.5 text-xs">
                  <p style={{ color: 'var(--c-muted)' }}>{payload[0].payload.bin}</p>
                  <p className="font-semibold">{payload[0].value} participants</p>
                </div>
              )
            }}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]} fill={color} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── CGM Quality Panel ─────────────────────────────────────────────────────────

function CGMQualityPanel({ cgm }) {
  if (!cgm || !Object.keys(cgm).length) return (
    <p className="text-sm text-center py-6" style={{ color: 'var(--c-muted)' }}>
      CGM quality data unavailable.
    </p>
  )

  const dropoutColor = cgm.mean_dropout_pct < 5 ? '#1D9E75' : cgm.mean_dropout_pct < 15 ? '#BA7517' : '#E24B4A'

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Sampled</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>{cgm.n_sampled}</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>of {cgm.n_total} with CGM</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Mean dropout</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif', color: dropoutColor }}>
            {cgm.mean_dropout_pct}%
          </p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>missing readings</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>&lt;5% dropout</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif', color: '#1D9E75' }}>
            {cgm.pct_under5_dropout}%
          </p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>high quality</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Mean duration</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>{cgm.mean_duration_days}d</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>CGM wear time</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card2 p-4">
          <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>Dropout rate distribution (%)</p>
          <HistogramBar data={cgm.dropout_hist} color="#D85A30" />
        </div>
        <div className="card2 p-4">
          <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>CGM duration distribution (days)</p>
          <HistogramBar data={cgm.duration_hist} color="#2f7bff" />
        </div>
      </div>

      <div className="card2 p-4 text-xs" style={{ color: 'var(--c-muted)', lineHeight: 1.8 }}>
        <span className="font-medium" style={{ color: 'var(--c-text)' }}>Device: </span>Dexcom G6 · 5-min intervals · factory-calibrated · no fingerstick required
        <br />
        <span className="font-medium" style={{ color: 'var(--c-text)' }}>Dropout definition: </span>
        (expected readings − actual readings) / expected, where expected = days × 288
      </div>
    </div>
  )
}

// ── ECG Quality Panel ─────────────────────────────────────────────────────────

function ECGQualityPanel({ ecg }) {
  if (!ecg || !Object.keys(ecg).length) return (
    <p className="text-sm text-center py-6" style={{ color: 'var(--c-muted)' }}>
      ECG quality data unavailable.
    </p>
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Sampled</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>{ecg.n_sampled}</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>of {ecg.n_total} with ECG</p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Normal interpretation</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif', color: '#1D9E75' }}>
            {ecg.pct_normal}%
          </p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Abnormal flag</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif', color: ecg.pct_abnormal_flag > 20 ? '#E24B4A' : '#BA7517' }}>
            {ecg.pct_abnormal_flag}%
          </p>
        </div>
        <div className="card2 p-3">
          <p className="text-xs mb-1" style={{ color: 'var(--c-muted)' }}>Mean HR</p>
          <p className="text-lg font-bold" style={{ fontFamily: 'Syne, sans-serif' }}>{ecg.mean_hr}</p>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>bpm</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card2 p-4">
          <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>HR distribution (bpm)</p>
          <HistogramBar data={ecg.hr_hist} color="#1D9E75" />
        </div>
        <div className="card2 p-4">
          <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-muted)' }}>
            QTc distribution (ms)
            <span className="ml-2" style={{ color: '#E24B4A' }}>— &gt;450ms = prolonged</span>
          </p>
          <HistogramBar data={ecg.qtc_hist} color="#D85A30" />
        </div>
      </div>

      {/* Sensor provenance */}
      <div className="card2 p-4">
        <p className="text-xs font-medium mb-3" style={{ color: 'var(--c-text)' }}>Sensor provenance</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1.5 text-xs" style={{ color: 'var(--c-muted)' }}>
          {[
            ['Device',         ecg.device_model],
            ['Firmware',       ecg.firmware],
            ['Sampling rate',  `${ecg.sampling_rate_hz} Hz`],
            ['HP filter',      `${ecg.hp_filter_hz} Hz`],
            ['LP filter',      `${ecg.lp_filter_hz} Hz`],
            ['Notch filter',   `${ecg.notch_filter_hz} Hz`],
          ].map(([k, v]) => (
            <div key={k}>
              <span style={{ color: 'var(--c-text)' }}>{k}: </span>{v}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main Export ───────────────────────────────────────────────────────────────

export default function SignalQualityPanel({ data }) {
  if (!data) return null
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h3 className="section-title mb-4">CGM signal quality (Dexcom G6)</h3>
        <CGMQualityPanel cgm={data.cgm} />
      </div>
      <div>
        <h3 className="section-title mb-4">ECG quality & provenance (Philips TC30)</h3>
        <ECGQualityPanel ecg={data.ecg} />
      </div>
    </div>
  )
}
