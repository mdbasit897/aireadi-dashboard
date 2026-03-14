import { useState, useEffect, useRef } from 'react'

export function useApi(fetchFn, deps = [], { skip = false } = {}) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(!skip)
  const [error, setError]     = useState(null)
  const mountedRef            = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (skip) { setLoading(false); return }
    setLoading(true)
    setError(null)
    fetchFn()
      .then(d  => { if (mountedRef.current) { setData(d);   setLoading(false) } })
      .catch(e => { if (mountedRef.current) { setError(e.message); setLoading(false) } })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, loading, error }
}
