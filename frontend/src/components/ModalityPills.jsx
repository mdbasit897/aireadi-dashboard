import { MODALITY_META } from '../utils/clinical'
import clsx from 'clsx'

export default function ModalityPills({ modalities = {} }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.entries(MODALITY_META).map(([key, meta]) => {
        const has = modalities[key]
        return (
          <span
            key={key}
            className={clsx(
              'badge text-xs',
              has
                ? 'bg-[rgba(29,158,117,0.12)] text-[#5DCAA5]'
                : 'bg-[rgba(255,255,255,0.04)] text-[var(--c-muted)] line-through opacity-50'
            )}
          >
            {meta.label}
          </span>
        )
      })}
    </div>
  )
}
