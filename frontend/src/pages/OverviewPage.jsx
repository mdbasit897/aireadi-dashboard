import { useCallback } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, LineChart, Line, CartesianGrid, Cell,
} from 'recharts'
import { RefreshCw } from 'lucide-react'

import { useApi } from '../hooks/useApi'
import { api } from '../utils/api'
import { STUDY_GROUPS } from '../utils/clinical'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import { SkeletonCard, SkeletonChartCard } from '../components/Skeleton'
import ErrorState from '../components/ErrorState'

// ── Tooltip helpers ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs" style={{ pointerEvents: 'none' }}>
      <p style={{ color: 'var(--c-muted)' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="font-semibold" style={{ color: p.color || p.fill || 'var(--c-text)' }}>
          {p.name}: {p.value?.toLocaleString()}
        </p>
      ))}
    </div>
  )
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children, delay = 0 }) {
  return (
    <div className={`fade-up-d${delay}`}>
      <h2 className="section-title mb-4">{title}</h2>
      {children}
    </div>
  )
}

// ── Overview Page ─────────────────────────────────────────────────────────────

export default function OverviewPage() {
  const { data: summary, loading: loadingS, error: errS, } = useApi(api.getCohortSummary, [])
  const { data: ageDist, loading: loadingA } = useApi(api.getAgeDistribution, [])
  const { data: enrollment, loading: loadingE } = useApi(api.getEnrollment, [])
  const { data: matrix, loading: loadingM } = useApi(api.getSiteGroupMatrix, [])

  if (errS) return (
    <div className="p-8">
      <ErrorState message={`Could not load cohort data: ${errS}`} />
    </div>
  )

  return (
    <div>
      <PageHeader
        title="Cohort Overview"
        subtitle="AI-READI v3.0.0 — Flagship Type 2 Diabetes Dataset"
      >
        <span className="text-xs px-2 py-1 rounded" style={{ background: 'rgba(29,158,117,0.12)', color: '#5DCAA5' }}>
          Live data
        </span>
      </PageHeader>

      <div className="px-8 py-6 flex flex-col gap-8">

        {/* ── Key metrics ──────────────────────────────────────────────── */}
        <Section title="Key metrics" delay={1}>
          {loadingS ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Total participants" value={summary.total_participants.toLocaleString()} sub="of ~4,000 target" />
              <MetricCard label="Age range" value={`${summary.age_min}–${summary.age_max}`} sub={`Mean age ${summary.age_mean} yrs`} />
              <MetricCard label="Dataset size" value={summary.dataset_size} sub={`${summary.num_files.toLocaleString()} files`} />
              <MetricCard label="ECG + CGM overlap" value={summary.ecg_cgm_overlap.toLocaleString()} sub={`${((summary.ecg_cgm_overlap / summary.total_participants) * 100).toFixed(1)}% of cohort`} accent="#2f7bff" />
            </div>
          )}
        </Section>

        {/* ── Study groups + sites ─────────────────────────────────────── */}
        <Section title="Cohort composition" delay={2}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Study groups bar chart */}
            <div className="card p-5">
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>Study groups</h3>
              {loadingS ? <SkeletonChartCard height="h-44" /> : (
                <div style={{ height: 176 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={summary.study_groups}
                      layout="vertical"
                      margin={{ top: 0, right: 40, left: 8, bottom: 0 }}
                    >
                      <XAxis type="number" tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
                      <YAxis
                        type="category" dataKey="label"
                        tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                        tickLine={false} axisLine={false} width={130}
                      />
                      <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]} label={{ position: 'right', fill: 'var(--c-muted)', fontSize: 11 }}>
                        {summary.study_groups.map(g => (
                          <Cell key={g.group} fill={g.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Clinical sites */}
            <div className="card p-5">
              <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>Clinical sites</h3>
              {loadingS ? <SkeletonChartCard height="h-44" /> : (
                <div>
                  {summary.sites.map(s => (
                    <div key={s.site} className="flex items-center gap-3 mb-4 last:mb-0">
                      <span className="text-xs font-mono w-10 flex-shrink-0" style={{ color: 'var(--c-accent2)' }}>
                        {s.site}
                      </span>
                      <div className="flex-1 h-5 rounded overflow-hidden" style={{ background: 'var(--c-surface2)' }}>
                        <div
                          className="h-full rounded transition-all"
                          style={{
                            width: `${(s.count / summary.total_participants) * 100}%`,
                            background: 'var(--c-accent)',
                          }}
                        />
                      </div>
                      <span className="text-sm font-semibold tabular-nums w-12 text-right">
                        {s.count}
                      </span>
                    </div>
                  ))}
                  <p className="text-xs mt-4" style={{ color: 'var(--c-muted)' }}>
                    UW · UCSD · UAB — age & sex matched across racial/ethnic groups
                  </p>
                </div>
              )}
            </div>
          </div>
        </Section>

        {/* ── Enrollment timeline ──────────────────────────────────────── */}
        <Section title="Enrollment timeline" delay={2}>
          <div className="card p-5">
            <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
              Monthly enrollment (Jul 2023 – May 2025)
            </h3>
            {loadingE ? <div className="skeleton h-48" /> : enrollment && (
              <div style={{ height: 192 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={enrollment} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                    <defs>
                      <linearGradient id="enrollGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#2f7bff" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#2f7bff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                      tickLine={false} axisLine={false}
                      interval={3}
                      tickFormatter={v => v.slice(2)} // "2024-01" → "24-01"
                    />
                    <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.1)' }} />
                    <Line
                      type="monotone" dataKey="count" name="New participants"
                      stroke="#2f7bff" strokeWidth={2} dot={false}
                      activeDot={{ r: 4, fill: '#2f7bff', strokeWidth: 0 }}
                    />
                    <Line
                      type="monotone" dataKey="cumulative" name="Cumulative"
                      stroke="#1D9E75" strokeWidth={1.5} dot={false} strokeDasharray="4 3"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Section>

        {/* ── Age distribution ─────────────────────────────────────────── */}
        <Section title="Age distribution" delay={3}>
          <div className="card p-5">
            <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--c-muted)' }}>
              Participant age (5-year buckets) — eligible range 40–85 yrs
            </h3>
            {loadingA ? <div className="skeleton h-44" /> : ageDist && (
              <div style={{ height: 176 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ageDist} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: 'var(--c-muted)', fontSize: 11 }}
                      tickLine={false} axisLine={false}
                    />
                    <YAxis tick={{ fill: 'var(--c-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                    <Bar dataKey="count" name="Participants" fill="#2f7bff" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Section>

        {/* ── Modality coverage ────────────────────────────────────────── */}
        <Section title="Modality coverage" delay={3}>
          {loadingS ? (
            <div className="grid grid-cols-3 gap-3">
              {[...Array(9)].map((_, i) => <SkeletonCard key={i} lines={2} />)}
            </div>
          ) : summary && (
            <>
              <div className="grid grid-cols-3 gap-3">
                {summary.modalities.map(m => (
                  <div key={m.modality} className="card2 p-4">
                    <p className="text-xs mb-2" style={{ color: 'var(--c-muted)' }}>{m.label}</p>
                    <div className="h-1.5 rounded-full mb-2" style={{ background: 'var(--c-surface)' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${m.pct}%`, background: m.pct > 95 ? '#1D9E75' : m.pct > 80 ? '#BA7517' : '#D85A30' }}
                      />
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-sm font-semibold">{m.count.toLocaleString()}</span>
                      <span className="text-xs" style={{ color: 'var(--c-muted)' }}>{m.pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs mt-3" style={{ color: 'var(--c-muted)' }}>
                Participants with all 9 modalities: <strong style={{ color: 'var(--c-text)' }}>{summary.all_modalities_count.toLocaleString()}</strong>
                {' '}({((summary.all_modalities_count / summary.total_participants) * 100).toFixed(1)}%)
                &nbsp;·&nbsp; FLIO has the lowest coverage (Heidelberg device only at select sites)
              </p>
            </>
          )}
        </Section>

        {/* ── Train/val/test split ─────────────────────────────────────── */}
        <Section title="Recommended ML split" delay={4}>
          {loadingS ? <SkeletonCard /> : summary && (
            <div className="card p-5 flex flex-wrap gap-6">
              {summary.splits.map(s => {
                const colors = { train: '#1D9E75', val: '#378ADD', test: '#BA7517' }
                const pct = ((s.count / summary.total_participants) * 100).toFixed(1)
                return (
                  <div key={s.split} className="flex items-center gap-3">
                    <div className="w-2 h-8 rounded-full" style={{ background: colors[s.split] }} />
                    <div>
                      <p className="text-xs capitalize" style={{ color: 'var(--c-muted)' }}>{s.split}</p>
                      <p className="text-lg font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>
                        {s.count.toLocaleString()}
                        <span className="text-xs font-normal ml-1.5" style={{ color: 'var(--c-muted)' }}>{pct}%</span>
                      </p>
                    </div>
                  </div>
                )
              })}
              <p className="w-full text-xs mt-2" style={{ color: 'var(--c-muted)' }}>
                Stratified by the dataset creators to reduce demographic bias in ML models.
              </p>
            </div>
          )}
        </Section>

      </div>
    </div>
  )
}
