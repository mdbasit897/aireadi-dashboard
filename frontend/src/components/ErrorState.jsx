import { AlertTriangle } from 'lucide-react'

export default function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <AlertTriangle size={32} style={{ color: 'var(--c-vhigh)' }} />
      <p className="text-sm text-center max-w-xs" style={{ color: 'var(--c-muted)' }}>
        {message || 'Something went wrong loading this data.'}
      </p>
      {onRetry && (
        <button className="btn-ghost text-xs" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
