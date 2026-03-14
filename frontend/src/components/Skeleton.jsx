export function SkeletonBlock({ h = 'h-8', w = 'w-full', className = '' }) {
  return <div className={`skeleton ${h} ${w} ${className}`} />
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card p-5 flex flex-col gap-3">
      <SkeletonBlock h="h-3" w="w-24" />
      <SkeletonBlock h="h-8" w="w-32" />
      {lines > 2 && <SkeletonBlock h="h-3" w="w-16" />}
    </div>
  )
}

export function SkeletonChartCard({ height = 'h-52' }) {
  return (
    <div className="card p-5 flex flex-col gap-3">
      <SkeletonBlock h="h-4" w="w-36" />
      <SkeletonBlock h={height} />
    </div>
  )
}
