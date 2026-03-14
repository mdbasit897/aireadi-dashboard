import { STUDY_GROUPS } from '../utils/clinical'

export default function GroupBadge({ group, short = false }) {
  const meta = STUDY_GROUPS[group] || { label: group, text: '#8b92a8', bg: 'rgba(139,146,168,0.12)' }
  return (
    <span
      className="badge"
      style={{ background: meta.bg, color: meta.text }}
    >
      {short ? (meta.shortLabel || meta.label) : meta.label}
    </span>
  )
}
