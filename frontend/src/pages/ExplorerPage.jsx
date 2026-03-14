import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight, Check, X } from 'lucide-react'

import { useApi } from '../hooks/useApi'
import { api } from '../utils/api'
import { STUDY_GROUPS, SITES, SPLITS } from '../utils/clinical'
import PageHeader from '../components/PageHeader'
import GroupBadge from '../components/GroupBadge'
import ErrorState from '../components/ErrorState'

const PAGE_SIZE = 25

function FilterSelect({ label, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="label-muted">{label}</label>
      <select
        className="input-base"
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ minWidth: 148 }}
      >
        <option value="">All</option>
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function ModalityDot({ has }) {
  return (
    <span
      className="inline-flex w-4 h-4 rounded-full items-center justify-center flex-shrink-0"
      style={{ background: has ? 'rgba(29,158,117,0.15)' : 'rgba(255,255,255,0.04)' }}
    >
      {has
        ? <Check size={9} style={{ color: '#1D9E75' }} strokeWidth={3} />
        : <X    size={9} style={{ color: 'var(--c-muted)' }} strokeWidth={2} />
      }
    </span>
  )
}

export default function ExplorerPage() {
  const navigate = useNavigate()

  const [page, setPage]         = useState(1)
  const [search, setSearch]     = useState('')
  const [group, setGroup]       = useState('')
  const [site, setSite]         = useState('')
  const [split, setSplit]       = useState('')

  const fetchFn = useCallback(() =>
    api.getPatients({ page, page_size: PAGE_SIZE, study_group: group, site, split, search }),
    [page, search, group, site, split]
  )

  const { data, loading, error } = useApi(fetchFn, [page, search, group, site, split])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  function resetFilters() {
    setPage(1); setSearch(''); setGroup(''); setSite(''); setSplit('')
  }

  const hasFilters = search || group || site || split

  return (
    <div>
      <PageHeader
        title="Patient Explorer"
        subtitle="Browse and filter 2,280 AI-READI participants"
      />

      <div className="px-8 py-6 flex flex-col gap-5">

        {/* ── Filters ──────────────────────────────────────────────────── */}
        <div className="card p-4 flex flex-wrap gap-4 items-end">
          {/* Search */}
          <div className="flex flex-col gap-1 flex-1 min-w-40">
            <label className="label-muted">Search ID</label>
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--c-muted)' }} />
              <input
                className="input-base pl-8"
                placeholder="Participant ID…"
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1) }}
              />
            </div>
          </div>

          <FilterSelect
            label="Study group"
            value={group}
            onChange={v => { setGroup(v); setPage(1) }}
            options={Object.entries(STUDY_GROUPS).map(([k, v]) => ({ value: k, label: v.shortLabel }))}
          />
          <FilterSelect
            label="Clinical site"
            value={site}
            onChange={v => { setSite(v); setPage(1) }}
            options={Object.entries(SITES).map(([k, v]) => ({ value: k, label: v.short }))}
          />
          <FilterSelect
            label="ML split"
            value={split}
            onChange={v => { setSplit(v); setPage(1) }}
            options={Object.entries(SPLITS).map(([k, v]) => ({ value: k, label: v.label }))}
          />

          {hasFilters && (
            <button className="btn-ghost text-xs self-end" onClick={resetFilters}>
              Clear filters
            </button>
          )}
        </div>

        {/* ── Result count ─────────────────────────────────────────────── */}
        {data && (
          <p className="text-sm" style={{ color: 'var(--c-muted)' }}>
            Showing <strong style={{ color: 'var(--c-text)' }}>{data.total.toLocaleString()}</strong> participants
            {hasFilters ? ' matching filters' : ''}
          </p>
        )}

        {/* ── Error ────────────────────────────────────────────────────── */}
        {error && <ErrorState message={error} />}

        {/* ── Table ────────────────────────────────────────────────────── */}
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--c-border)' }}>
                {['ID', 'Site', 'Study Group', 'Age', 'Visit Date', 'Split', 'ECG', 'CGM', 'Wearable', 'Retinal'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium" style={{ color: 'var(--c-muted)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? [...Array(10)].map((_, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--c-border)' }}>
                      {[...Array(10)].map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="skeleton h-4 rounded" style={{ width: j === 2 ? 120 : 60 }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : data?.participants.map(p => (
                    <tr
                      key={p.person_id}
                      className="table-row"
                      onClick={() => navigate(`/patient/${p.person_id}`)}
                    >
                      <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--c-accent2)' }}>
                        {p.person_id}
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--c-muted)' }}>
                        {p.clinical_site}
                      </td>
                      <td className="px-4 py-3">
                        <GroupBadge group={p.study_group} short />
                      </td>
                      <td className="px-4 py-3 tabular-nums">{p.age}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--c-muted)' }}>
                        {p.study_visit_date}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="badge text-xs capitalize"
                          style={{
                            background: { train: 'rgba(29,158,117,0.12)', val: 'rgba(55,138,221,0.12)', test: 'rgba(186,117,23,0.12)' }[p.recommended_split],
                            color: { train: '#5DCAA5', val: '#57a0ff', test: '#EF9F27' }[p.recommended_split],
                          }}
                        >
                          {p.recommended_split}
                        </span>
                      </td>
                      <td className="px-4 py-3"><ModalityDot has={p.has_ecg} /></td>
                      <td className="px-4 py-3"><ModalityDot has={p.has_cgm} /></td>
                      <td className="px-4 py-3"><ModalityDot has={p.has_wearable} /></td>
                      <td className="px-4 py-3"><ModalityDot has={p.has_retinal} /></td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {/* ── Pagination ───────────────────────────────────────────────── */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-xs" style={{ color: 'var(--c-muted)' }}>
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                className="btn-ghost"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                style={{ opacity: page <= 1 ? 0.4 : 1 }}
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                className="btn-ghost"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
                style={{ opacity: page >= totalPages ? 0.4 : 1 }}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
