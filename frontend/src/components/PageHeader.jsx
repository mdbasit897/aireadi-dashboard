export default function PageHeader({ title, subtitle, children }) {
  return (
    <div
      className="flex items-start justify-between px-8 pt-8 pb-6 border-b"
      style={{ borderColor: 'var(--c-border)' }}
    >
      <div>
        <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--c-text)' }}>
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm" style={{ color: 'var(--c-muted)' }}>{subtitle}</p>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
