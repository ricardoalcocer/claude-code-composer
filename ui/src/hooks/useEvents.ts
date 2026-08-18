import { useEffect, useRef, useState } from 'react'

/**
 * Subscribes to /api/events (SSE) and surfaces two monotonically increasing
 * version numbers: `library` bumps when anything writes to the archive (a
 * transform, a finished generation, or Claude composing in a terminal — the
 * server watches the filesystem too), `jobs` bumps on any agent job change.
 *
 * Consumers depend on these in useEffect deps to refetch. On connection loss
 * we retry with backoff; versions only ever move forward, so a reconnect can't
 * cause stale refetches.
 */
export function useEvents() {
  const [library, setLibrary] = useState(0)
  const [jobs, setJobs] = useState(0)
  const [connected, setConnected] = useState(false)
  const retryRef = useRef(1000)

  useEffect(() => {
    let source: EventSource | null = null
    let retryTimer: number | undefined
    let closed = false

    function connect() {
      source = new EventSource('/api/events')
      source.onopen = () => {
        setConnected(true)
        retryRef.current = 1000
      }
      source.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as { library: number; jobs: number }
          setLibrary((v) => Math.max(v, data.library))
          setJobs((v) => Math.max(v, data.jobs))
        } catch { /* ignore malformed frames */ }
      }
      source.onerror = () => {
        setConnected(false)
        source?.close()
        if (closed) return
        retryTimer = window.setTimeout(connect, retryRef.current)
        retryRef.current = Math.min(retryRef.current * 2, 15000)
      }
    }

    connect()
    return () => {
      closed = true
      source?.close()
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
    }
  }, [])

  return { library, jobs, connected }
}
